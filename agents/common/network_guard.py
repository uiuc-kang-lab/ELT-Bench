"""Host-owned lifecycle for restricted networking in task containers.

The proxy is not the enforcement boundary by itself: the workload's network
namespace also denies every direct connection except explicitly declared TCP
services. Nothing here changes the host firewall or an existing task container.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import subprocess
from pathlib import Path
from typing import Any

from .network_firewall import apply_container_firewall
from .network_policy import NetworkPolicy
from .network_proxy import RestrictedProxy, _host


NETWORK_INSTRUCTION = """
Network access is restricted to the model API and the task's declared services.
Use the supplied task definition, schemas, local documentation, and source data.
Do not fetch external solutions, SQL models, benchmark outputs, or ground truth.
Public package downloads are unavailable during the task; use installed tools.
Prepared images include the Airbyte Terraform provider in a local mirror and
dbt-utils at /opt/elt/dbt_utils (use a local packages.yml dependency if needed).
""".strip()


def _is_hostname(name: Any) -> bool:
    try:
        _host(name.lower())
    except (AttributeError, ValueError):
        return False
    return True


def _docker_json(*args: str) -> Any:
    result = subprocess.run(
        ["docker", *args], check=True, text=True, capture_output=True,
    )
    return json.loads(result.stdout)


def policy_identity(mode: str, extra_endpoints: tuple[str, ...] = ()) -> dict[str, Any]:
    """A run-selection marker, never a replacement for the resolved allowlist."""
    return {
        "version": 2, "mode": mode,
        "extra_endpoints_sha256": hashlib.sha256(
            json.dumps(sorted(set(extra_endpoints))).encode()
        ).hexdigest(),
    }


def require_matching_network_policy(
    result: dict[str, Any], mode: str, extra_endpoints: tuple[str, ...] = (),
) -> None:
    previous = result.get("network_access")
    requested = policy_identity(mode, extra_endpoints)
    # Missing metadata belongs to the old unrestricted runner. Explicitly
    # selecting that mode permits historical reproduction, never silent reuse
    # of an old result as a restricted evaluation.
    if previous is None and mode == "unrestricted":
        return
    if previous != requested:
        raise RuntimeError(
            "Existing result was produced with a different or unknown network "
            "policy. Choose a new --suffix/--output_dir, or explicitly use "
            "--overwrite to rerun it."
        )


def check_offline_dependencies(image: str, *, transform_only: bool = False) -> None:
    """Check the trusted image before resetting any warehouse namespace."""
    hint = (
        "Build a prepared image with agents/common/offline-deps.Dockerfile "
        "and select it with --image; see agents/README.md."
    )
    try:
        _docker_json("image", "inspect", image)
    except (subprocess.SubprocessError, ValueError):
        raise RuntimeError(f"Restricted-run image is unavailable locally. {hint}") from None
    if transform_only:
        return
    script = (
        "import os,pathlib; "
        "assert os.environ.get('TF_CLI_CONFIG_FILE') == '/opt/elt/terraform.rc'; "
        "assert pathlib.Path('/opt/elt/terraform.rc').is_file(); "
        "assert any(pathlib.Path('/opt/elt/terraform-providers/registry.terraform.io/"
        "airbytehq/airbyte').glob('terraform-provider-airbyte_0.6.5_*.zip'))"
    )
    try:
        subprocess.run(
            ["docker", "run", "--rm", "--network", "none", "--cap-drop=ALL",
             "--security-opt=no-new-privileges:true", "--entrypoint", "python",
             image, "-I", "-c", script],
            check=True, capture_output=True, text=True, timeout=30,
        )
    except subprocess.SubprocessError:
        raise RuntimeError(f"Restricted full-ELT run requires the offline Terraform mirror. {hint}") from None


class ContainerNetworkGuard:
    """One proxy and one immutable egress policy for a newly created container."""

    def __init__(self, policy: NetworkPolicy, network: str, audit_path: Path):
        self.policy = policy
        self.network = network
        self.audit_path = Path(audit_path)
        self.proxy: RestrictedProxy | None = None
        self.proxy_url: str | None = None
        self.firewall: dict[str, Any] | None = None
        self.host_address_map: dict[str, str] = {}
        self.status = "not_started"

    def start(self) -> None:
        if self.proxy is not None:
            raise RuntimeError("Network guard already started")
        info = _docker_json("network", "inspect", self.network)[0]
        if info.get("Driver") != "bridge":
            raise RuntimeError("Restricted networking requires a Linux Docker bridge")
        gateways = [
            item.get("Gateway") for item in info.get("IPAM", {}).get("Config", [])
            if item.get("Gateway")
        ]
        gateway = next(
            (host for host in gateways if ipaddress.ip_address(host).version == 4), None,
        )
        if gateway is None:
            raise RuntimeError("Docker bridge has no IPv4 gateway for the trusted proxy")
        # Docker's embedded DNS knows service aliases; the trusted host proxy
        # does not. Resolve those aliases from daemon-owned metadata, without
        # expanding the endpoint allowlist or trusting task-written hosts files.
        self.host_address_map = {"host.docker.internal": gateway}
        for container_id, member in info.get("Containers", {}).items():
            address = member.get("IPv4Address")
            if not address:
                continue
            address = str(ipaddress.ip_interface(address).ip)
            try:
                attached = _docker_json("inspect", container_id)[0]
            except (subprocess.CalledProcessError, ValueError, IndexError):
                # "ep-<id>" entries (a container being created or removed by a
                # parallel runner) cannot be inspected; keep only their name.
                attached = {}
            endpoint = attached.get("NetworkSettings", {}).get("Networks", {}).get(self.network, {})
            for name in [member.get("Name"), *(endpoint.get("Aliases") or [])]:
                # Other task containers on the bridge are named like
                # "...-snowflake-apple_store": not valid hostnames, and never
                # allowed endpoints. Skip them instead of failing this task.
                if _is_hostname(name):
                    self.host_address_map[name.lower()] = address
        # Start closed to clients until the new task container's address is known.
        self.proxy = RestrictedProxy(
            self.policy.http_endpoints, bind_host=gateway, allowed_client_ip="0.0.0.0",
            host_address_map=self.host_address_map,
        )
        self.proxy_url = self.proxy.start()
        self.status = "proxy_ready"

    @property
    def docker_security_args(self) -> list[str]:
        return ["--cap-drop=ALL", "--security-opt=no-new-privileges:true"]

    @property
    def environment(self) -> dict[str, str]:
        if self.proxy_url is None:
            raise RuntimeError("Start the trusted proxy before creating the container")
        return {
            "HTTP_PROXY": self.proxy_url, "HTTPS_PROXY": self.proxy_url,
            "http_proxy": self.proxy_url, "https_proxy": self.proxy_url,
            "ALL_PROXY": "", "all_proxy": "",
            "NO_PROXY": "localhost,127.0.0.1,::1",
            "no_proxy": "localhost,127.0.0.1,::1",
        }

    def install(self, container_name: str) -> None:
        if self.proxy is None or self.proxy_url is None:
            raise RuntimeError("Network proxy is not running")
        info = _docker_json("inspect", container_name)[0]
        endpoint = info.get("NetworkSettings", {}).get("Networks", {}).get(self.network)
        if not endpoint or not endpoint.get("IPAddress"):
            raise RuntimeError("Task container is not attached to the expected bridge")
        self.proxy.set_allowed_client_ip(endpoint["IPAddress"])
        from urllib.parse import urlsplit

        url = urlsplit(self.proxy_url)
        try:
            self.firewall = apply_container_firewall(
                container_name, url.hostname, url.port,
                direct_tcp_endpoints=[
                    (self.host_address_map.get(host, host), port)
                    for host, port in self.policy.direct_tcp_endpoints
                ],
            )
        except Exception:
            self.status = "installation_failed"
            self.save_audit()
            raise
        self.status = "enforced"
        self.save_audit()

    def manifest(self) -> dict[str, Any]:
        policy = self.policy.to_dict()
        return {
            "version": 1, "mode": "restricted", "status": self.status,
            "policy": policy,
            "policy_sha256": hashlib.sha256(
                json.dumps(policy, sort_keys=True).encode()
            ).hexdigest(),
            "firewall": self.firewall,
            "docker_host_address_map": self.host_address_map,
            "proxy_events": list(self.proxy.events) if self.proxy else [],
            "scope": "Direct connections from the task container; allowed services "
                     "retain their own permissions and upstream network access.",
        }

    def save_audit(self) -> None:
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.audit_path.with_suffix(self.audit_path.suffix + ".tmp")
        temporary.write_text(json.dumps(self.manifest(), indent=2) + "\n")
        temporary.replace(self.audit_path)

    def close(self) -> None:
        # The runner removes the task container first; its namespace and rules
        # disappear together. No host firewall cleanup is needed.
        if self.proxy is not None:
            self.proxy.close()
        self.save_audit()


def add_network_arguments(parser: Any) -> None:
    parser.add_argument(
        "--network-access", choices=("restricted", "unrestricted"), default="restricted",
        help="Default: enforce task-container egress allowlist. Unrestricted is "
             "only for explicitly reproducing historical runs.",
    )
    parser.add_argument(
        "--network-allow", action="append", default=[], metavar="HOST:PORT",
        help="Additional operator-approved exact HTTP(S) endpoint. Repeat as needed; "
             "never add public code, benchmark, or GT hosting for normal evaluations.",
    )

"""Fail-closed egress rules for a fresh, local Docker task network namespace.

The caller must keep the container idle until this function returns and remove it
on any exception. No host firewall table is changed. This requires Linux, a local
Docker daemon, and noninteractive sudo for stat/nsenter and both iptables tools.

Loopback remains available, including Docker's 127.0.0.11 DNS resolver. Resolving
a public name does not authorize connecting to its address. Established sessions
are preserved, so this must run before starting the agent, not on a live session.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import shlex
import socket
import subprocess
import sys
from collections.abc import Sequence
from typing import Any


class FirewallError(RuntimeError):
    """The container must not be used because egress isolation is unverified."""


_INSPECT_FORMAT = (
    '{"id":{{json .Id}},"pid":{{json .State.Pid}},'
    '"running":{{json .State.Running}},'
    '"network_mode":{{json .HostConfig.NetworkMode}},'
    '"privileged":{{json .HostConfig.Privileged}},'
    '"cap_drop":{{json .HostConfig.CapDrop}},'
    '"cap_add":{{json .HostConfig.CapAdd}},'
    '"security_opt":{{json .HostConfig.SecurityOpt}}}'
)
_TIMEOUT = 30
# Validate again *inside* the entered namespace before executing any firewall
# tool. This closes the PID-reuse race between the host check and nsenter. -c
# leaves stdin untouched for iptables-restore, and no shell is involved.
_NAMESPACE_EXEC_GUARD = (
    "import os,sys; "
    "actual=os.stat('/proc/self/ns/net').st_ino; "
    "expected=int(sys.argv[1]); "
    "sys.exit(125) if actual != expected else None; "
    "os.execvp(sys.argv[2], sys.argv[2:])"
)


def _run(args: list[str], *, purpose: str, input_text: str | None = None) -> str:
    try:
        result = subprocess.run(
            args, input=input_text, capture_output=True, text=True,
            timeout=_TIMEOUT, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise FirewallError(
            f"{purpose} failed ({type(exc).__name__}); no permissive fallback."
        ) from exc
    if result.returncode != 0:
        # Only fixed administrative commands run here. Avoid copying potentially
        # sensitive daemon diagnostics or complete command arguments into logs.
        hint = (
            " Noninteractive sudo -n permission and Linux namespace/firewall "
            "tools are required."
            if args[0] == "sudo" else " Check access to the local Docker daemon."
        )
        raise FirewallError(
            f"{purpose} failed (exit {result.returncode}).{hint} "
            "The task container must be removed; no permissive fallback."
        )
    return result.stdout


def _inspect_container(name: str) -> dict[str, Any]:
    raw = _run(
        ["docker", "inspect", "--type", "container", "--format", _INSPECT_FORMAT, name],
        purpose="Inspecting task-container isolation",
    )
    try:
        snapshot = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise FirewallError("Docker returned invalid isolation metadata.") from exc
    if not isinstance(snapshot, dict):
        raise FirewallError("Docker isolation metadata is not an object.")
    _validate_snapshot(snapshot)
    return snapshot


def _validate_snapshot(snapshot: dict[str, Any]) -> None:
    pid = snapshot.get("pid")
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        raise FirewallError("Refusing an absent or invalid task-container PID.")
    if snapshot.get("running") is not True:
        raise FirewallError("Refusing a task container that is not running.")
    mode = snapshot.get("network_mode")
    if not isinstance(mode, str) or not mode:
        raise FirewallError("Container network mode is missing.")
    if mode == "host" or mode.startswith("container:"):
        raise FirewallError("Refusing host or shared-container network namespaces.")
    if snapshot.get("privileged") is not False:
        raise FirewallError("A non-privileged task container is required.")
    caps = snapshot.get("cap_drop")
    if not isinstance(caps, list) or "ALL" not in {str(c).upper() for c in caps}:
        raise FirewallError("The task container must drop ALL capabilities.")
    if snapshot.get("cap_add") not in (None, []):
        raise FirewallError("Capabilities must not be added back to the task container.")
    opts = snapshot.get("security_opt")
    if not isinstance(opts, list):
        raise FirewallError("The task container must enable no-new-privileges.")
    no_new_privs = {str(x).lower() for x in opts}
    enabled = {"no-new-privileges", "no-new-privileges:true", "no-new-privileges=true"}
    disabled = {"no-new-privileges:false", "no-new-privileges=false"}
    if not no_new_privs.intersection(enabled) or no_new_privs.intersection(disabled):
        raise FirewallError("The task container must enable no-new-privileges.")
    if not isinstance(snapshot.get("id"), str) or not snapshot["id"]:
        raise FirewallError("The task-container identity is missing.")


def _namespace_inode(pid: int) -> int:
    value = _run(
        ["sudo", "-n", "stat", "--dereference", "--format=%i", f"/proc/{pid}/ns/net"],
        purpose="Inspecting task-container network namespace",
    ).strip()
    if not value.isdecimal() or int(value) <= 0:
        raise FirewallError("Unable to verify the task network namespace inode.")
    return int(value)


def _host_namespace_inodes() -> set[int]:
    try:
        current = os.stat("/proc/self/ns/net").st_ino
        try:
            init = os.stat("/proc/1/ns/net").st_ino
        except PermissionError:
            # Hardened procfs can hide root-owned namespace links from the
            # runner user. Retain the PID 1 check using the same read-only
            # noninteractive permission required for the task namespace.
            init = _namespace_inode(1)
        return {current, init}
    except OSError as exc:
        raise FirewallError("Unable to inspect host network namespace identity.") from exc


def _guard_namespace(
    name: str, expected: dict[str, Any], inode: int, host_inodes: set[int]
) -> None:
    current = _inspect_container(name)
    if current["id"] != expected["id"] or current["pid"] != expected["pid"]:
        raise FirewallError("Container identity/PID changed while applying network policy.")
    current_inode = _namespace_inode(current["pid"])
    if current_inode in host_inodes:
        raise FirewallError("Refusing to change a host network namespace.")
    if current_inode != inode:
        raise FirewallError("Task network namespace changed while applying policy.")


def _port(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 65535:
        raise FirewallError("An endpoint TCP port must be an integer from 1 to 65535.")
    return value


def _resolve(host: str, port: int) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    if (
        not isinstance(host, str) or not host or host != host.strip()
        or any(c in host for c in "/@?#%[]") or any(c.isspace() for c in host)
    ):
        raise FirewallError("An endpoint must be a plain hostname or unscoped IP address.")
    try:
        literal = ipaddress.ip_address(host)
        values = [literal]
    except ValueError:
        # A colon that was not an IPv6 address must not be interpreted as a URL,
        # credentials, or a hostname:port pair.
        if ":" in host:
            raise FirewallError("Endpoint host and port must be provided separately.")
        try:
            records = socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        except OSError as exc:
            raise FirewallError("Failed to resolve an explicitly permitted endpoint.") from exc
        try:
            values = [ipaddress.ip_address(r[4][0]) for r in records if r[0] in (socket.AF_INET, socket.AF_INET6)]
        except ValueError as exc:
            raise FirewallError("Endpoint resolution returned an invalid address.") from exc
    normalized = set()
    for address in values:
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
            address = address.ipv4_mapped
        if address.is_unspecified or address.is_multicast:
            raise FirewallError("Unspecified or multicast endpoint addresses are not permitted.")
        normalized.add(address)
    if not normalized:
        raise FirewallError("An explicitly permitted endpoint resolved to no usable addresses.")
    return sorted(normalized, key=lambda x: (x.version, int(x)))


def _rules(version: int, endpoints: set[tuple[str, int]]) -> str:
    lines = [
        "*filter", ":INPUT ACCEPT [0:0]", ":FORWARD DROP [0:0]", ":OUTPUT DROP [0:0]",
        "-A OUTPUT -o lo -j ACCEPT",
        "-A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT",
    ]
    for address, port in sorted(endpoints, key=lambda x: (int(ipaddress.ip_address(x[0])), x[1])):
        ip = ipaddress.ip_address(address)
        if ip.version != version:
            continue
        destination = f"{ip}/{32 if version == 4 else 128}"
        lines.append(f"-A OUTPUT -d {destination} -p tcp -m tcp --dport {port} -j ACCEPT")
    return "\n".join([*lines, "COMMIT", ""])


def _canonical_rules(text: str) -> tuple[dict[str, str], list[tuple[str, ...]]]:
    chains: dict[str, str] = {}
    rules: list[tuple[str, ...]] = []
    in_table = False
    committed = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line == "*filter" and not in_table and not committed:
            in_table = True
            continue
        if line == "COMMIT" and in_table:
            in_table = False
            committed = True
            continue
        if not in_table:
            raise FirewallError("Unexpected table/content in firewall verification.")
        match = re.fullmatch(r":(\S+) (\S+) \[\d+:\d+\]", line)
        if match:
            if match[1] in chains:
                raise FirewallError("Duplicate chain in firewall verification.")
            chains[match[1]] = match[2]
            continue
        try:
            parts = shlex.split(line)
            if parts[:2] != ["-A", "OUTPUT"]:
                raise FirewallError("Unexpected rule in firewall verification.")
            for i, part in enumerate(parts[:-1]):
                if part == "--ctstate":
                    parts[i + 1] = ",".join(sorted(parts[i + 1].split(",")))
                elif part == "-d":
                    parts[i + 1] = str(ipaddress.ip_network(parts[i + 1], strict=False))
            rules.append(tuple(parts))
        except (ValueError, IndexError) as exc:
            raise FirewallError("Invalid firewall rule returned during verification.") from exc
    if in_table or not committed:
        raise FirewallError("Incomplete firewall verification output.")
    return chains, rules


def _verify_rules(expected: str, actual: str) -> None:
    if _canonical_rules(expected) != _canonical_rules(actual):
        raise FirewallError("Installed network rules do not match the required default-deny policy.")


def apply_container_firewall(
    container_name: str,
    proxy_host: str,
    proxy_port: int,
    direct_tcp_endpoints: Sequence[tuple[str, int]] = (),
) -> dict[str, Any]:
    """Install and verify OUTPUT DROP in a fresh task container's netns.

    All validation, resolution, command, and verification errors raise
    FirewallError. The caller must remove the container, never start the agent
    after an error, and must not expose a Docker socket or grant NET_ADMIN.
    """
    if not sys.platform.startswith("linux"):
        raise FirewallError("Container namespace egress isolation requires Linux.")
    if not isinstance(container_name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", container_name):
        raise FirewallError("Invalid task-container name or ID.")
    proxy_port = _port(proxy_port)
    proxy_addresses = _resolve(proxy_host, proxy_port)
    endpoints = {(str(ip), proxy_port) for ip in proxy_addresses}
    direct_audit: list[dict[str, Any]] = []
    for endpoint in direct_tcp_endpoints:
        if not isinstance(endpoint, (tuple, list)) or len(endpoint) != 2:
            raise FirewallError("Each direct endpoint must be a (host, TCP port) pair.")
        host, port = endpoint
        port = _port(port)
        addresses = _resolve(host, port)
        endpoints.update((str(ip), port) for ip in addresses)
        direct_audit.append({"host": host, "port": port, "resolved_addresses": [str(ip) for ip in addresses]})
    snapshot = _inspect_container(container_name)
    host_inodes = _host_namespace_inodes()
    inode = _namespace_inode(snapshot["pid"])
    if inode in host_inodes:
        raise FirewallError("Refusing to change a host network namespace.")
    prefix = [
        "sudo", "-n", "nsenter", "--target", str(snapshot["pid"]), "--net", "--",
        sys.executable, "-I", "-c", _NAMESPACE_EXEC_GUARD, str(inode),
    ]
    families = [(4, "iptables"), (6, "ip6tables")]
    applied: dict[str, Any] = {}
    for version, executable in families:
        _guard_namespace(container_name, snapshot, inode, host_inodes)
        rules = _rules(version, endpoints)
        _run(prefix + [f"{executable}-restore", "--wait", "5"], purpose=f"Installing IPv{version} task egress policy", input_text=rules)
        applied[f"ipv{version}"] = {"requested_rules": rules}
    # Read back both families only after both installations, so a partial
    # success or an unexpected broad rule never returns an approval record.
    for version, executable in families:
        _guard_namespace(container_name, snapshot, inode, host_inodes)
        actual = _run(prefix + [f"{executable}-save", "--table", "filter"], purpose=f"Verifying IPv{version} task egress policy")
        _verify_rules(applied[f"ipv{version}"]["requested_rules"], actual)
        applied[f"ipv{version}"].update({"verified": True, "installed_rules": actual, "sha256": hashlib.sha256(actual.encode()).hexdigest()})
    _guard_namespace(container_name, snapshot, inode, host_inodes)
    return {
        "enforced": True, "container_name": container_name, "container_id": snapshot["id"],
        "pid": snapshot["pid"], "network_namespace_inode": inode,
        "network_mode": snapshot["network_mode"], "output_policy": "DROP",
        "proxy": {"host": proxy_host, "port": proxy_port, "resolved_addresses": [str(ip) for ip in proxy_addresses]},
        "direct_tcp_endpoints": direct_audit, "families": applied,
        "dns_note": "Loopback, including Docker DNS at 127.0.0.11, remains usable; DNS resolution alone never permits a public TCP/UDP connection.",
        "scope_note": "Only this task netns filter tables were replaced. INPUT is ACCEPT for runner/runtime ingress; FORWARD and OUTPUT default DROP. Agent must start only after this verification.",
    }

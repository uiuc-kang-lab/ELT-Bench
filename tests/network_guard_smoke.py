#!/usr/bin/env python3
"""Real, opt-in network isolation smoke using only local controlled services.

Run from the repository with an existing image and bridge network::

    python tests/network_guard_smoke.py --report /tmp/elt-network-smoke.json

Creates only a random ``elt-network-smoke-*`` container, never pulls images,
and deletes that container before stopping its host-owned proxy. Requires the
same Docker and noninteractive sudo permissions as the restricted runner.
No real API, warehouse, public download, or existing container is contacted.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import os
from pathlib import Path
import shutil
import socket
import socketserver
import ssl
import subprocess
import sys
import tempfile
import threading
import uuid


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agents.common.network_guard import ContainerNetworkGuard
from agents.common.network_policy import NetworkPolicy


CLIENT = r'''
import http.client, json, os, socket, ssl, sys, urllib.error, urllib.request
from urllib.parse import urlsplit

c = json.loads(sys.argv[1])
results = []
def record(name, passed, **evidence):
    results.append(dict(name=name, passed=bool(passed), **evidence))

def request(name, url, expected, data=None, opener=None):
    try:
        if opener is None:
            opener = urllib.request.build_opener(
                urllib.request.HTTPSHandler(context=ssl._create_unverified_context()))
        with opener.open(urllib.request.Request(url, data=data), timeout=4) as r:
            status, body = r.status, r.read(1024)
        record(name, status == expected and body == (data or b"allowed"),
               status=status, body=body.decode("ascii", "replace"))
    except urllib.error.HTTPError as e:
        record(name, e.code == expected, status=e.code)
    except Exception as e:
        # CONNECT denial is wrapped in URLError rather than HTTPError.
        cause = getattr(e, "reason", e)
        denied = "403" in str(cause)
        record(name, expected == 403 and denied, error_type=type(e).__name__,
               proxy_returned_403=denied)

base = "http://%s:%s" % (c["gateway"], c["allowed_port"])
denied = "http://%s:%s/blocked" % (c["gateway"], c["denied_port"])
request("allowed_http_get", base + "/ok", 200)
request("allowed_http_post", base + "/post", 200, b"smoke-post-body")
request("denied_http_endpoint", denied, 403)
request("redirect_to_denied_endpoint", base + "/redirect", 403)
request("github_rejected_at_proxy", "https://github.com/", 403)
request("huggingface_rejected_at_proxy", "https://huggingface.co/", 403)

proxy = urlsplit(c["proxy_url"])
connection = http.client.HTTPConnection(proxy.hostname, proxy.port, timeout=4)
try:
    connection.request("GET", base + "/ok", headers={"Host": "forbidden.invalid"})
    response = connection.getresponse()
    record("spoofed_host_rejected", response.status == 400, status=response.status)
    response.read()
except Exception as e:
    record("spoofed_host_rejected", False, error_type=type(e).__name__)
finally:
    connection.close()

with socket.create_connection((c["gateway"], c["echo_port"]), timeout=3) as s:
    s.sendall(b"native-tcp-smoke")
    reply = s.recv(1024)
record("explicit_native_tcp_allowed", reply == b"native-tcp-smoke")

if c["tls_port"]:
    request("allowed_https_get", "https://%s:%s/ok" % (c["gateway"], c["tls_port"]), 200)
    tunnel = http.client.HTTPConnection(proxy.hostname, proxy.port, timeout=4)
    established = False
    try:
        tunnel.set_tunnel(c["gateway"], c["tls_port"])
        tunnel.connect()
        established = True
        # An allowed CONNECT IP must not permit a different TLS SNI authority.
        with ssl._create_unverified_context().wrap_socket(
                tunnel.sock, server_hostname="forbidden.invalid") as tls:
            tls.sendall(b"GET /ok HTTP/1.0\r\n\r\n")
            reply = tls.recv(1024)
        record("different_tls_sni_rejected", not reply)
    except (ssl.SSLError, ConnectionError, OSError) as e:
        record("different_tls_sni_rejected", established, error_type=type(e).__name__,
               connect_was_accepted=established)
    finally:
        tunnel.close()

status = {}
for line in open("/proc/self/status"):
    key, _, value = line.partition(":")
    if key in ("CapEff", "CapPrm", "CapBnd", "NoNewPrivs"):
        status[key] = value.strip()
record("agent_has_no_capabilities", all(int(status[k], 16) == 0 for k in ("CapEff", "CapPrm", "CapBnd")), **status)
record("agent_has_no_new_privileges", status["NoNewPrivs"] == "1")
try:
    raw = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    raw.close()
    record("raw_packet_socket_denied", False)
except PermissionError:
    record("raw_packet_socket_denied", True)

for key in list(os.environ):
    if key.lower() in ("http_proxy", "https_proxy", "all_proxy", "no_proxy"):
        del os.environ[key]

def direct_request(name, url, no_proxy_star=False):
    if no_proxy_star:
        os.environ["NO_PROXY"] = "*"
        os.environ["no_proxy"] = "*"
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url, timeout=0.7) as r:
            r.read(64)
        record(name, False)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        record(name, True, error_type=type(e).__name__)

direct_request("unset_proxy_direct_denied_http_blocked", denied)
direct_request("unset_proxy_direct_allowed_http_blocked", base + "/ok")
direct_request("no_proxy_star_cannot_bypass", denied, True)
for label, port in (("denied", c["denied_port"]), ("allowed", c["allowed_port"])):
    try:
        with socket.create_connection((c["gateway"], port), timeout=0.7):
            pass
        record("raw_tcp_direct_%s_ip_blocked" % label, False)
    except (TimeoutError, OSError) as e:
        record("raw_tcp_direct_%s_ip_blocked" % label, True, error_type=type(e).__name__)

print(json.dumps(results))
'''


def run(args: list[str], *, input_text: str | None = None, timeout: int = 30) -> str:
    result = subprocess.run(args, input=input_text, text=True, capture_output=True, timeout=timeout)
    if result.returncode:
        # Do not copy arbitrary Docker or sudo diagnostics into the report.
        raise RuntimeError(f"{Path(args[0]).name} command failed (exit {result.returncode})")
    return result.stdout


class ServiceHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args):
        pass

    def do_GET(self):
        self.server.observations.append({"method": "GET", "path": self.path})
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", self.server.redirect_to)
            body = b""
        else:
            self.send_response(200)
            body = b"allowed"
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self.server.observations.append({"method": "POST", "path": self.path, "bytes": len(body)})
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class EchoHandler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(3)
        data = self.request.recv(1024)
        self.request.sendall(data)


class EchoServer(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


def start_service(server, services):
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    services.append((server, thread))
    return server.server_address[1]


def http_service(gateway, services, tls_context=None):
    server = ThreadingHTTPServer((gateway, 0), ServiceHandler)
    server.daemon_threads = True
    server.observations = []
    server.redirect_to = ""
    if tls_context:
        server.socket = tls_context.wrap_socket(server.socket, server_side=True)
    return server, start_service(server, services)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--network", default="elt-docker_elt_network")
    parser.add_argument("--image", default="python:3.11-slim")
    args = parser.parse_args()
    name = "elt-network-smoke-" + uuid.uuid4().hex[:16]
    report = {
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "container_name": name, "network": args.network, "image": args.image,
        "passed": False, "checks": [], "cleanup": {},
        "limits": [
            "Controlled local endpoints only; no real model API or warehouse tested.",
            "GitHub and Hugging Face requests must be denied at the local proxy before upstream connection.",
            "IPv6 enforcement is established by actual installed-rule readback; the Docker bridge need not have IPv6 routing.",
        ],
    }
    guard = None
    services = []
    created = False
    temporary = tempfile.TemporaryDirectory(prefix="elt-network-smoke-")
    temp = Path(temporary.name)
    try:
        report["image_id"] = run(["docker", "image", "inspect", "--format", "{{.Id}}", args.image]).strip()
        info = json.loads(run(["docker", "network", "inspect", args.network]))[0]
        if info.get("Driver") != "bridge":
            raise RuntimeError("Smoke requires an existing Docker bridge network")
        gateway = next(item["Gateway"] for item in info["IPAM"]["Config"]
                       if item.get("Gateway") and ipaddress.ip_address(item["Gateway"]).version == 4)
        report["gateway"] = gateway
        report["host_network_namespace_inode"] = os.stat("/proc/self/ns/net").st_ino
        deny_server, deny_port = http_service(gateway, services)
        allow_server, allow_port = http_service(gateway, services)
        allow_server.redirect_to = f"http://{gateway}:{deny_port}/blocked"
        echo_server = EchoServer((gateway, 0), EchoHandler)
        echo_port = start_service(echo_server, services)

        # Demonstrate the denied service exists before evaluating blocked egress.
        with socket.create_connection((gateway, deny_port), timeout=3) as control:
            control.sendall(b"GET /host-control HTTP/1.0\r\n\r\n")
            response = control.recv(1024)
        if b"200" not in response.split(b"\r\n", 1)[0]:
            raise RuntimeError("Controlled denied service did not respond to the host")
        report["host_control_denied_service_reachable"] = True
        deny_server.observations.clear()

        tls_port = None
        tls_server = None
        if shutil.which("openssl"):
            run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                 "-subj", "/CN=network-smoke.invalid", "-keyout", str(temp / "key.pem"),
                 "-out", str(temp / "cert.pem")])
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(temp / "cert.pem", temp / "key.pem")
            tls_server, tls_port = http_service(gateway, services, context)
        else:
            report["tls_skipped"] = "Local openssl command unavailable; no certificate downloaded"
        policy = NetworkPolicy(
            http_endpoints=[(gateway, allow_port)] + ([(gateway, tls_port)] if tls_port else []),
            direct_tcp_endpoints=[(gateway, echo_port)],
            notes=["Synthetic smoke endpoints; no existing service permissions"],
        )
        guard = ContainerNetworkGuard(policy, args.network, temp / "guard-audit.json")
        guard.start()
        command = ["docker", "run", "--detach", "--rm", "--pull=never", "--name", name,
                   "--network", args.network, *guard.docker_security_args]
        for key, value in guard.environment.items():
            command.extend(["--env", f"{key}={value}"])
        command.extend(["--entrypoint", "sleep", args.image, "infinity"])
        run(command)
        created = True
        guard.install(name)
        config = {"gateway": gateway, "allowed_port": allow_port, "denied_port": deny_port,
                  "echo_port": echo_port, "tls_port": tls_port, "proxy_url": guard.proxy_url}
        output = run(["docker", "exec", "--interactive", name, "python", "-", json.dumps(config)],
                     input_text=CLIENT, timeout=60)
        report["checks"] = json.loads(output)
        for version in (4, 6):
            family = guard.firewall["families"][f"ipv{version}"]
            report["checks"].append({
                "name": f"ipv{version}_default_drop_verified",
                "passed": family["verified"] and ":OUTPUT DROP" in family["installed_rules"],
                "installed_rules_sha256": family["sha256"],
            })
        events = list(guard.proxy.events)
        for host in ("github.com", "huggingface.co"):
            matches = [e for e in events if e.get("host") == host]
            report["checks"].append({
                "name": f"{host}_never_opened_upstream",
                "passed": bool(matches) and all(not e["allowed"] for e in matches),
                "events": matches,
            })
        if tls_port:
            report["checks"].append({
                "name": "tls_sni_rejection_recorded",
                "passed": any(e.get("result") == "tls_hello_rejected" for e in events),
            })
        report["service_observations"] = {
            "allowed_http": allow_server.observations,
            "denied_http": deny_server.observations,
            "allowed_https": tls_server.observations if tls_server else [],
        }
        report["checks"].append({"name": "denied_service_received_no_container_requests",
                                  "passed": not deny_server.observations})
        report["passed"] = all(check["passed"] for check in report["checks"])
    except Exception as exc:
        report["error"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        # Only our exact random name is eligible for removal, even after partial
        # docker-run failure. Never select by prefix or enumerate other containers.
        assert name.startswith("elt-network-smoke-")
        try:
            def container_exists():
                names = run(["docker", "ps", "--all", "--filter", f"name=^/{name}$",
                             "--format", "{{.Names}}"], timeout=15).splitlines()
                if any(found != name for found in names):
                    raise RuntimeError("Exact-name cleanup filter returned a different container")
                return bool(names)

            exists = container_exists()
            if exists:
                run(["docker", "rm", "--force", name])
            # A daemon error must not be mistaken for confirmed removal.
            report["cleanup"]["container_removed"] = not container_exists()
            report["cleanup"]["container_was_started"] = created
        except Exception as exc:
            report["cleanup"]["container_removed"] = False
            report["cleanup"]["error_type"] = type(exc).__name__
        if guard:
            try:
                guard.close()
                report["guard"] = guard.manifest()
                report["cleanup"]["proxy_stopped"] = True
            except Exception as exc:
                report["cleanup"]["proxy_stopped"] = False
                report["cleanup"]["proxy_error_type"] = type(exc).__name__
        for server, thread in services:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
        report["cleanup"]["controlled_services_stopped"] = all(not thread.is_alive() for _, thread in services)
        temporary.cleanup()
        report["cleanup"]["temporary_certificate_removed"] = not temp.exists()
        report["passed"] = report["passed"] and all(
            report["cleanup"].get(key, True) for key in
            ("container_removed", "proxy_stopped", "controlled_services_stopped", "temporary_certificate_removed"))
        report["source_sha256"] = {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in [Path(__file__), ROOT / "agents/common/network_guard.py",
                         ROOT / "agents/common/network_firewall.py", ROOT / "agents/common/network_proxy.py",
                         ROOT / "agents/common/network_policy.py"]
        }
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": report["passed"], "checks": len(report["checks"]),
                      "failed_checks": [c["name"] for c in report["checks"] if not c["passed"]],
                      "error": report.get("error"), "cleanup": report["cleanup"],
                      "report": str(args.report)}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Opt-in real startup checks for the restricted Claude/OpenHands containers.

Executes the current runner startup functions, extracted by AST so importing
this test cannot import SDKs, open task configs, or initialize a real task.
Only already-present images, empty temporary workspaces, random smoke container
names, and synthetic session credentials are used. No LLM or warehouse call.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
from typing import Any
import urllib.error
import urllib.request
import uuid


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agents.common.network_guard import ContainerNetworkGuard
from agents.common.network_policy import NetworkPolicy


def docker(args, *, check=True):
    result = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=30)
    if check and result.returncode:
        raise RuntimeError("Docker smoke administration failed")
    return result


def exists(name):
    names = docker(["ps", "--all", "--filter", f"name=^/{name}$", "--format", "{{.Names}}"]).stdout.splitlines()
    if any(found != name for found in names):
        raise RuntimeError("Smoke cleanup filter did not match the exact container name")
    return bool(names)


def load_startup(path: Path, image: str, network: str):
    tree = ast.parse(path.read_text())
    functions = {"ensure_container", "_run", "_workspace_mounts", "_wait_for_agent_server"}
    constants = {"IMAGE_NAME", "NETWORK_NAME", "CONTAINER_HOME", "CONTAINER_WORKDIR",
                 "AUTH_ENV", "CONTAINER_ENV_PASSTHROUGH", "CONTAINER_ENV_FIXED",
                 "AGENT_SERVER_READY_TIMEOUT_SEC"}
    selected = [ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)]
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in functions:
            selected.append(node)
        elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in constants for t in node.targets):
            selected.append(node)
    selected_tree = ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[]))
    # Do not copy any model, warehouse, cloud, or operator-proxy credentials
    # into the workload. Docker still needs its normal CLI binary/config path.
    safe_env = {key: os.environ[key] for key in ("PATH", "HOME", "LANG", "LC_ALL") if key in os.environ}
    safe_env.update({"NO_PROXY": "localhost,127.0.0.1,::1", "no_proxy": "localhost,127.0.0.1,::1"})

    def safe_run(command, **kwargs):
        command = list(command)
        if command[:2] == ["docker", "run"]:
            # Extra smoke-only safety: an image disappearance cannot cause a pull.
            command.insert(2, "--pull=never")
            name = command[command.index("--name") + 1]
            if not name.startswith("elt-network-smoke-"):
                raise RuntimeError("Refusing to create a non-smoke container")
        elif command[:2] in (["docker", "rm"], ["docker", "exec"]):
            if not any(token.startswith("elt-network-smoke-") for token in command[2:]):
                raise RuntimeError("Refusing to mutate a non-smoke container")
        kwargs.setdefault("env", safe_env)
        kwargs.setdefault("timeout", 45)
        return subprocess.run(command, **kwargs)

    logger = logging.Logger("isolated-runner-network-smoke")
    logger.addHandler(logging.NullHandler())
    direct_urlopen = urllib.request.build_opener(urllib.request.ProxyHandler({})).open
    namespace = {
        "Path": Path, "Any": Any, "ContainerNetworkGuard": ContainerNetworkGuard,
        "os": SimpleNamespace(environ=safe_env, getuid=os.getuid, getgid=os.getgid),
        "subprocess": SimpleNamespace(run=safe_run, CompletedProcess=subprocess.CompletedProcess),
        "logger": logger, "time": time,
        "urllib": SimpleNamespace(error=urllib.error, request=SimpleNamespace(urlopen=direct_urlopen)),
    }
    exec(compile(selected_tree, str(path), "exec"), namespace)
    namespace["NETWORK_NAME"] = network
    return namespace, {
        "source": str(path.relative_to(ROOT)),
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "functions": sorted(node.name for node in selected if isinstance(node, ast.FunctionDef)),
        "smoke_only_overrides": ["No credentials inherited", "docker run --pull=never", "Host readiness request bypasses operator proxies"],
    }


RUNTIME_PROBE = r'''
import json, os, pathlib, pwd
status = {}
for line in open('/proc/self/status'):
    k, _, v = line.partition(':')
    if k in ('CapEff','CapBnd','NoNewPrivs'):
        status[k] = v.strip()
home = pathlib.Path(os.environ['HOME'])
marker = home / 'network-smoke-write'
marker.write_text('smoke')
marker.unlink()
task_marker = pathlib.Path('/workspace/elt/network-smoke-write')
task_marker.write_text('smoke')
task_marker.unlink()
print(json.dumps({'uid':os.getuid(), 'gid':os.getgid(), 'home':str(home),
                  'home_owner':home.stat().st_uid, 'home_writable':True,
                  'elt_writable':True, 'passwd_lookup':pwd.getpwuid(os.getuid()).pw_name,
                  'status':status}))
'''


def run_one(kind, image, network, temporary_root):
    name = "elt-network-smoke-" + kind + "-" + uuid.uuid4().hex[:12]
    result = {"runner": kind, "container_name": name, "image": image, "passed": False, "checks": [], "cleanup": {}}
    guard = None
    taskdir = temporary_root / kind
    (taskdir / "elt").mkdir(parents=True)
    try:
        result["image_id"] = docker(["image", "inspect", "--format", "{{.Id}}", image]).stdout.strip()
        path = ROOT / ("agents/openhands/run.py" if kind == "openhands" else "agents/claude_agent/run.py")
        startup, result["startup_source"] = load_startup(path, image, network)
        guard = ContainerNetworkGuard(NetworkPolicy([], [], ["Empty startup-smoke policy"]), network, taskdir / "guard.json")
        if kind == "openhands":
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
            startup["ensure_container"](name, taskdir, port, secrets.token_hex(24),
                env_extra={"DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1"}, image=image, network_guard=guard)
            result["checks"].append({"name": "actual_agent_server_ready", "passed": True})
        else:
            startup["ensure_container"](name, taskdir, image=image, network_guard=guard)
            version = docker(["exec", name, "claude", "--version"]).stdout.strip()
            result["cli_version"] = version
            result["checks"].append({"name": "actual_claude_cli_version", "passed": bool(version)})
        probe = subprocess.run(["docker", "exec", "--interactive", name, "python", "-"], input=RUNTIME_PROBE,
                               capture_output=True, text=True, timeout=30)
        if probe.returncode:
            raise RuntimeError("Unprivileged runtime probe failed")
        runtime = json.loads(probe.stdout)
        result["runtime"] = runtime
        result["checks"].extend([
            {"name": "host_user_and_owned_writable_home", "passed": runtime["uid"] == os.getuid() == runtime["home_owner"] and runtime["home_writable"]},
            {"name": "task_elt_writable", "passed": runtime["elt_writable"]},
            {"name": "capabilities_dropped", "passed": int(runtime["status"]["CapEff"], 16) == int(runtime["status"]["CapBnd"], 16) == 0},
            {"name": "no_new_privileges", "passed": runtime["status"]["NoNewPrivs"] == "1"},
            {"name": "both_firewall_families_enforced", "passed": guard.status == "enforced" and all(guard.firewall["families"][f"ipv{v}"]["verified"] for v in (4,6))},
        ])
        result["passed"] = all(check["passed"] for check in result["checks"])
    except Exception as exc:
        # subprocess errors can include command args; a type and return code
        # identify this test failure without exposing any environment values.
        result["error"] = {"type": type(exc).__name__, "returncode": getattr(exc, "returncode", None)}
        if isinstance(exc, RuntimeError):
            result["error"]["message"] = str(exc)
    finally:
        assert name.startswith("elt-network-smoke-")
        try:
            if exists(name):
                docker(["rm", "--force", name])
            result["cleanup"]["container_removed"] = not exists(name)
        except Exception:
            result["cleanup"]["container_removed"] = False
        if guard:
            try:
                guard.close()
                result["guard"] = guard.manifest()
                result["cleanup"]["proxy_stopped"] = True
            except Exception:
                result["cleanup"]["proxy_stopped"] = False
        result["passed"] = result["passed"] and all(result["cleanup"].values())
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--network", default="elt-docker_elt_network")
    parser.add_argument("--openhands-image", default="elt-swe-openhands:latest")
    parser.add_argument("--claude-image", default="elt-swe-claude:latest")
    args = parser.parse_args()
    report = {"started_at_utc": datetime.now(timezone.utc).isoformat(), "results": [],
              "scope": "Actual current ensure_container functions only; no task, LLM, warehouse or real credentials."}
    with tempfile.TemporaryDirectory(prefix="elt-network-smoke-runner-") as temp:
        for kind, image in (("claude", args.claude_image), ("openhands", args.openhands_image)):
            result = run_one(kind, image, args.network, Path(temp))
            report["results"].append(result)
            print(json.dumps({"runner": kind, "passed": result["passed"], "error": result.get("error"), "cleanup": result["cleanup"]}), flush=True)
    report["temporary_workspaces_removed"] = not Path(temp).exists()
    report["passed"] = all(result["passed"] for result in report["results"]) and report["temporary_workspaces_removed"]
    report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    report["source_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": report["passed"], "report": str(args.report)}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

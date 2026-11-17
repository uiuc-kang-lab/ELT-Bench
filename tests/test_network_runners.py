"""Test real runner launch functions without importing their agent SDKs.

Only selected AST definitions and literal configuration are loaded. Every
Docker command, readiness probe, and network guard operation is mocked.
"""

from __future__ import annotations

import argparse
import ast
import logging
import os
from pathlib import Path
import subprocess
import sys
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents"))
from common.network_guard import add_network_arguments  # noqa: E402


RUNNERS = ("claude_agent", "openhands")


def load_runner_functions(runner):
    """Compile the actual launch/parser code, excluding SDK imports and main."""
    source_path = ROOT / "agents" / runner / "run.py"
    tree = ast.parse(source_path.read_text(), filename=str(source_path))
    names = {
        "IMAGE_NAME", "NETWORK_NAME", "CONTAINER_WORKDIR", "CONTAINER_HOME",
        "AUTH_ENV", "CONTAINER_ENV_PASSTHROUGH", "CONTAINER_ENV_FIXED",
        "AGENT_SERVER_READY_TIMEOUT_SEC",
    }
    functions = {"ensure_container", "_workspace_mounts", "_parse_shard", "parse_args"}
    selected = [ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)]
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in functions:
            selected.append(node)
        elif isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id in names for target in node.targets):
            selected.append(node)
    namespace = {
        "__name__": "isolated_network_runner",
        "Path": Path,
        "os": os,
        "argparse": argparse,
        "AGENT_DIR": source_path.parent,
        "logger": logging.getLogger("network-runner-test"),
        "destination_choices": lambda: ("snowflake", "databricks", "redshift"),
        "add_network_arguments": add_network_arguments,
    }
    code = compile(ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[])), str(source_path), "exec")
    exec(code, namespace)
    return namespace


class RunnerArgumentsTests(unittest.TestCase):
    def parse(self, runner, args):
        namespace = load_runner_functions(runner)
        with patch.object(sys, "argv", ["run.py", *args]):
            return namespace["parse_args"](), namespace["IMAGE_NAME"]

    def test_default_is_restricted_with_prepared_image(self):
        for runner in RUNNERS:
            with self.subTest(runner=runner):
                args, base_image = self.parse(runner, [])
                self.assertEqual(args.network_access, "restricted")
                self.assertEqual(args.image, base_image + ":restricted")
                self.assertEqual(args.network_allow, [])

    def test_explicit_unrestricted_selects_original_image(self):
        for runner in RUNNERS:
            with self.subTest(runner=runner):
                args, base_image = self.parse(runner, ["--network-access", "unrestricted"])
                self.assertEqual(args.network_access, "unrestricted")
                self.assertEqual(args.image, base_image)

    def test_explicit_image_is_preserved_in_both_modes(self):
        for runner in RUNNERS:
            for mode in ("restricted", "unrestricted"):
                with self.subTest(runner=runner, mode=mode):
                    args, _ = self.parse(runner, ["--network-access", mode, "--image", "operator:prepared", "--network-allow", "api.example.test:443"])
                    self.assertEqual(args.image, "operator:prepared")
                    self.assertEqual(args.network_allow, ["api.example.test:443"])


class ContainerStartupTests(unittest.TestCase):
    def harness(self, runner, *, fail_install=False, fail_start=False):
        namespace = load_runner_functions(runner)
        events = []
        commands = []

        def run(command, **kwargs):
            commands.append((command, kwargs))
            events.append(("docker", command))
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        def start():
            events.append(("guard_start", None))
            if fail_start:
                raise RuntimeError("proxy initialization failed")

        def install(container):
            events.append(("guard_install", container))
            if fail_install:
                raise RuntimeError("firewall installation failed")

        guard = types.SimpleNamespace(
            start=Mock(side_effect=start),
            install=Mock(side_effect=install),
            docker_security_args=["--cap-drop=ALL", "--security-opt=no-new-privileges:true"],
            environment={
                "HTTP_PROXY": "http://guard.test:8080",
                "HTTPS_PROXY": "http://guard.test:8080",
                "http_proxy": "http://guard.test:8080",
                "https_proxy": "http://guard.test:8080",
                "ALL_PROXY": "", "all_proxy": "",
                "NO_PROXY": "localhost,127.0.0.1,::1",
                "no_proxy": "localhost,127.0.0.1,::1",
            },
        )
        namespace["_run"] = Mock(side_effect=run)
        namespace["_wait_for_agent_server"] = Mock(side_effect=lambda *args: events.append(("wait", args)))
        return namespace, guard, events, commands

    @staticmethod
    def invoke(namespace, runner, guard, **kwargs):
        arguments = {"image": "local:prepared", "network_guard": guard, **kwargs}
        if runner == "openhands":
            arguments.update(port=19080, session_key="test-session-key")
        return namespace["ensure_container"]("test-task", Path("/tmp/test-input"), **arguments)

    @staticmethod
    def server_start(command):
        return command[:2] == ["docker", "exec"] and any("openhands.agent_server" in arg for arg in command)

    def test_openhands_firewall_precedes_server_start_and_readiness(self):
        namespace, guard, events, commands = self.harness("openhands")
        self.invoke(namespace, "openhands", guard)
        install_at = next(i for i, event in enumerate(events) if event[0] == "guard_install")
        server_at = next(i for i, event in enumerate(events) if event[0] == "docker" and self.server_start(event[1]))
        wait_at = next(i for i, event in enumerate(events) if event[0] == "wait")
        self.assertLess(install_at, server_at)
        self.assertLess(server_at, wait_at)
        guard.install.assert_called_once_with("test-task")
        docker_run = next(command for command, _ in commands if command[:2] == ["docker", "run"])
        self.assertEqual(docker_run[-2:], ["sleep", "infinity"])

    def test_openhands_install_failure_prevents_server_start(self):
        namespace, guard, events, commands = self.harness("openhands", fail_install=True)
        with self.assertRaisesRegex(RuntimeError, "firewall installation failed"):
            self.invoke(namespace, "openhands", guard)
        self.assertFalse(any(self.server_start(command) for command, _ in commands))
        namespace["_wait_for_agent_server"].assert_not_called()

    def test_claude_install_failure_propagates_without_success(self):
        namespace, guard, events, commands = self.harness("claude_agent", fail_install=True)
        with self.assertRaisesRegex(RuntimeError, "firewall installation failed"):
            self.invoke(namespace, "claude_agent", guard)
        self.assertEqual(events[-1], ("guard_install", "test-task"))
        self.assertFalse(any(any("docker_claude" in arg for arg in command) for command, _ in commands))

    def test_guard_start_failure_prevents_container_creation(self):
        for runner in RUNNERS:
            with self.subTest(runner=runner):
                namespace, guard, _, commands = self.harness(runner, fail_start=True)
                with self.assertRaisesRegex(RuntimeError, "proxy initialization failed"):
                    self.invoke(namespace, runner, guard)
                self.assertFalse(any(command[:2] == ["docker", "run"] for command, _ in commands))
                guard.install.assert_not_called()

    def test_both_runners_apply_capability_and_privilege_restrictions(self):
        for runner in RUNNERS:
            with self.subTest(runner=runner):
                namespace, guard, events, commands = self.harness(runner)
                self.invoke(namespace, runner, guard)
                docker_run = next(command for command, _ in commands if command[:2] == ["docker", "run"])
                self.assertIn("--cap-drop=ALL", docker_run)
                self.assertIn("--security-opt=no-new-privileges:true", docker_run)
                self.assertNotIn("--privileged", docker_run)
                self.assertNotIn("--cap-add", docker_run)
                self.assertEqual(docker_run[docker_run.index("--user") + 1], f"{os.getuid()}:{os.getgid()}")
                self.assertLess(next(i for i, e in enumerate(events) if e[0] == "guard_start"), next(i for i, e in enumerate(events) if e[0] == "docker" and e[1][:2] == ["docker", "run"]))

    def test_openhands_empty_all_proxy_overrides_host_and_env_extra(self):
        namespace, guard, _, commands = self.harness("openhands")
        hostile = {key: "http://unapproved.test:8080" for key in guard.environment}
        with patch.dict(os.environ, hostile, clear=True):
            self.invoke(namespace, "openhands", guard, env_extra={**hostile, "LLM_API_KEY": "fixture-key"})
        docker_run, kwargs = next((command, kwargs) for command, kwargs in commands if command[:2] == ["docker", "run"])
        for key, value in guard.environment.items():
            self.assertEqual(kwargs["env"][key], value)
            self.assertIn(key, [docker_run[i + 1] for i, arg in enumerate(docker_run[:-1]) if arg == "-e"])
        self.assertEqual(kwargs["env"]["LLM_API_KEY"], "fixture-key")
        self.assertNotIn("fixture-key", " ".join(docker_run))
        self.assertNotIn("test-session-key", " ".join(docker_run))

    def test_claude_fixed_proxy_values_override_inherited_values(self):
        namespace, guard, _, commands = self.harness("claude_agent")
        hostile = {key: "http://unapproved.test:8080" for key in guard.environment}
        with patch.dict(os.environ, hostile, clear=True):
            self.invoke(namespace, "claude_agent", guard)
        docker_run = next(command for command, _ in commands if command[:2] == ["docker", "run"])
        assignments = [docker_run[i + 1] for i, arg in enumerate(docker_run[:-1]) if arg == "-e"]
        for key, value in guard.environment.items():
            matching = [item for item in assignments if item == key or item.startswith(key + "=")]
            self.assertEqual(matching[-1], f"{key}={value}")
        self.assertNotIn("unapproved.test", " ".join(docker_run))


if __name__ == "__main__":
    unittest.main()

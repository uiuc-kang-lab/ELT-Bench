"""Network-guard lifecycle tests using fake Docker metadata and no sockets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents"))
from common import network_guard as guard_module  # noqa: E402
from common.network_firewall import FirewallError  # noqa: E402
from common.network_policy import NetworkPolicy  # noqa: E402


class PolicyIdentityTests(unittest.TestCase):
    def test_default_cli_mode_is_restricted(self):
        parser = argparse.ArgumentParser()
        guard_module.add_network_arguments(parser)
        self.assertEqual(parser.parse_args([]).network_access, "restricted")
        args = parser.parse_args(["--network-allow", "first.test:443", "--network-allow", "second.test:80"])
        self.assertEqual(args.network_allow, ["first.test:443", "second.test:80"])

    def test_legacy_result_is_not_reused_as_restricted(self):
        with self.assertRaisesRegex(RuntimeError, "different or unknown network"):
            guard_module.require_matching_network_policy({"finished": True, "status": "success"}, "restricted")

    def test_legacy_result_requires_explicit_unrestricted_mode(self):
        guard_module.require_matching_network_policy({"finished": True}, "unrestricted")

    def test_mode_or_extra_endpoint_change_requires_rerun(self):
        saved = {"network_access": guard_module.policy_identity("restricted", ("one.test:443",))}
        guard_module.require_matching_network_policy(saved, "restricted", ("one.test:443",))
        for mode, endpoints in [("unrestricted", ("one.test:443",)), ("restricted", ()), ("restricted", ("two.test:443",))]:
            with self.subTest(mode=mode, endpoints=endpoints), self.assertRaises(RuntimeError):
                guard_module.require_matching_network_policy(saved, mode, endpoints)

    def test_extra_endpoint_order_and_duplicates_do_not_change_identity(self):
        a = guard_module.policy_identity("restricted", ("one.test:443", "two.test:443", "one.test:443"))
        b = guard_module.policy_identity("restricted", ("two.test:443", "one.test:443"))
        self.assertEqual(a, b)
        self.assertNotIn("one.test", json.dumps(a))


class OfflineDependencyTests(unittest.TestCase):
    def test_missing_image_fails_before_any_container_starts(self):
        with patch.object(guard_module, "_docker_json", side_effect=subprocess.CalledProcessError(1, "docker", stderr="private diagnostic")) as inspect, patch.object(guard_module.subprocess, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "unavailable locally") as ctx:
                guard_module.check_offline_dependencies("prepared:restricted")
            inspect.assert_called_once_with("image", "inspect", "prepared:restricted")
            run.assert_not_called()
            self.assertNotIn("private diagnostic", str(ctx.exception))

    def test_missing_mirror_fails_in_disconnected_probe(self):
        with patch.object(guard_module, "_docker_json", return_value=[{"Id": "image-id"}]), patch.object(guard_module.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "docker", stderr="private diagnostic")) as run:
            with self.assertRaisesRegex(RuntimeError, "offline Terraform mirror") as ctx:
                guard_module.check_offline_dependencies("prepared:restricted")
            command = run.call_args.args[0]
            self.assertEqual(command[command.index("--network") + 1], "none")
            self.assertIn("--cap-drop=ALL", command)
            self.assertIn("--security-opt=no-new-privileges:true", command)
            self.assertEqual(command[command.index("--entrypoint") + 1], "python")
            self.assertEqual(run.call_args.kwargs["timeout"], 30)
            self.assertNotIn("private diagnostic", str(ctx.exception))

    def test_transform_only_requires_local_image_but_skips_mirror_probe(self):
        with patch.object(guard_module, "_docker_json", return_value=[{"Id": "image-id"}]) as inspect, patch.object(guard_module.subprocess, "run") as run:
            guard_module.check_offline_dependencies("existing:latest", transform_only=True)
            inspect.assert_called_once_with("image", "inspect", "existing:latest")
            run.assert_not_called()

    def test_probe_timeout_fails_closed(self):
        with patch.object(guard_module, "_docker_json", return_value=[{"Id": "image-id"}]), patch.object(guard_module.subprocess, "run", side_effect=subprocess.TimeoutExpired("docker", 30)):
            with self.assertRaisesRegex(RuntimeError, "offline Terraform mirror"):
                guard_module.check_offline_dependencies("prepared:restricted")

    def test_prepared_image_passes_offline_probe(self):
        with patch.object(guard_module, "_docker_json", return_value=[{"Id": "image-id"}]), patch.object(guard_module.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
            guard_module.check_offline_dependencies("prepared:restricted")
            run.assert_called_once()
            self.assertTrue(run.call_args.kwargs["check"])


class ContainerNetworkGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.audit = Path(self.tmp.name) / "audit/network_policy.json"
        self.network = "test-network"
        self.policy = NetworkPolicy(
            http_endpoints=[("airbyte", 80), ("api.together.xyz", 443)],
            direct_tcp_endpoints=[("postgres", 5432), ("external-db.test", 5439)],
            notes=["Fixture policy contains no credentials."],
        )
        self.guard = guard_module.ContainerNetworkGuard(self.policy, self.network, self.audit)
        self.network_info = {
            "Driver": "bridge",
            "IPAM": {"Config": [{"Gateway": "172.18.0.1", "Subnet": "172.18.0.0/16"}]},
            "Containers": {
                "service-id": {"Name": "elt-postgres", "IPv4Address": "172.18.0.2/16"},
                "unselected-id": {"Name": "unselected-service", "IPv4Address": "172.18.0.3/16"},
            },
        }
        self.task_info = {"NetworkSettings": {"Networks": {self.network: {"IPAddress": "172.18.0.50"}}}}

        def docker_json(*args):
            if args == ("network", "inspect", self.network):
                return [self.network_info]
            if args == ("inspect", "service-id"):
                return [{"NetworkSettings": {"Networks": {self.network: {"Aliases": ["postgres", "DB-ALIAS"]}}}}]
            if args == ("inspect", "unselected-id"):
                return [{"NetworkSettings": {"Networks": {self.network: {"Aliases": ["unused-alias"]}}}}]
            if args == ("inspect", "task-container"):
                return [self.task_info]
            raise AssertionError("Unexpected mocked Docker call")

        docker_patch = patch.object(guard_module, "_docker_json", side_effect=docker_json)
        self.docker = docker_patch.start()
        self.addCleanup(docker_patch.stop)
        proxy_patch = patch.object(guard_module, "RestrictedProxy", autospec=True)
        self.proxy_factory = proxy_patch.start()
        self.addCleanup(proxy_patch.stop)
        self.proxy = self.proxy_factory.return_value
        self.proxy.start.return_value = "http://172.18.0.1:32123"
        self.proxy.events = []
        firewall_patch = patch.object(guard_module, "apply_container_firewall", return_value={"verified": True})
        self.firewall = firewall_patch.start()
        self.addCleanup(firewall_patch.stop)

    def test_start_resolves_only_daemon_owned_names_without_expanding_acl(self):
        self.guard.start()
        kwargs = self.proxy_factory.call_args.kwargs
        self.assertEqual(self.proxy_factory.call_args.args[0], self.policy.http_endpoints)
        self.assertEqual(kwargs["bind_host"], "172.18.0.1")
        self.assertEqual(kwargs["allowed_client_ip"], "0.0.0.0")
        mapping = kwargs["host_address_map"]
        self.assertEqual(mapping["host.docker.internal"], "172.18.0.1")
        self.assertEqual(mapping["elt-postgres"], "172.18.0.2")
        self.assertEqual(mapping["postgres"], "172.18.0.2")
        self.assertEqual(mapping["db-alias"], "172.18.0.2")
        self.assertNotIn(("unused-alias", 80), self.policy.http_endpoints)
        self.assertNotIn(("172.18.0.0/16", 80), self.policy.http_endpoints)
        self.assertEqual(self.guard.status, "proxy_ready")
        self.firewall.assert_not_called()

    def test_environment_overrides_all_proxy_casings_and_preserves_empty_clears(self):
        with self.assertRaises(RuntimeError):
            _ = self.guard.environment
        self.guard.start()
        environment = self.guard.environment
        for name in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            self.assertEqual(environment[name], "http://172.18.0.1:32123")
        for name in ("ALL_PROXY", "all_proxy"):
            self.assertIn(name, environment)
            self.assertEqual(environment[name], "")
        for name in ("NO_PROXY", "no_proxy"):
            self.assertEqual(environment[name], "localhost,127.0.0.1,::1")
            self.assertNotIn("*", environment[name])

    def test_security_arguments_remove_capabilities(self):
        self.assertIn("--cap-drop=ALL", self.guard.docker_security_args)
        self.assertIn("--security-opt=no-new-privileges:true", self.guard.docker_security_args)
        self.assertFalse(any("cap-add" in arg or "privileged" in arg for arg in self.guard.docker_security_args))

    def test_install_binds_only_new_task_ip_and_exact_direct_endpoints(self):
        self.guard.start()
        self.guard.install("task-container")
        self.proxy.set_allowed_client_ip.assert_called_once_with("172.18.0.50")
        self.firewall.assert_called_once_with("task-container", "172.18.0.1", 32123, direct_tcp_endpoints=[("172.18.0.2", 5432), ("external-db.test", 5439)])
        self.assertEqual(self.guard.status, "enforced")
        manifest = json.loads(self.audit.read_text())
        self.assertEqual(manifest["status"], "enforced")
        self.assertEqual(manifest["policy"], self.policy.to_dict())
        self.assertEqual(manifest["firewall"], {"verified": True})
        self.assertFalse(self.audit.with_suffix(".json.tmp").exists())

    def test_firewall_failure_propagates_and_records_no_enforced_state(self):
        self.guard.start()
        self.firewall.side_effect = FirewallError("mocked verification failure")
        with self.assertRaises(FirewallError):
            self.guard.install("task-container")
        manifest = json.loads(self.audit.read_text())
        self.assertEqual(manifest["status"], "installation_failed")
        self.assertIsNone(manifest["firewall"])
        self.guard.close()  # The runner owns cleanup even on install failure.
        self.proxy.close.assert_called_once_with()

    def test_missing_task_attachment_never_installs_rules(self):
        self.guard.start()
        self.task_info = {"NetworkSettings": {"Networks": {"wrong-network": {"IPAddress": "172.19.0.2"}}}}
        with self.assertRaisesRegex(RuntimeError, "expected bridge"):
            self.guard.install("task-container")
        self.firewall.assert_not_called()
        self.proxy.set_allowed_client_ip.assert_not_called()
        self.guard.close()
        self.proxy.close.assert_called_once_with()

    def test_nonbridge_network_fails_before_proxy_start(self):
        self.network_info["Driver"] = "host"
        with self.assertRaisesRegex(RuntimeError, "Docker bridge"):
            self.guard.start()
        self.proxy_factory.assert_not_called()
        self.firewall.assert_not_called()

    def test_no_ipv4_gateway_fails_before_proxy_start(self):
        self.network_info["IPAM"]["Config"] = [{"Gateway": "2001:db8::1"}]
        with self.assertRaisesRegex(RuntimeError, "IPv4 gateway"):
            self.guard.start()
        self.proxy_factory.assert_not_called()

    def test_install_before_start_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "not running"):
            self.guard.install("task-container")
        self.firewall.assert_not_called()

    def test_close_after_partial_start_still_closes_proxy(self):
        self.proxy.start.side_effect = OSError("mocked bind failure")
        with self.assertRaises(OSError):
            self.guard.start()
        self.guard.close()
        self.proxy.close.assert_called_once_with()
        self.assertEqual(json.loads(self.audit.read_text())["status"], "not_started")

    def test_audit_copies_proxy_metadata_without_request_contents(self):
        self.guard.start()
        self.proxy.events = [{"host": "github.com", "port": 443, "method": "CONNECT", "allowed": False, "result": "endpoint_denied"}]
        self.guard.install("task-container")
        self.guard.close()
        saved = json.loads(self.audit.read_text())
        self.assertEqual(saved["proxy_events"], self.proxy.events)
        self.assertNotIn(("github.com", 443), self.policy.http_endpoints)
        self.assertNotIn("headers", json.dumps(saved))


if __name__ == "__main__":
    unittest.main()

"""Isolation tests using a fake Docker/netns executor; never touch real rules."""
import copy
import importlib.util
import json
import os
import sys
from pathlib import Path
import socket
import subprocess
from types import SimpleNamespace
import unittest
from unittest import mock

MODULE = Path(__file__).resolve().parents[1] / "agents/common/network_firewall.py"
spec = importlib.util.spec_from_file_location("network_firewall_test_target", MODULE)
fw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fw)


class FakeSystem:
    def __init__(self):
        self.snapshot = {"id": "abc123", "pid": 4321, "running": True,
                         "network_mode": "task-network", "privileged": False,
                         "cap_drop": ["ALL"], "cap_add": [],
                         "security_opt": ["no-new-privileges:true"]}
        self.inode = 22
        self.calls = []
        self.installed = {}
        self.fail_on = None
        self.modify_saved = None
        self.inspect_count = 0
        self.change_pid_on_inspect = None

    def run(self, args, *, input=None, **kwargs):
        self.calls.append((list(args), input))
        self.assert_safe_invocation(args, kwargs)
        if self.fail_on and self.fail_on in args:
            return subprocess.CompletedProcess(args, 1, "", "private diagnostic must not leak")
        if args[:2] == ["docker", "inspect"]:
            self.inspect_count += 1
            snapshot = copy.deepcopy(self.snapshot)
            if self.inspect_count == self.change_pid_on_inspect:
                snapshot["pid"] += 1
            return subprocess.CompletedProcess(args, 0, json.dumps(snapshot), "")
        if args[:3] == ["sudo", "-n", "stat"]:
            return subprocess.CompletedProcess(args, 0, str(self.inode) + "\n", "")
        if args[:3] != ["sudo", "-n", "nsenter"]:
            raise AssertionError("Unexpected administrative command")
        if args[3:7] != ["--target", "4321", "--net", "--"]:
            raise AssertionError("Firewall command must enter only the task netns")
        if args[7:10] != [sys.executable, "-I", "-c"] or args[10] != fw._NAMESPACE_EXEC_GUARD or args[11] != "22":
            raise AssertionError("Firewall tool requires an in-namespace inode guard")
        tool = args[12]
        if tool.endswith("-restore"):
            self.installed[tool.removesuffix("-restore")] = input
            return subprocess.CompletedProcess(args, 0, "", "")
        if tool.endswith("-save"):
            prefix = tool.removesuffix("-save")
            output = self.installed[prefix]
            # Kernel output may reorder conntrack states and change counters.
            output = output.replace("ESTABLISHED,RELATED", "RELATED,ESTABLISHED")
            output = output.replace("[0:0]", "[7:100]")
            if self.modify_saved:
                output = self.modify_saved(prefix, output)
            return subprocess.CompletedProcess(args, 0, "# generated\n" + output, "")
        raise AssertionError("Unexpected namespace tool")

    @staticmethod
    def assert_safe_invocation(args, kwargs):
        if not isinstance(args, list) or kwargs.get("shell"):
            raise AssertionError("Shell invocation is forbidden")
        if kwargs.get("timeout") != 30:
            raise AssertionError("Administrative commands need a finite timeout")

    def firewall_calls(self):
        return [args for args, _ in self.calls if args[:3] == ["sudo", "-n", "nsenter"]]


class FirewallTests(unittest.TestCase):
    def setUp(self):
        self.fake = FakeSystem()
        self.patches = [
            mock.patch.object(fw.subprocess, "run", side_effect=self.fake.run),
            mock.patch.object(fw, "_host_namespace_inodes", return_value={11}),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def apply(self, **kwargs):
        return fw.apply_container_firewall("fresh-task", "192.0.2.10", 3128, **kwargs)

    def test_default_deny_exact_tcp_allowances_both_families_and_readback(self):
        result = self.apply(direct_tcp_endpoints=[("198.51.100.20", 5439), ("2001:db8::20", 443)])
        self.assertTrue(result["enforced"])
        self.assertEqual(result["network_namespace_inode"], 22)
        self.assertEqual(len(self.fake.firewall_calls()), 4)
        v4, v6 = self.fake.installed["iptables"], self.fake.installed["ip6tables"]
        for text in (v4, v6):
            self.assertIn(":OUTPUT DROP", text)
            self.assertIn(":FORWARD DROP", text)
            self.assertIn("-o lo -j ACCEPT", text)
            self.assertNotIn("-p udp", text)
            self.assertNotIn("0.0.0.0/0", text)
        self.assertIn("192.0.2.10/32 -p tcp -m tcp --dport 3128", v4)
        self.assertIn("198.51.100.20/32 -p tcp -m tcp --dport 5439", v4)
        self.assertIn("2001:db8::20/128 -p tcp -m tcp --dport 443", v6)
        self.assertNotIn("198.51.100.20", v6)
        self.assertTrue(result["families"]["ipv4"]["verified"])
        self.assertTrue(result["families"]["ipv6"]["verified"])

    def test_resolved_proxy_includes_only_resolved_addresses_and_port(self):
        records = [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("192.0.2.10", 3128)),
            (socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("2001:db8::10", 3128, 0, 0)),
        ]
        with mock.patch.object(fw.socket, "getaddrinfo", return_value=records):
            result = fw.apply_container_firewall("fresh-task", "proxy.test", 3128)
        self.assertEqual(result["proxy"]["resolved_addresses"], ["192.0.2.10", "2001:db8::10"])
        self.assertIn("2001:db8::10/128", self.fake.installed["ip6tables"])

    def test_host_and_shared_network_modes_are_rejected_without_mutation(self):
        for mode in ("host", "container:some-other-container"):
            with self.subTest(mode=mode):
                self.fake.snapshot["network_mode"] = mode
                with self.assertRaises(fw.FirewallError):
                    self.apply()
        self.assertEqual(self.fake.firewall_calls(), [])

    def test_even_misreported_network_mode_cannot_target_host_inode(self):
        self.fake.inode = 11
        with self.assertRaisesRegex(fw.FirewallError, "host network namespace"):
            self.apply()
        self.assertEqual(self.fake.firewall_calls(), [])

    def test_container_replacement_aborts_before_next_mutation(self):
        self.fake.change_pid_on_inspect = 3
        with self.assertRaisesRegex(fw.FirewallError, "identity/PID changed"):
            self.apply()
        self.assertEqual(len(self.fake.firewall_calls()), 1)
        self.assertIn("iptables-restore", self.fake.firewall_calls()[0])

    def test_missing_hardening_settings_fail_closed(self):
        cases = [{"privileged": True}, {"cap_drop": []}, {"cap_add": ["NET_ADMIN"]},
                 {"security_opt": []}, {"security_opt": ["no-new-privileges:false"]},
                 {"running": False}, {"pid": 0}, {"pid": True}]
        original = copy.deepcopy(self.fake.snapshot)
        for update in cases:
            with self.subTest(update=update):
                self.fake.snapshot = {**original, **update}
                with self.assertRaises(fw.FirewallError):
                    self.apply()
        self.assertEqual(self.fake.firewall_calls(), [])

    def test_ipv6_install_failure_does_not_return_partial_success(self):
        self.fake.fail_on = "ip6tables-restore"
        with self.assertRaisesRegex(fw.FirewallError, "IPv6"):
            self.apply()
        self.assertIn("iptables", self.fake.installed)
        self.assertNotIn("ip6tables", self.fake.installed)

    def test_sudo_denial_is_explicit_and_does_not_leak_diagnostics(self):
        self.fake.fail_on = "stat"
        with self.assertRaises(fw.FirewallError) as cm:
            self.apply()
        self.assertIn("sudo -n", str(cm.exception))
        self.assertNotIn("private diagnostic", str(cm.exception))
        self.assertEqual(self.fake.firewall_calls(), [])

    def test_broad_accept_in_readback_is_rejected(self):
        self.fake.modify_saved = lambda family, text: text.replace("COMMIT", "-A OUTPUT -j ACCEPT\nCOMMIT")
        with self.assertRaisesRegex(fw.FirewallError, "do not match"):
            self.apply()

    def test_output_policy_changed_to_accept_is_rejected(self):
        self.fake.modify_saved = lambda family, text: text.replace(":OUTPUT DROP", ":OUTPUT ACCEPT")
        with self.assertRaises(fw.FirewallError):
            self.apply()

    def test_ipv6_readback_must_be_verified_too(self):
        self.fake.modify_saved = lambda family, text: text.replace(":OUTPUT DROP", ":OUTPUT ACCEPT") if family == "ip6tables" else text
        with self.assertRaises(fw.FirewallError):
            self.apply()

    def test_invalid_proxy_arguments_cannot_become_command_arguments(self):
        for host, port in [("https://proxy.test", 443), ("name:secret@proxy.test", 443),
                           ("proxy.test", "3128"), ("proxy.test", True),
                           ("proxy.test", 0), ("0.0.0.0", 3128), ("::", 3128),
                           ("ff02::1", 3128), ("fe80::1%eth0", 3128)]:
            with self.subTest(host=host, port=port):
                with self.assertRaises(fw.FirewallError):
                    fw.apply_container_firewall("fresh-task", host, port)
        self.assertEqual(self.fake.calls, [])

    def test_dns_failure_never_installs_rules_or_starts_agent(self):
        with mock.patch.object(fw.socket, "getaddrinfo", side_effect=socket.gaierror()):
            with self.assertRaises(fw.FirewallError):
                fw.apply_container_firewall("fresh-task", "absent.test", 3128)
        self.assertEqual(self.fake.calls, [])

    def test_no_admin_command_is_ever_run_in_host_namespace(self):
        self.apply()
        for args, _ in self.fake.calls:
            if any("tables-" in token for token in args):
                self.assertEqual(args[:7], ["sudo", "-n", "nsenter", "--target", "4321", "--net", "--"])
        inspect = next(args for args, _ in self.fake.calls if args[:2] == ["docker", "inspect"])
        self.assertNotIn(".Config.Env", inspect[inspect.index("--format") + 1])

    def test_incomplete_verification_output_fails(self):
        self.fake.modify_saved = lambda family, text: text.replace("COMMIT", "")
        with self.assertRaisesRegex(fw.FirewallError, "Incomplete"):
            self.apply()


class HostNamespaceIdentityTests(unittest.TestCase):
    def test_protected_init_namespace_uses_read_only_sudo_and_preserves_both_ids(self):
        with mock.patch.object(fw.os, "stat", side_effect=[SimpleNamespace(st_ino=11), PermissionError()]), \
                mock.patch.object(fw, "_namespace_inode", return_value=12) as sudo_stat:
            self.assertEqual(fw._host_namespace_inodes(), {11, 12})
        sudo_stat.assert_called_once_with(1)

    def test_init_namespace_sudo_failure_never_omits_host_identity_check(self):
        with mock.patch.object(fw.os, "stat", side_effect=[SimpleNamespace(st_ino=11), PermissionError()]), \
                mock.patch.object(fw, "_namespace_inode", side_effect=fw.FirewallError("sudo denied")):
            with self.assertRaisesRegex(fw.FirewallError, "sudo denied"):
                fw._host_namespace_inodes()

    def test_unreadable_current_namespace_fails_without_administrative_mutation(self):
        with mock.patch.object(fw.os, "stat", side_effect=PermissionError()), \
                mock.patch.object(fw, "_namespace_inode") as sudo_stat:
            with self.assertRaisesRegex(fw.FirewallError, "host network namespace"):
                fw._host_namespace_inodes()
        sudo_stat.assert_not_called()


class EnteredNamespaceGuardTests(unittest.TestCase):
    def test_wrong_namespace_exits_before_running_the_requested_program(self):
        wrong_inode = os.stat("/proc/self/ns/net").st_ino + 1
        result = subprocess.run(
            [sys.executable, "-I", "-c", fw._NAMESPACE_EXEC_GUARD, str(wrong_inode),
             sys.executable, "-I", "-c", "print('must-not-execute')"],
            capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(result.returncode, 125)
        self.assertEqual(result.stdout, "")

    def test_matching_namespace_preserves_stdin_without_using_a_shell(self):
        inode = os.stat("/proc/self/ns/net").st_ino
        result = subprocess.run(
            [sys.executable, "-I", "-c", fw._NAMESPACE_EXEC_GUARD, str(inode),
             sys.executable, "-I", "-c", "import sys; print(sys.stdin.read(), end='')"],
            input="*filter\nCOMMIT\n", capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "*filter\nCOMMIT\n")


if __name__ == "__main__":
    unittest.main()

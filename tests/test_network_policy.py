"""Offline tests: no container, warehouse, DNS or external HTTP access."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import MagicMock, patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents"))
from common import network_policy as policy  # noqa: E402


SECRET = "MUST_NOT_APPEAR_IN_AUDIT_123"


class NetworkPolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "config.yaml"
        self.config = {
            "snowflake": {"config": {"account": "org-account", "username": "test-user", "password": SECRET, "database": "task-db", "schema": "task", "warehouse": "task-wh", "role": "airbyte-role"}},
            "databricks": {"config": {"hostname": "workspace.example.test", "client_id": "id", "secret": SECRET}},
            "redshift": {"config": {"host": "cluster.example.test", "port": 5439, "password": SECRET}},
            "Airbyte": {"config": {"server_url": "http://airbyte:80/api/public/v1/", "password": SECRET}},
            "postgres": {"config": {"host": "elt-postgres", "port": 5432, "password": SECRET}},
            "mongodb": {"config": {"connection_string": f"mongodb://user:{SECRET}@mongo-a:27017,mongo-b:27018/db?replicaSet=rs0"}},
            "aws_s3": {"AWS_ENDPOINT_URL": "http://elt-localstack:4566", "AWS_SECRET_ACCESS_KEY": SECRET},
            "flat_files": [{"path": f"https://drive.google.com/uc?id=data&token={SECRET}"}],
            "custom_api": {"config": {"configuration": {}}},
        }
        self.discovery = patch.object(policy, "discover_snowflake_endpoints", return_value=[("account.snowflakecomputing.com", 443), ("ocsp.example.test", 80), ("account-stage.s3.example.test", 443)])
        self.discover_mock = self.discovery.start()
        self.addCleanup(self.discovery.stop)

    def build(self, destination="snowflake", runner="openhands", model="together_ai/zai-org/GLM-5.3", **kwargs):
        self.path.write_text(yaml.safe_dump(self.config), encoding="utf-8")
        kwargs.setdefault("environ", {})
        return policy.build_network_policy(self.path, destination, runner, model, **kwargs)

    def test_full_task_separates_proxy_and_native_database_endpoints(self):
        actual = self.build()
        self.assertEqual(actual.direct_tcp_endpoints, [("elt-postgres", 5432), ("mongo-a", 27017), ("mongo-b", 27018)])
        self.assertEqual(set(actual.http_endpoints), {("account.snowflakecomputing.com", 443), ("ocsp.example.test", 80), ("account-stage.s3.example.test", 443), ("airbyte", 80), ("elt-localstack", 4566), ("drive.google.com", 443), ("api.together.xyz", 443), ("api.together.ai", 443)})
        self.assertEqual(self.discover_mock.call_count, 1)
        self.assertNotIn(SECRET, json.dumps(actual.to_dict()))

    def test_kimi_uses_selected_together_provider_not_model_owner(self):
        result = self.build(model="together_ai/moonshotai/Kimi-K3", transform_only=True)
        self.assertIn(("api.together.xyz", 443), result.http_endpoints)
        self.assertFalse(any("moonshot" in host or "zai" in host for host, _ in result.http_endpoints))

    def test_no_implicit_repositories_registries_search_or_wildcards(self):
        result = self.build()
        hosts = {host for host, _ in result.http_endpoints + result.direct_tcp_endpoints}
        forbidden = {"github.com", "api.github.com", "raw.githubusercontent.com", "huggingface.co", "pypi.org", "files.pythonhosted.org", "google.com", "bing.com", "amazonaws.com", "snowflakecomputing.com"}
        self.assertFalse(hosts & forbidden)
        self.assertFalse(any("*" in host for host in hosts))

    def test_transform_only_skips_even_invalid_source_sections(self):
        for key in ("Airbyte", "postgres", "mongodb", "aws_s3", "flat_files", "custom_api"):
            self.config[key] = "invalid source ignored in transformation-only mode"
        result = self.build(transform_only=True)
        self.assertEqual(result.direct_tcp_endpoints, [])
        self.assertEqual(len(result.http_endpoints), 5)

    def test_databricks_exact_workspace_host_only(self):
        self.config["databricks"]["config"]["hostname"] = f"https://Workspace.Example.Test:8443/sql/1.0?token={SECRET}"
        result = self.build(destination="databricks", transform_only=True)
        self.assertIn(("workspace.example.test", 8443), result.http_endpoints)
        self.assertEqual(self.discover_mock.call_count, 0)
        self.assertNotIn(SECRET, json.dumps(result.to_dict()))

    def test_redshift_is_direct_tcp(self):
        result = self.build(destination="redshift", transform_only=True)
        self.assertEqual(result.direct_tcp_endpoints, [("cluster.example.test", 5439)])
        self.assertNotIn(("cluster.example.test", 5439), result.http_endpoints)

    def test_credential_overlay_matches_warehouse_role_semantics(self):
        credentials = {"account": "override-account", "user": "override-user", "password": SECRET, "role": "connection-role", "warehouse": "connection-wh", "database": "ignore-db", "schema": "ignore-schema"}
        (self.path.parent / "snowflake_credential.json").write_text(json.dumps(credentials))
        result = self.build()
        given = self.discover_mock.call_args.args[0]
        self.assertEqual(given["_connection_role"], "connection-role")
        self.assertEqual(given["_connection_warehouse"], "connection-wh")
        self.assertEqual(given["role"], "airbyte-role")
        self.assertEqual(given["database"], "task-db")
        self.assertEqual(given["schema"], "task")
        self.assertEqual(given["user"], "override-user")
        self.assertNotIn(SECRET, json.dumps(result.to_dict()))

    def test_discovery_failure_does_not_leak_connector_exception(self):
        self.discover_mock.side_effect = RuntimeError("connection password=" + SECRET)
        with self.assertRaises(policy.NetworkPolicyError) as ctx:
            self.build()
        self.assertNotIn(SECRET, str(ctx.exception))
        self.assertIn("no network policy", str(ctx.exception))

    def test_empty_or_wildcard_discovery_fails_closed(self):
        for value in ([], [("*.amazonaws.com", 443)], [("good.test", 0)], [("good.test", True)]):
            with self.subTest(value=value):
                self.discover_mock.return_value = value
                with self.assertRaises(policy.NetworkPolicyError):
                    self.build()

    def test_extra_endpoint_deduplication_and_canonicalization(self):
        result = self.build(extra_endpoints=["MODEL.EXAMPLE.TEST:443", "model.example.test:443", "https://other.example.test:8443"])
        self.assertEqual(result.http_endpoints.count(("model.example.test", 443)), 1)
        self.assertIn(("other.example.test", 8443), result.http_endpoints)
        self.assertNotIn(("model.example.test", 443), result.direct_tcp_endpoints)

    def test_operator_wildcard_subnet_userinfo_and_path_rejected(self):
        bad = ["*.example.test:443", ".example.test:443", "10.0.0.0/8:443", f"user:{SECRET}@example.test:443", "example.test", "example.test:0", "example.test:65536", "example.test:NaN", "https://example.test:443/path", "example.test:443?token=" + SECRET, "example.test:443#fragment", "https://example.test", "example.test:443\n", "example.test\\@evil.test:443", "[fe80::1%eth0]:443", "127.1:443"]
        for value in bad:
            with self.subTest(value=value.replace(SECRET, "REDACTED")):
                with self.assertRaises(policy.NetworkPolicyError) as ctx:
                    policy.parse_extra_endpoint(value)
                self.assertNotIn(SECRET, str(ctx.exception))

    def test_exact_ipv4_ipv6_operator_endpoints(self):
        self.assertEqual(policy.parse_extra_endpoint("127.0.0.1:8080"), ("127.0.0.1", 8080))
        self.assertEqual(policy.parse_extra_endpoint("[2001:db8::1]:443"), ("2001:db8::1", 443))

    def test_explicit_provider_base_replaces_default_and_strips_query(self):
        result = self.build(transform_only=True, environ={"TOGETHERAI_API_BASE": f"https://llm.example.test:8443/v1?key={SECRET}", "ANTHROPIC_BASE_URL": "https://unselected.example.test"})
        self.assertIn(("llm.example.test", 8443), result.http_endpoints)
        self.assertNotIn(("api.together.xyz", 443), result.http_endpoints)
        self.assertNotIn(("unselected.example.test", 443), result.http_endpoints)
        self.assertNotIn(SECRET, json.dumps(result.to_dict()))

    def test_selected_base_has_deterministic_precedence_and_only_one_permission(self):
        env = {
            "TOGETHERAI_API_BASE": "https://first.example.test/v1",
            "TOGETHER_API_BASE": "https://second.example.test/v1",
            "TOGETHER_BASE_URL": "https://third.example.test/v1",
            "LLM_BASE_URL": "https://generic-first.example.test/v1",
            "LLM_API_BASE": "https://generic-second.example.test/v1",
        }
        model = "together_ai/zai-org/GLM-5.3"
        for name in list(env):
            selected = policy.selected_model_api_base("openhands", model, env)
            self.assertEqual(selected, env[name])
            result = self.build(model=model, transform_only=True, environ=env)
            selected_host = selected.split("/")[2]
            extra_hosts = {host for host, _ in result.http_endpoints} - {"account.snowflakecomputing.com", "ocsp.example.test", "account-stage.s3.example.test"}
            self.assertEqual(extra_hosts, {selected_host})
            env.pop(name)
        self.assertIsNone(policy.selected_model_api_base("openhands", model, env))

    def test_selected_base_ignores_unselected_malformed_values(self):
        env = {"OPENAI_BASE_URL": "https://selected.example.test/v1", "OPENAI_API_BASE": f"https://user:{SECRET}@bad.test", "LLM_BASE_URL": "not a url"}
        self.assertEqual(policy.selected_model_api_base("openhands", "openai/gpt-6", env), "https://selected.example.test/v1")

    def test_selected_base_skips_empty_values_and_can_use_process_environment(self):
        env = {"TOGETHERAI_API_BASE": "", "LLM_BASE_URL": "https://fallback.example.test/v1"}
        with patch.dict(policy.os.environ, env, clear=True):
            self.assertEqual(policy.selected_model_api_base("openhands", "together_ai/moonshotai/Kimi-K3"), env["LLM_BASE_URL"])

    def test_claude_ignores_generic_and_unsupported_base_variables(self):
        env = {"ANTHROPIC_API_BASE": "https://unused-anthropic.test", "LLM_BASE_URL": "https://unused-generic.test", "LLM_API_BASE": f"https://user:{SECRET}@unused.test"}
        self.assertIsNone(policy.selected_model_api_base("claude", "claude-opus-4-7", env))
        result = self.build(runner="claude", model="claude-opus-4-7", transform_only=True, environ=env)
        self.assertIn(("api.anthropic.com", 443), result.http_endpoints)
        self.assertFalse(any("unused" in host for host, _ in result.http_endpoints))
        env["ANTHROPIC_BASE_URL"] = "https://selected-anthropic.test/v1"
        self.assertEqual(policy.selected_model_api_base("claude", "claude-opus-4-7", env), env["ANTHROPIC_BASE_URL"])
        result = self.build(runner="claude", model="claude-opus-4-7", transform_only=True, environ=env)
        self.assertIn(("selected-anthropic.test", 443), result.http_endpoints)
        self.assertNotIn(("api.anthropic.com", 443), result.http_endpoints)

    def test_selected_base_is_validated_before_runner_receives_it(self):
        with self.assertRaises(policy.NetworkPolicyError) as ctx:
            policy.selected_model_api_base("openhands", "openai/gpt-6", {"OPENAI_BASE_URL": f"https://user:{SECRET}@bad.test"})
        self.assertNotIn(SECRET, str(ctx.exception))

    def test_llm_base_userinfo_fails_without_secret_in_error(self):
        with self.assertRaises(policy.NetworkPolicyError) as ctx:
            self.build(environ={"LLM_BASE_URL": f"https://user:{SECRET}@model.example.test/v1"})
        self.assertNotIn(SECRET, str(ctx.exception))

    def test_unknown_provider_requires_explicit_operator_permission(self):
        with self.assertRaisesRegex(policy.NetworkPolicyError, "--network-allow"):
            self.build(model="unknown/model")
        result = self.build(model="unknown/model", extra_endpoints=["custom.example.test:443"], transform_only=True)
        self.assertIn(("custom.example.test", 443), result.http_endpoints)
        self.assertEqual(len(result.http_endpoints), 4)

    def test_unknown_provider_can_use_explicit_base(self):
        result = self.build(model="unknown/model", transform_only=True, environ={"LLM_API_BASE": "http://model.internal:9000/v1"})
        self.assertIn(("model.internal", 9000), result.http_endpoints)

    def test_claude_oauth_and_api(self):
        api = self.build(runner="claude", model="claude-opus-4-7", transform_only=True, environ={"ANTHROPIC_API_KEY": SECRET})
        oauth = self.build(runner="claude", model="claude-opus-4-7", transform_only=True, environ={"CLAUDE_CODE_OAUTH_TOKEN": SECRET})
        self.assertIn(("api.anthropic.com", 443), api.http_endpoints)
        self.assertNotIn(("claude.ai", 443), api.http_endpoints)
        self.assertIn(("claude.ai", 443), oauth.http_endpoints)
        self.assertNotIn(SECRET, json.dumps(oauth.to_dict()))

    def test_unsupported_claude_cloud_mode_does_not_guess(self):
        with self.assertRaises(policy.NetworkPolicyError):
            self.build(runner="claude", model="claude-opus-4-7", environ={"CLAUDE_CODE_USE_BEDROCK": "1"})

    def test_codex_cli_and_sdk_are_distinct(self):
        sdk = self.build(runner="codex", model="gpt-6", transform_only=True)
        cli = self.build(runner="codex-cli", model="gpt-6", transform_only=True)
        self.assertIn(("api.openai.com", 443), sdk.http_endpoints)
        self.assertNotIn(("chatgpt.com", 443), sdk.http_endpoints)
        self.assertIn(("chatgpt.com", 443), cli.http_endpoints)
        self.assertIn(("auth.openai.com", 443), cli.http_endpoints)

    def test_source_http_userinfo_does_not_leak(self):
        self.config["Airbyte"]["config"]["server_url"] = f"http://user:{SECRET}@airbyte:80/"
        with self.assertRaises(policy.NetworkPolicyError) as ctx:
            self.build()
        self.assertNotIn(SECRET, str(ctx.exception))

    def test_mongodb_port_zero_and_srv_fail_closed(self):
        for uri in ("mongodb://mongo:0/db", "mongodb+srv://mongo.example.test/db"):
            self.config["mongodb"]["config"]["connection_string"] = uri
            with self.subTest(uri=uri), self.assertRaises(policy.NetworkPolicyError):
                self.build()

    def test_custom_api_only_explicit_endpoint_is_allowed(self):
        self.config["custom_api"]["config"]["configuration"] = json.dumps({"base_url": f"http://source.internal:5005/task?key={SECRET}", "api_key": SECRET})
        result = self.build()
        self.assertIn(("source.internal", 5005), result.http_endpoints)
        self.assertNotIn(SECRET, json.dumps(result.to_dict()))

    def test_missing_s3_endpoint_does_not_grant_aws_suffix(self):
        del self.config["aws_s3"]["AWS_ENDPOINT_URL"]
        with self.assertRaises(policy.NetworkPolicyError):
            self.build()

    def test_bad_yaml_and_credential_json_do_not_echo_sensitive_lines(self):
        self.path.write_text("password: [" + SECRET)
        with self.assertRaises(policy.NetworkPolicyError) as ctx:
            policy.build_network_policy(self.path, "snowflake", "claude", "claude", environ={})
        self.assertNotIn(SECRET, str(ctx.exception))
        (self.path.parent / "snowflake_credential.json").write_text('{"password": "' + SECRET)
        with self.assertRaises(policy.NetworkPolicyError) as ctx:
            self.build()
        self.assertNotIn(SECRET, str(ctx.exception))

    def test_config_path_name_is_respected(self):
        self.path = self.path.with_name("trusted-task.yaml")
        self.assertTrue(self.build().http_endpoints)


class SnowflakeDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.connector = ModuleType("snowflake.connector")
        self.connector.connect = MagicMock()
        parent = ModuleType("snowflake")
        parent.connector = self.connector
        self.modules = patch.dict(sys.modules, {"snowflake": parent, "snowflake.connector": self.connector})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.cursor = self.connector.connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
        self.config = {"account": "org-account", "username": "test-user", "password": SECRET, "warehouse": "task-wh", "role": "airbyte-role", "_connection_warehouse": "admin-wh", "_connection_role": "connection-role"}

    def test_exact_account_allowlist_query_and_connection_arguments(self):
        self.cursor.fetchone.return_value = (json.dumps([{"host": "ACCOUNT.snowflakecomputing.com", "port": 443, "type": "SNOWFLAKE_DEPLOYMENT"}, {"host": "ocsp.example.test", "port": 80, "type": "OCSP_CACHE"}, {"host": "bucket.s3.example.test", "port": 443, "type": "STAGE"}]),)
        result = policy.discover_snowflake_endpoints(self.config)
        self.cursor.execute.assert_called_once_with("SELECT SYSTEM$ALLOWLIST()")
        self.connector.connect.assert_called_once_with(account="org-account", user="test-user", password=SECRET, warehouse="admin-wh", role="connection-role")
        self.assertIn(("account.snowflakecomputing.com", 443), result)
        self.assertEqual(len(result), 3)

    def test_connector_failure_is_sanitized(self):
        self.connector.connect.side_effect = RuntimeError("private config " + SECRET)
        with self.assertRaises(policy.NetworkPolicyError) as ctx:
            policy.discover_snowflake_endpoints(self.config)
        self.assertNotIn(SECRET, str(ctx.exception))

    def test_real_shaped_allowlist_selects_only_sql_transport_types(self):
        transport = [
            ("SNOWFLAKE_DEPLOYMENT", "account.snowflakecomputing.com", 443),
            ("SNOWFLAKE_DEPLOYMENT_REGIONLESS", "org-account.snowflakecomputing.com", 443),
            ("STAGE", "sfc-stage.s3.us-west-2.amazonaws.com", 443),
            ("OCSP_CACHE", "ocsp.snowflakecomputing.com", 80),
            ("OCSP_CACHE_REGIONLESS", "ocsp.org-account.snowflakecomputing.com", 80),
            ("OCSP_RESPONDER", "ocsp.example.test", 80),
            ("CRL_DISTRIBUTION_POINT", "crl.r2m01.amazontrust.com", 80),
        ]
        optional = [
            "SNOWSQL_REPO", "OUT_OF_BAND_TELEMETRY", "DUO_SECURITY",
            "SNOWCONVERT", "SPCS_REGISTRY_REGIONLESS", "ACCOUNT_PUBLIC",
            "SNOWSIGHT_DEPLOYMENT", "SNOWSIGHT_DEPLOYMENT_REGIONLESS",
            "OPENFLOW", "EXTERNAL_TELEMETRY", "DCP_DEPLOYMENT", "DCP_REGISTRY",
            "CLIENT_FAILOVER", "OCSP_CLIENT_FAILOVER", "FUTURE_OPTIONAL_SERVICE",
        ]
        entries = [{"type": kind, "host": host, "port": port} for kind, host, port in transport]
        entries += [{"type": kind, "host": kind.lower().replace("_", "-") + ".optional.test", "port": 443} for kind in optional]
        entries += [
            {"type": "ACCOUNT_PUBLIC_WILDCARD", "host": "*.account.snowflake.app", "port": 443},
            {"type": "APP_SERVICE_PUBLIC_WILDCARD", "host": "*.org-account.us-west-2.aws.snowflake.app", "port": 80},
        ]
        self.cursor.fetchone.return_value = (json.dumps(entries),)
        result = policy.discover_snowflake_endpoints(self.config)
        self.assertEqual(result, sorted((host, port) for _, host, port in transport))
        self.assertFalse(any("*" in host or host.endswith(".optional.test") for host, _ in result))

    def test_regionless_sql_deployment_is_sufficient_and_duplicates_collapse(self):
        entry = {"type": "SNOWFLAKE_DEPLOYMENT_REGIONLESS", "host": "org-account.snowflakecomputing.com", "port": 443}
        self.cursor.fetchone.return_value = ([entry, entry],)
        self.assertEqual(policy.discover_snowflake_endpoints(self.config), [("org-account.snowflakecomputing.com", 443)])

    def test_wildcard_or_invalid_selected_transport_fails_closed(self):
        deployment = {"type": "SNOWFLAKE_DEPLOYMENT", "host": "account.snowflakecomputing.com", "port": 443}
        for kind in policy._SNOWFLAKE_SQL_TRANSPORT_TYPES:
            for endpoint in ({"host": "*.amazonaws.com", "port": 443}, {"host": "good.test", "port": 0}, {"host": "user:" + SECRET + "@good.test", "port": 443}, {"port": 443}):
                self.cursor.fetchone.return_value = (json.dumps([deployment, {"type": kind, **endpoint}]),)
                with self.subTest(kind=kind, fields=tuple(endpoint)), self.assertRaises(policy.NetworkPolicyError) as ctx:
                    policy.discover_snowflake_endpoints(self.config)
                self.assertNotIn(SECRET, str(ctx.exception))

    def test_missing_sql_deployment_fails_even_with_valid_stage_or_optional_hosts(self):
        for entries in ([{"type": "STAGE", "host": "bucket.s3.example.test", "port": 443}], [{"type": "ACCOUNT_PUBLIC", "host": "account.snowflakecomputing.com", "port": 443}], [{"type": "ACCOUNT_PUBLIC_WILDCARD", "host": "*.snowflake.app", "port": 443}]):
            self.cursor.fetchone.return_value = (entries,)
            with self.subTest(kind=entries[0]["type"]), self.assertRaises(policy.NetworkPolicyError):
                policy.discover_snowflake_endpoints(self.config)

    def test_missing_or_malformed_type_cannot_be_silently_accepted(self):
        deployment = {"type": "SNOWFLAKE_DEPLOYMENT", "host": "account.snowflakecomputing.com", "port": 443}
        for malformed in (None, [], {}, {"type": None}, {"type": []}, {"type": "STAGE "}, {"host": "example.test", "port": 443}):
            self.cursor.fetchone.return_value = ([deployment, malformed],)
            with self.subTest(entry_type=type(malformed).__name__), self.assertRaises(policy.NetworkPolicyError):
                policy.discover_snowflake_endpoints(self.config)

    def test_malformed_empty_or_wildcard_server_result_aborts(self):
        for value in (None, ("[]",), ("not json " + SECRET,), ('[{"host":"*.amazonaws.com","port":443}]',), ('[{"host":"good.test","port":0}]',)):
            self.cursor.fetchone.return_value = value
            with self.subTest(result_type=type(value).__name__), self.assertRaises(policy.NetworkPolicyError) as ctx:
                policy.discover_snowflake_endpoints(self.config)
            self.assertNotIn(SECRET, str(ctx.exception))


if __name__ == "__main__":
    unittest.main()

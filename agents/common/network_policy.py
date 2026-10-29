"""Build a narrow, auditable task egress policy on the trusted runner.

This module does not install firewall rules. HTTP(S) endpoints belong behind
the enforcing proxy; only native database protocols belong in the direct TCP
list. Endpoint discovery happens before the agent receives its workspace.
Never derive permissions from files that the agent has subsequently edited.
"""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

import yaml


Endpoint = tuple[str, int]

# SYSTEM$ALLOWLIST also returns optional apps, package downloads, UI and
# telemetry endpoints, including wildcard hosts. This benchmark uses SQL
# clients, so grant only these documented transport and certificate endpoints.
# https://docs.snowflake.com/en/sql-reference/functions/system_allowlist
_SNOWFLAKE_SQL_DEPLOYMENT_TYPES = frozenset({
    "SNOWFLAKE_DEPLOYMENT", "SNOWFLAKE_DEPLOYMENT_REGIONLESS",
})
_SNOWFLAKE_SQL_TRANSPORT_TYPES = _SNOWFLAKE_SQL_DEPLOYMENT_TYPES | frozenset({
    "STAGE", "OCSP_CACHE", "OCSP_CACHE_REGIONLESS", "OCSP_RESPONDER",
    "CRL_DISTRIBUTION_POINT",
})


class NetworkPolicyError(ValueError):
    """The required endpoint set could not be established safely."""


@dataclass
class NetworkPolicy:
    http_endpoints: list[Endpoint]
    direct_tcp_endpoints: list[Endpoint]
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Return only host/port permissions and non-sensitive policy notes."""
        return {
            "http_endpoints": [list(endpoint) for endpoint in self.http_endpoints],
            "direct_tcp_endpoints": [list(endpoint) for endpoint in self.direct_tcp_endpoints],
            "notes": list(self.notes),
        }


def _host(value: Any) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise NetworkPolicyError("Endpoint host must be an exact hostname or IP address.")
    if any(c.isspace() or ord(c) < 32 for c in value) or any(c in value for c in "*/\\@?#%"):
        raise NetworkPolicyError("Wildcard, credential-bearing, or malformed endpoint host is not allowed.")
    # Brackets are an authority syntax, not part of a stored IPv6 host.
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        pass
    if ":" in value or "[" in value or "]" in value:
        raise NetworkPolicyError("Malformed endpoint IP address.")
    try:
        normalized = value.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError:
        raise NetworkPolicyError("Malformed endpoint hostname.") from None
    if len(normalized) > 253 or not normalized or value.startswith("."):
        raise NetworkPolicyError("Malformed endpoint hostname.")
    labels = normalized.split(".")
    if not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", part) for part in labels):
        raise NetworkPolicyError("Malformed endpoint hostname.")
    if re.fullmatch(r"[0-9.]+", normalized):
        raise NetworkPolicyError("Ambiguous numeric endpoint host; use a complete IP address.")
    return normalized


def _port(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise NetworkPolicyError("Endpoint port must be an integer from 1 to 65535.")
    if isinstance(value, str) and not re.fullmatch(r"[0-9]+", value):
        raise NetworkPolicyError("Endpoint port must be an integer from 1 to 65535.")
    number = int(value)
    if not 1 <= number <= 65535:
        raise NetworkPolicyError("Endpoint port must be an integer from 1 to 65535.")
    return number


def _endpoint(host: Any, port: Any) -> Endpoint:
    return _host(host), _port(port)


def _url_endpoint(value: Any, *, default_scheme: str | None = None) -> Endpoint:
    """Discard paths/queries without retaining credentials in errors or notes."""
    if not isinstance(value, str) or not value or any(c.isspace() or ord(c) < 32 for c in value):
        raise NetworkPolicyError("An HTTP endpoint must be a valid HTTP(S) URL.")
    if "\\" in value:
        raise NetworkPolicyError("Backslashes are not allowed in an endpoint URL.")
    if "://" not in value:
        if default_scheme is None:
            raise NetworkPolicyError("An HTTP endpoint requires an explicit HTTP(S) scheme.")
        value = default_scheme + "://" + value
    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() not in ("http", "https") or parsed.username is not None or parsed.password is not None:
            raise NetworkPolicyError("HTTP endpoint URLs cannot contain user information or a non-HTTP scheme.")
        host = parsed.hostname
        port = parsed.port
    except ValueError:
        raise NetworkPolicyError("Malformed HTTP endpoint URL.") from None
    return _endpoint(host, port if port is not None else (443 if parsed.scheme.lower() == "https" else 80))


def parse_extra_endpoint(value: str) -> Endpoint:
    """Parse an operator's exact host:port permission, never a subnet/pattern.

    HTTP(S) URLs are accepted only as an authority, with an explicit port.
    Paths, query strings and fragments are rejected to avoid suggesting that
    this endpoint policy enforces a narrower URL-path permission.
    """
    if not isinstance(value, str) or not value or value != value.strip() or any(c.isspace() or ord(c) < 32 for c in value):
        raise NetworkPolicyError("--network-allow requires an exact host:port endpoint.")
    if "\\" in value:
        raise NetworkPolicyError("--network-allow cannot contain a backslash.")
    try:
        parsed = urlsplit(value if "://" in value else "//" + value)
        if parsed.scheme and parsed.scheme not in ("http", "https"):
            raise NetworkPolicyError("--network-allow supports HTTP(S) endpoints only.")
        if parsed.username is not None or parsed.password is not None or parsed.path or parsed.query or parsed.fragment:
            raise NetworkPolicyError("--network-allow cannot contain user information, a path, a query or a fragment.")
        if parsed.port is None:
            raise NetworkPolicyError("--network-allow requires an explicit port.")
        return _endpoint(parsed.hostname, parsed.port)
    except ValueError:
        raise NetworkPolicyError("--network-allow requires an exact host:port with no wildcard or user information.") from None


def _mapping(value: Any, description: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise NetworkPolicyError(f"{description} must be a mapping.")
    return value


def _read_config(path: Path) -> Mapping[str, Any]:
    try:
        return _mapping(yaml.safe_load(path.read_text(encoding="utf-8")), "Task configuration")
    except Exception:
        # YAML errors may echo a line containing a password. Do not chain them.
        raise NetworkPolicyError("Unable to read the trusted task configuration.") from None


def _destination_config(path: Path, config: Mapping[str, Any], destination: str) -> dict[str, Any]:
    section = _mapping(config.get(destination), "Destination configuration")
    result = dict(_mapping(section.get("config"), "Destination connection configuration"))
    credential_path = path.parent / f"{destination}_credential.json"
    if credential_path.is_file():
        try:
            credentials = dict(_mapping(json.loads(credential_path.read_text(encoding="utf-8")), "Destination credentials"))
        except Exception:
            raise NetworkPolicyError("Unable to read trusted destination credentials.") from None
        # Match warehouse._load_destination_config's connection-role and
        # warehouse semantics; preserve the task database/schema.
        if destination == "snowflake":
            if credentials.get("role"):
                result["_connection_role"] = credentials["role"]
            if credentials.get("warehouse"):
                result["_connection_warehouse"] = credentials["warehouse"]
            for name in ("role", "warehouse", "database", "schema"):
                credentials.pop(name, None)
        else:
            if credentials.get("database"):
                result["_connection_database"] = credentials["database"]
            for name in ("database", "schema"):
                credentials.pop(name, None)
        result.update(credentials)
    return result


def discover_snowflake_endpoints(config: Mapping[str, Any]) -> list[Endpoint]:
    """Read the account's exact deployment, OCSP and stage endpoint list.

    Patch this function in offline tests. No wildcard fallback is permitted:
    Only SQL transport types are selected; optional services and their
    wildcard entries are not granted. Discovery errors, malformed selected
    endpoints, or results without a SQL deployment abort policy construction.
    Connection arguments follow common.warehouse's trusted host connection.
    """
    user = config.get("user") or config.get("username")
    if not user or not config.get("account") or not config.get("password"):
        raise NetworkPolicyError("Snowflake endpoint discovery requires trusted account, user and password configuration.")
    kwargs = {"account": config["account"], "user": user, "password": config["password"]}
    warehouse = config.get("_connection_warehouse") or config.get("warehouse")
    role = config.get("_connection_role")
    if warehouse:
        kwargs["warehouse"] = warehouse
    if role:
        kwargs["role"] = role
    try:
        import snowflake.connector

        with snowflake.connector.connect(**kwargs) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT SYSTEM$ALLOWLIST()")
                row = cursor.fetchone()
        entries = json.loads(row[0]) if row and isinstance(row[0], str) else (row[0] if row else None)
        if not isinstance(entries, list) or not entries:
            raise ValueError("Empty allowlist")
        result = []
        has_deployment = False
        for entry in entries:
            if not isinstance(entry, Mapping):
                raise ValueError("Malformed allowlist entry")
            endpoint_type = entry.get("type")
            if not isinstance(endpoint_type, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]*", endpoint_type):
                raise ValueError("Malformed allowlist type")
            if endpoint_type not in _SNOWFLAKE_SQL_TRANSPORT_TYPES:
                # Unknown future services also receive no implicit permission.
                continue
            result.append(_endpoint(entry["host"], entry["port"]))
            has_deployment |= endpoint_type in _SNOWFLAKE_SQL_DEPLOYMENT_TYPES
        if not has_deployment:
            raise ValueError("Missing SQL deployment endpoint")
        return sorted(set(result))
    except Exception:
        # Connector errors can carry account details or credentials. No leak,
        # no guessed *.amazonaws.com or *.snowflakecomputing.com permission.
        raise NetworkPolicyError("Snowflake SYSTEM$ALLOWLIST() discovery failed; no network policy was granted.") from None


def _mongo_endpoints(value: Any) -> list[Endpoint]:
    if not isinstance(value, str) or any(c.isspace() or ord(c) < 32 for c in value):
        raise NetworkPolicyError("MongoDB requires a valid trusted connection string.")
    if not value.startswith("mongodb://"):
        # Atlas SRV records and replica-set advertised peers can change. Do not
        # guess domains/ports or grant a whole suffix for an unknown topology.
        raise NetworkPolicyError("MongoDB network policy requires explicit mongodb:// host:port seed endpoints; SRV discovery is not supported.")
    authority = value[len("mongodb://"):].split("/", 1)[0].split("?", 1)[0].rsplit("@", 1)[-1]
    if not authority:
        raise NetworkPolicyError("MongoDB connection string has no seed endpoint.")
    result = []
    for peer in authority.split(","):
        try:
            parsed = urlsplit("//" + peer)
            result.append(_endpoint(parsed.hostname, parsed.port if parsed.port is not None else 27017))
        except ValueError:
            raise NetworkPolicyError("Malformed MongoDB seed endpoint.") from None
    return result


def _source_endpoints(config: Mapping[str, Any], http: set[Endpoint], direct: set[Endpoint], notes: list[str]) -> None:
    if "Airbyte" in config:
        airbyte = _mapping(_mapping(config["Airbyte"], "Airbyte").get("config"), "Airbyte connection")
        http.add(_url_endpoint(airbyte.get("server_url")))
    if "postgres" in config:
        postgres = _mapping(_mapping(config["postgres"], "Postgres source").get("config"), "Postgres connection")
        direct.add(_endpoint(postgres.get("host"), postgres.get("port", 5432)))
    if "mongodb" in config:
        mongo = _mapping(_mapping(config["mongodb"], "MongoDB source").get("config"), "MongoDB connection")
        direct.update(_mongo_endpoints(mongo.get("connection_string")))
        notes.append("MongoDB permissions cover configured seed hosts only; additional advertised peers require a trusted explicit configuration.")
    if "aws_s3" in config:
        s3 = _mapping(config["aws_s3"], "S3 source")
        endpoint = s3.get("AWS_ENDPOINT_URL") or s3.get("endpoint")
        if endpoint:
            http.add(_url_endpoint(endpoint))
        else:
            raise NetworkPolicyError("S3 source needs an explicit trusted AWS_ENDPOINT_URL for restricted networking.")
    if "flat_files" in config:
        files = config["flat_files"]
        if not isinstance(files, list):
            raise NetworkPolicyError("Flat-file sources must be a list.")
        for item in files:
            path = _mapping(item, "Flat-file source").get("path")
            if isinstance(path, str) and path.startswith(("http://", "https://")):
                http.add(_url_endpoint(path))
            elif isinstance(path, str) and ("://" not in path or path.startswith(("file://", "s3://"))):
                continue
            else:
                raise NetworkPolicyError("Unsupported flat-file source endpoint; configure an explicit HTTP(S) source.")
        notes.append("Flat-file permissions cover configured URL hosts only; redirect destinations are not implicitly allowed.")
    if "custom_api" in config:
        source = _mapping(_mapping(config["custom_api"], "Custom API source").get("config"), "Custom API connection")
        nested = source.get("configuration", {})
        if isinstance(nested, str):
            try:
                nested = json.loads(nested)
            except (ValueError, TypeError):
                raise NetworkPolicyError("Malformed custom API configuration.") from None
        nested = _mapping(nested, "Custom API settings")
        found = False
        for settings in (source, nested):
            for key in ("url", "base_url", "api_url", "endpoint", "endpoint_url"):
                if settings.get(key):
                    http.add(_url_endpoint(settings[key]))
                    found = True
        if not found:
            notes.append("The custom API source supplies no endpoint; its connector-managed access does not grant arbitrary task-container egress.")


def _model_provider(runner: str, model: str, environ: Mapping[str, str]) -> str:
    runner = runner.lower().replace("_", "-")
    if runner in ("claude", "claude-agent"):
        if environ.get("CLAUDE_CODE_USE_BEDROCK") or environ.get("CLAUDE_CODE_USE_VERTEX"):
            provider = "custom"
        else:
            provider = "anthropic"
    elif runner in ("codex", "codex-agent", "codex-sdk", "codex-cli"):
        provider = "openai"
    elif "/" in model:
        provider = model.split("/", 1)[0].lower()
    elif model.lower().startswith("claude"):
        provider = "anthropic"
    elif model.lower().startswith(("gpt-", "o1", "o3", "o4")):
        provider = "openai"
    else:
        provider = "custom"
    return "together_ai" if provider == "together" else provider


def selected_model_api_base(
    runner: str, model: str, environ: Mapping[str, str] | None = None,
) -> str | None:
    """Return the single explicit base URL the runner must actually configure.

    OpenHands precedence is the first nonempty provider-specific variable in
    the order below, then LLM_BASE_URL, then LLM_API_BASE. The caller supplies
    this exact result as ``LLM(base_url=...)`` for both agent and condenser.
    Claude CLI only receives ANTHROPIC_BASE_URL, so its other/generic base
    variables are deliberately ignored. None means use the provider default.

    The full URL is for runner configuration only; do not log it. The audit
    policy retains only its validated host and port.
    """
    env = os.environ if environ is None else environ
    runner = runner.lower().replace("_", "-")
    if runner in ("claude", "claude-agent"):
        variables = ("ANTHROPIC_BASE_URL",)
    else:
        provider = _model_provider(runner, model, env)
        variables = {
            "anthropic": ("ANTHROPIC_BASE_URL", "ANTHROPIC_API_BASE"),
            "openai": ("OPENAI_BASE_URL", "OPENAI_API_BASE"),
            "together_ai": ("TOGETHERAI_API_BASE", "TOGETHER_API_BASE", "TOGETHER_BASE_URL"),
        }.get(provider, ()) + ("LLM_BASE_URL", "LLM_API_BASE")
    selected = next((env[name] for name in variables if env.get(name)), None)
    if selected is not None:
        _url_endpoint(selected)  # Validate without including its value in errors.
    return selected


def _llm_endpoints(runner: str, model: str, environ: Mapping[str, str], extras: Sequence[Endpoint]) -> tuple[list[Endpoint], list[str]]:
    runner = runner.lower().replace("_", "-")
    notes: list[str] = []
    provider = _model_provider(runner, model, environ)
    explicit = selected_model_api_base(runner, model, environ)
    if explicit is not None:
        notes.append("The selected explicit LLM base contributes its exact host and port only; unused alternative base variables are not permitted.")
        return [_url_endpoint(explicit)], notes
    if provider == "anthropic":
        endpoints = [("api.anthropic.com", 443)]
        if runner in ("claude", "claude-agent") and environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
            endpoints.append(("claude.ai", 443))
        return endpoints, notes
    if provider == "openai":
        if runner == "codex-cli":
            return [("api.openai.com", 443), ("chatgpt.com", 443), ("auth.openai.com", 443)], notes
        return [("api.openai.com", 443)], notes
    if provider in ("together_ai", "together"):
        # The configured Kimi K3 and GLM 5.3 runs both use together_ai, not
        # arbitrary moonshot/zai hosts inferred from their model identifiers.
        return [("api.together.xyz", 443), ("api.together.ai", 443)], notes
    if extras:
        notes.append("Unknown LLM provider: no default host was guessed; operator-supplied exact HTTP endpoints are required.")
        return [], notes
    raise NetworkPolicyError("Unknown LLM provider; specify its exact host:port with --network-allow or an explicit LLM base URL.")


def build_network_policy(
    config_path: Path,
    destination: str,
    runner: str,
    model: str,
    extra_endpoints: Sequence[str] = (),
    transform_only: bool = False,
    environ: Mapping[str, str] | None = None,
) -> NetworkPolicy:
    """Build permissions from trusted inputs; fail closed on missing endpoints.

    ``extra_endpoints`` are operator authorizations for HTTP proxy endpoints.
    They never grant arbitrary direct TCP. The caller must enforce the result
    before starting any agent-generated command and stop on any exception.
    """
    if destination not in ("snowflake", "databricks", "redshift"):
        raise NetworkPolicyError("Unsupported network-policy destination.")
    path = Path(config_path)
    extras = [parse_extra_endpoint(value) for value in extra_endpoints]
    config = _read_config(path)
    connection = _destination_config(path, config, destination)
    http: set[Endpoint] = set(extras)
    direct: set[Endpoint] = set()
    notes = ["HTTP(S) endpoints require the enforcing egress proxy; direct TCP is limited to native database protocols.", "No package registry, code-hosting site, search service, or wildcard domain is implicitly permitted."]
    if destination == "snowflake":
        try:
            discovered = discover_snowflake_endpoints(connection)
        except Exception:
            raise NetworkPolicyError("Snowflake SYSTEM$ALLOWLIST() discovery failed; no network policy was granted.") from None
        if not discovered:
            raise NetworkPolicyError("Snowflake endpoint discovery returned an empty allowlist.")
        try:
            http.update(_endpoint(host, port) for host, port in discovered)
        except (ValueError, TypeError):
            raise NetworkPolicyError("Snowflake endpoint discovery returned an invalid endpoint.") from None
        notes.append("Snowflake SQL deployment, stage and certificate endpoints were obtained from the trusted account's SYSTEM$ALLOWLIST(); other service types are excluded.")
    elif destination == "databricks":
        http.add(_url_endpoint(connection.get("hostname") or connection.get("server_hostname"), default_scheme="https"))
    else:
        direct.add(_endpoint(connection.get("host"), connection.get("port", 5439)))
    if transform_only:
        notes.append("Transformation-only mode excludes all Airbyte and source-system endpoints.")
    else:
        _source_endpoints(config, http, direct, notes)
    llm, llm_notes = _llm_endpoints(runner, model, os.environ if environ is None else environ, extras)
    http.update(llm)
    notes.extend(llm_notes)
    if extras:
        notes.append("Operator --network-allow entries authorize exact HTTP host:port pairs, not URL paths or direct TCP.")
    return NetworkPolicy(sorted(http), sorted(direct), notes)

"""Destination-specific behavior shared by every ELT-Bench agent.

The task's generated ``config.yaml`` is the source of truth for database and
schema names.  Credentials are loaded from a host-side JSON file when present,
then overlaid on the destination config.  Agent runners should call
``prepare_destination`` before copying task files into their workspace.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class DestinationSpec:
    name: str
    display_name: str
    inputs_dir: str
    benchmark_dir: str
    sync_delay_seconds: int


DESTINATIONS: dict[str, DestinationSpec] = {
    "snowflake": DestinationSpec(
        name="snowflake",
        display_name="Snowflake",
        inputs_dir="inputs",
        benchmark_dir="elt-bench/snowflake",
        sync_delay_seconds=0,
    ),
    "databricks": DestinationSpec(
        name="databricks",
        display_name="Databricks",
        inputs_dir="inputs_databricks",
        benchmark_dir="elt-bench/databricks",
        sync_delay_seconds=60,
    ),
    "redshift": DestinationSpec(
        name="redshift",
        display_name="Redshift",
        inputs_dir="inputs_redshift",
        benchmark_dir="elt-bench/redshift",
        sync_delay_seconds=20,
    ),
}


def destination_choices() -> tuple[str, ...]:
    return tuple(DESTINATIONS)


def get_destination(name: str) -> DestinationSpec:
    try:
        return DESTINATIONS[name]
    except KeyError as exc:
        choices = ", ".join(destination_choices())
        raise ValueError(f"Unsupported destination {name!r}; choose one of: {choices}") from exc


def resolve_inputs_path(destination: str, path: str | Path | None = None) -> Path:
    spec = get_destination(destination)
    return Path(path).expanduser().resolve() if path else REPO_ROOT / spec.inputs_dir


def resolve_benchmark_path(destination: str, path: str | Path | None = None) -> Path:
    spec = get_destination(destination)
    return Path(path).expanduser().resolve() if path else REPO_ROOT / spec.benchmark_dir


def adapt_prompt(text: str, destination: str) -> str:
    """Adapt a Snowflake/Databricks/Redshift benchmark prompt."""
    spec = get_destination(destination)
    text = re.sub(r"\b(?:Snowflake|Databricks|Redshift)\b", spec.display_name, text)

    if spec.sync_delay_seconds:
        delay = spec.sync_delay_seconds
        delay_label = "1 minute" if delay == 60 else f"{delay} seconds"
        trigger = (
            "7. Trigger Sync Jobs One by One with Delay: Due to warehouse resource "
            f"limitations, trigger jobs one at a time with at least {delay_label} "
            f"between triggers (for example, `sleep {delay}`). Do not wait for one "
            "job to finish before triggering the next."
        )
    else:
        trigger = (
            "7. Trigger All Sync Jobs Using the Airbyte API: Use the Airbyte API "
            "with every retrieved connection ID. Refer to "
            "/workspace/documentation/trigger_job.md and use "
            "/workspace/config.yaml for the required values."
        )
    text = re.sub(r"(?m)^7\.\s.*$", trigger, text)

    if destination == "databricks" and "OAuth machine-to-machine (M2M)" not in text:
        marker = (
            "1. Initialize the DBT Project: Set up a new DBT project by configuring "
            "it with /workspace/config.yaml, and remove the example directory under "
            "the models directory."
        )
        replacement = (
            marker
            + " Use OAuth machine-to-machine (M2M) authentication and refer to "
            "databricks_authentication.md for the required configuration."
        )
        text = text.replace(marker, replacement)
    return text


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a mapping in {path}")
    return value


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def _load_destination_config(
    destination: str,
    task_input_dir: Path,
    credential_path: str | Path | None,
) -> dict[str, Any]:
    config_path = task_input_dir / "config.yaml"
    config = _read_yaml(config_path)
    try:
        destination_config = config[destination]["config"]
    except (KeyError, TypeError) as exc:
        raise ValueError(
            f"{config_path} does not contain {destination}.config"
        ) from exc
    if not isinstance(destination_config, dict):
        raise ValueError(f"{destination}.config in {config_path} must be a mapping")

    result = dict(destination_config)
    credentials: dict[str, Any] = {}
    if credential_path:
        credentials = _read_json(Path(credential_path).expanduser().resolve())
    else:
        generated_credential = task_input_dir / f"{destination}_credential.json"
        if generated_credential.is_file():
            credentials = _read_json(generated_credential)

    # A full Snowflake connection file can use an administrative role while
    # config.yaml names the Airbyte destination role that should own the
    # schema. Keep those meanings separate.
    if destination == "snowflake":
        if credentials.get("role"):
            result["_connection_role"] = credentials["role"]
        if credentials.get("warehouse"):
            result["_connection_warehouse"] = credentials["warehouse"]
        credentials = {
            key: value
            for key, value in credentials.items()
            if key not in {"role", "warehouse", "database", "schema"}
        }
    result.update(credentials)
    return result


def _require(config: Mapping[str, Any], *keys: str) -> None:
    missing = [
        key
        for key in keys
        if config.get(key) in (None, "") or str(config.get(key)).startswith("<")
    ]
    if missing:
        raise ValueError(f"Missing destination configuration: {', '.join(missing)}")


def _ansi_identifier(value: Any) -> str:
    return '"' + str(value).replace('"', '""') + '"'


def _backtick_identifier(value: Any) -> str:
    return "`" + str(value).replace("`", "``") + "`"


def prepare_destination(
    destination: str,
    task_input_dir: str | Path,
    credential_path: str | Path | None = None,
) -> str:
    """Drop and recreate the task namespace, returning its qualified name."""
    task_input_dir = Path(task_input_dir).expanduser().resolve()
    config = _load_destination_config(destination, task_input_dir, credential_path)

    if destination == "snowflake":
        return _prepare_snowflake(config)
    if destination == "databricks":
        return _prepare_databricks(config)
    if destination == "redshift":
        return _prepare_redshift(config)
    get_destination(destination)
    raise AssertionError("unreachable")


def _prepare_snowflake(config: Mapping[str, Any]) -> str:
    _require(config, "account", "password", "database", "schema")
    user = config.get("user") or config.get("username")
    if not user:
        raise ValueError("Missing destination configuration: user/username")

    import snowflake.connector

    database = _ansi_identifier(config["database"])
    schema = _ansi_identifier(config["schema"])
    role = config.get("role")
    connection_args = {
        "account": config["account"],
        "user": user,
        "password": config["password"],
    }
    connection_warehouse = config.get("_connection_warehouse") or config.get("warehouse")
    connection_role = config.get("_connection_role")
    if connection_warehouse:
        connection_args["warehouse"] = connection_warehouse
    if connection_role:
        connection_args["role"] = connection_role

    with snowflake.connector.connect(**connection_args) as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {database}")
            cursor.execute(f"DROP SCHEMA IF EXISTS {database}.{schema} CASCADE")
            cursor.execute(f"CREATE SCHEMA {database}.{schema}")
            if role:
                role_identifier = _ansi_identifier(role)
                cursor.execute(
                    f"GRANT OWNERSHIP ON SCHEMA {database}.{schema} "
                    f"TO ROLE {role_identifier}"
                )
    return f"{config['database']}.{config['schema']}"


def _prepare_databricks(config: Mapping[str, Any]) -> str:
    _require(
        config,
        "hostname",
        "http_path",
        "client_id",
        "secret",
        "database",
        "schema",
    )

    from databricks import sql
    from databricks.sdk.core import Config, oauth_service_principal

    hostname = str(config["hostname"]).removeprefix("https://")
    oauth_config = Config(
        host=f"https://{hostname}",
        client_id=config["client_id"],
        client_secret=config["secret"],
    )

    def credential_provider():
        return oauth_service_principal(oauth_config)

    catalog = _backtick_identifier(config["database"])
    schema = _backtick_identifier(config["schema"])
    with sql.connect(
        server_hostname=hostname,
        http_path=config["http_path"],
        credentials_provider=credential_provider,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"DROP SCHEMA IF EXISTS {catalog}.{schema} CASCADE")
            cursor.execute(f"CREATE SCHEMA {catalog}.{schema}")
    return f"{config['database']}.{config['schema']}"


def _prepare_redshift(config: Mapping[str, Any]) -> str:
    _require(config, "host", "port", "database", "password", "schema")
    user = config.get("user") or config.get("username")
    if not user:
        raise ValueError("Missing destination configuration: user/username")

    import redshift_connector

    schema = _ansi_identifier(str(config["schema"]).lower())
    with redshift_connector.connect(
        host=config["host"],
        port=int(config["port"]),
        database=config["database"],
        user=user,
        password=config["password"],
    ) as connection:
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
            cursor.execute(f"CREATE SCHEMA {schema}")
    return f"{config['database']}.{str(config['schema']).lower()}"

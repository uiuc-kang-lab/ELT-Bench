import argparse
import json
import shutil
from pathlib import Path

import yaml


SCRIPT_DIR = Path(__file__).resolve().parent

DESTINATIONS = {
    "snowflake": {
        "default_dest": SCRIPT_DIR.parent / "inputs",
        "credential": SCRIPT_DIR / "destination/snowflake_credential.json",
        "config_fields": ("account",),
        "output_fields": {
            "account": "account",
            "user": "user",
            "password": "password",
        },
    },
    "databricks": {
        "default_dest": SCRIPT_DIR.parent / "inputs_databricks",
        "credential": SCRIPT_DIR / "destination/databricks_credential.json",
        "config_fields": (
            "database",
            "hostname",
            "client_id",
            "secret",
            "http_path",
        ),
        "output_fields": {
            "hostname": "hostname",
            "http_path": "http_path",
            "client_id": "client_id",
            "secret": "secret",
        },
    },
    "redshift": {
        "default_dest": SCRIPT_DIR.parent / "inputs_redshift",
        "credential": SCRIPT_DIR / "destination/redshift_credential.json",
        "config_fields": (
            "host",
            "port",
            "database",
            "username",
            "password",
            "s3_bucket_name",
            "s3_bucket_region",
            "access_key_id",
            "secret_access_key",
        ),
        "output_fields": {
            "host": "host",
            "port": "port",
            "database": "database",
            "username": "username",
            "password": "password",
        },
    },
}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate ELT-Bench agent inputs for a data destination."
    )
    parser.add_argument(
        "--destination",
        choices=DESTINATIONS,
        default="snowflake",
        help="Data warehouse to generate inputs for (default: snowflake)",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        help="Output directory; defaults to the destination-specific inputs directory",
    )
    parser.add_argument(
        "--credential",
        type=Path,
        help="Credential JSON; defaults to setup/destination/<destination>_credential.json",
    )
    return parser.parse_args(argv)


def load_json(path):
    with path.open("r") as file:
        return json.load(file)


def select_fields(credentials, fields, credential_path):
    missing = sorted(set(fields.values()) - credentials.keys())
    if missing:
        raise ValueError(
            f"{credential_path} is missing required fields: {', '.join(missing)}"
        )
    return {output: credentials[source] for output, source in fields.items()}


def generate_inputs(destination, dest=None, credential_path=None):
    spec = DESTINATIONS[destination]
    source = SCRIPT_DIR.parent / "elt-bench" / destination
    shared_schemas = SCRIPT_DIR.parent / "elt-bench" / "schemas"
    dest = Path(dest) if dest is not None else spec["default_dest"]
    credential_path = (
        Path(credential_path) if credential_path is not None else spec["credential"]
    )

    if not source.is_dir():
        raise FileNotFoundError(f"Benchmark directory does not exist: {source}")
    if not shared_schemas.is_dir():
        raise FileNotFoundError(
            f"Shared benchmark schema directory does not exist: {shared_schemas}"
        )

    destination_credentials = load_json(credential_path)
    airbyte_credentials = load_json(SCRIPT_DIR / "airbyte/airbyte_credential.json")
    missing_config_fields = sorted(
        set(spec["config_fields"]) - destination_credentials.keys()
    )
    if missing_config_fields:
        raise ValueError(
            f"{credential_path} is missing required fields: "
            f"{', '.join(missing_config_fields)}"
        )
    credential_output = select_fields(
        destination_credentials,
        spec["output_fields"],
        credential_path,
    )

    databases = sorted(path for path in source.iterdir() if path.is_dir())
    dest.mkdir(parents=True, exist_ok=True)

    for database in databases:
        output_directory = dest / database.name
        if output_directory.is_dir():
            shutil.rmtree(output_directory)
        shutil.copytree(database, output_directory)

        schema_source = shared_schemas / database.name
        if not schema_source.is_dir():
            raise FileNotFoundError(
                f"Shared schema does not exist for benchmark: {database.name}"
            )
        shutil.copytree(schema_source, output_directory / "schemas")

        config_path = output_directory / "config.yaml"
        with config_path.open("r") as file:
            config = yaml.safe_load(file)

        destination_config = config[destination]["config"]
        for field in spec["config_fields"]:
            destination_config[field] = destination_credentials[field]

        airbyte_config = config["Airbyte"]["config"]
        for field in ("password", "username", "workspace_id"):
            airbyte_config[field] = airbyte_credentials[field]
        if "custom_api" in config:
            airbyte_config["custom_api_definition_id"] = airbyte_credentials[
                "api_definition_id"
            ]

        with config_path.open("w") as file:
            yaml.safe_dump(config, file, sort_keys=False)

        with (output_directory / f"{destination}_credential.json").open("w") as file:
            json.dump(credential_output, file)

        shutil.copytree(
            SCRIPT_DIR.parent / "documentation",
            output_directory / "documentation",
        )
        shutil.copy(SCRIPT_DIR / "check_job_status.py", output_directory)
        elt_directory = output_directory / "elt"
        elt_directory.mkdir()
        shutil.copy(SCRIPT_DIR / "main.tf", elt_directory)

    return len(databases), dest


def main(argv=None):
    args = parse_args(argv)
    count, dest = generate_inputs(
        destination=args.destination,
        dest=args.dest,
        credential_path=args.credential,
    )
    print(f"Generated {count} {args.destination} input bundles in {dest}")


if __name__ == "__main__":
    main()

# Unified ELT-Bench agents

The Codex, Claude, OpenHands, and SWE-agent runners share one destination
implementation. Select the data warehouse with:

```bash
python agents/run.py codex --destination snowflake --only books
python agents/run.py claude --destination databricks --only books
python agents/run.py openhands --destination redshift --only books
python agents/run.py swe --destination snowflake --only books
```

Supported destinations are `snowflake`, `databricks`, and `redshift`.

Install the selected runner and all destination connectors:

```bash
pip install -r agents/codex_agent/requirements.txt
pip install -r agents/claude_agent/requirements.txt
pip install -r agents/openhands/requirements.txt
```

For SWE-agent, install the local package as described in
`agents/SWE-agent/README.md`, then install `PyYAML`,
`snowflake-connector-python`, `databricks-sql-connector`, `databricks-sdk`,
and `redshift-connector`.

Build the three-destination execution image for Codex, Claude, and SWE-agent:

```bash
docker build -t elt-swe agents/SWE-agent/docker/elt-swe
```

OpenHands needs its agent server in the same image:

```bash
docker build -t elt-swe agents/openhands/elt-swe-openhands
```

By default, each destination uses its generated input and benchmark folders:

| Destination | Inputs | Tasks |
| --- | --- | --- |
| Snowflake | `inputs/` | `elt-bench/snowflake/` |
| Databricks | `inputs_databricks/` | `elt-bench/databricks/` |
| Redshift | `inputs_redshift/` | `elt-bench/redshift/` |

Use `--test_path` or `--elt_bench` to override these paths. Use
`--credential /path/to/credential.json` to override the credential JSON in
each generated task directory.

Before a task starts, the runner reads that task's `config.yaml` and resets
the configured namespace. The separate `*_credential.json` file is used by
the host-side reset and is not copied into the agent workspace; the generated
`config.yaml` still contains the connection values required to build the
pipeline. Run
`python setup/write_config.py --destination <destination>` first if the input
folders have not been generated.

Each agent can also be run directly from its own directory. Run its `run.py
--help` (or `run_elt.py --help` for SWE-agent) for model, output, task
selection, and overwrite options. Results are separated by agent and
destination under `agents/output/`; logs are stored under `agents/logs/`.

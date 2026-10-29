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
pip install -r agents/codex_agent/requirements.txt   # exact pins; use a Python 3.12 env
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
selection, and overwrite options. The Codex, Claude and OpenHands runners
write results to `<agent dir>/output/` and logs to `<agent dir>/logs/`.

Those three runners share these behaviors:

- `--database NAME`: one shared database (Snowflake; default `elt`) with one
  schema per task, the layout the evaluator expects.
- The task container runs as the host user; Codex and OpenHands mount
  `/workspace` read-only except `/workspace/elt` (Claude guards Write/Edit
  with a hook).
- A failed warehouse reset aborts the task. `result.json` records a `status`;
  attempts the agent ended (`success`, `error_max_turns`, plus `stuck` for
  OpenHands) are kept, others (API errors, crashes) are rerun by the next
  invocation without `--overwrite`.
- `--shard K/N` splits the tasks across N parallel processes.

## Restricted networking for Claude and OpenHands

Claude and OpenHands default to `--network-access restricted`. The task container
can contact only its selected model API and declared task services. Public code,
search, benchmark and ground-truth hosts are not implicitly allowed. The runner
installs and verifies IPv4 and IPv6 firewall rules **before** starting the agent;
installation failure aborts the task. Clearing proxy variables or using raw
TCP/IP does not remove these rules. Containers drop all Linux capabilities and
cannot change their firewall.

This requires a local Linux Docker daemon, a Docker bridge, and host permission
to use `nsenter`, `iptables-restore/save` and `ip6tables-restore/save` (non-root
runners use `sudo -n`). The rules apply only inside the newly created task
container's network namespace. Existing services and the host firewall are not
modified. Other agent runners have not been migrated to this policy.

Prepare dependencies before evaluation. From the repository root, build an
offline layer on the exact agent image used for your experiment:

```bash
docker build --build-arg BASE_IMAGE=elt-swe-openhands \
  -f agents/common/offline-deps.Dockerfile \
  -t elt-swe-openhands:restricted agents/common
docker build --build-arg BASE_IMAGE=elt-swe-claude \
  -f agents/common/offline-deps.Dockerfile \
  -t elt-swe-claude:restricted agents/common

# Preserve the SDK/CLI versions used for Kimi K3 and newer Claude models.
docker build --build-arg BASE_IMAGE=elt-swe-openhands:kimi-k3 \
  -f agents/common/offline-deps.Dockerfile \
  -t elt-swe-openhands:kimi-k3-restricted agents/common
docker build --build-arg BASE_IMAGE=elt-swe-claude:2.1.287 \
  -f agents/common/offline-deps.Dockerfile \
  -t elt-swe-claude:2.1.287-restricted agents/common
```

These builds download only the pinned Airbyte Terraform provider (`0.6.5`) and
generic dbt-utils macros (`1.3.0`). Task-time package downloads remain blocked.
Terraform uses `/opt/elt/terraform.rc` and its filesystem mirror with no public
registry fallback. For dbt-utils, use a local dependency on `/opt/elt/dbt_utils`
in `packages.yml`. Full-ELT runs check the mirror before resetting a warehouse
namespace. Transformation-only runs do not require the Terraform mirror.

The default images in restricted mode are `elt-swe-openhands:restricted` and
`elt-swe-claude:restricted`. Use `--image` for a prepared variant. Use a new
`--suffix` or output directory for the new experiment: results without matching
network metadata cannot be silently reused. For example:

```bash
python agents/run.py claude --destination snowflake --only books \
  --image elt-swe-claude:2.1.287-restricted --suffix restricted-v1
```

Each task writes `network_policy.json` containing the resolved endpoint list,
firewall verification and up to 1,000 recent proxy events (host, port, method and
outcome; no request bodies or authentication headers). `result.json` records
the requested network mode. Snowflake SQL transport endpoints come from the task
account's `SYSTEM$ALLOWLIST()`; optional app, UI, registry and telemetry endpoints
are excluded, including wildcard app hosts. This uses the account available to the agent, not separate
host-only reset credentials. Explicit model base URLs must agree with the
runtime: OpenHands uses the selected provider's base URL variable, then
`LLM_BASE_URL`/`LLM_API_BASE`; Claude uses `ANTHROPIC_BASE_URL` only.

For a required additional HTTP service, an operator can pass
`--network-allow hostname:port`; wildcards and subnet grants are rejected. Do
not add GitHub, Hugging Face or another answer source as a dependency workaround.
`--network-access unrestricted` explicitly reproduces historical networking and
selects the original default image when `--image` is omitted.

This controls **direct task-container egress**, not the permissions of allowed
services. Airbyte connectors and other permitted services retain their upstream
access; preventing their use as indirect relays also requires service-side
restrictions. HTTPS tunnels check their destination and TLS SNI without
decrypting requests, so they cannot enforce URL paths inside an allowed host.

Run the network tests without calling a model or warehouse:

```bash
python -m unittest discover -s tests -p 'test_network_*.py'
# Requires the local Docker bridge and namespace/firewall permissions above.
python tests/network_guard_smoke.py --report /tmp/elt-network-smoke.json
python tests/runner_network_smoke.py --report /tmp/elt-runner-network-smoke.json
```

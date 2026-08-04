# OpenHands Agent for ELT-Bench

Drives an OpenHands agent against ELT-Bench tasks using the
[`openhands-sdk`](https://pypi.org/project/openhands-sdk/) Python SDK.
Uses one Docker container per task, copies the selected destination's input
bundle into the mount point, and resets that warehouse namespace before each
run. The agent runs on the host with its workspace set
to the mount dir — file-editing tools (`str_replace_editor` / `file_editor`)
write locally (the changes appear in the container at `/workspace`), and a
custom `container_bash` tool execs into the task container for
terraform / dbt / python / psql work. The default `execute_bash` tool is
NOT registered, so the agent cannot run commands on the host.

## Setup

```bash
conda create -n openhands_eltbench python=3.12 -y
conda activate openhands_eltbench

# Install openhands-sdk and openhands-tools at matching versions.
# They are separate PyPI packages and MUST be the same version — tools 1.19.x
# imports symbols (e.g. openhands.sdk.utils.path) that exist only in sdk 1.19.x.
pip install -r requirements.txt

# Auth — provider key consumed by LiteLLM. Either:
export LLM_API_KEY=sk-ant-...
# or one of these (checked as fallbacks):
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
```

If you upgrade later, upgrade both packages together (`pip install -U
openhands-sdk openhands-tools`) — installing only one will break imports.

Before first run, make sure the ELT-Bench setup is complete (Docker network
`elt-docker_elt_network`, image `elt-swe`, Airbyte, and generated destination
inputs). See the top-level `../../README.md`.

## Run

```bash
# Snowflake
python run.py --destination snowflake --model anthropic/claude-opus-4-7

# Databricks, one task
python run.py --destination databricks --only books

# Redshift, rerun an existing result
python run.py --destination redshift --only books --overwrite
```

The `--model` flag takes a LiteLLM-style `provider/model` string
(e.g. `anthropic/claude-opus-4-7`, `openai/gpt-4o`).

Results go to
`../output/openhands-<model>-<suffix>-<destination>/<db>/openhands/result.json`
(with `stats.json` alongside), and logs go to `../logs/openhands/`.

## Evaluation

Use the top-level evaluation scripts and select the same destination as the
agent run. See `../../README.md` for the current evaluation command.

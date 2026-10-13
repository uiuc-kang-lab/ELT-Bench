# OpenHands Agent for ELT-Bench

Drives an OpenHands agent against ELT-Bench tasks using the
[`openhands-sdk`](https://pypi.org/project/openhands-sdk/) Python SDK.
Uses one Docker container per task: the selected destination's input bundle
is copied into the mount point, the task is pointed at its own schema in a
shared database (`--database`), and that warehouse namespace is reset before
each run.

The OpenHands `agent-server` runs **inside** the task container (image
`elt-swe-openhands`), so all agent tools (`file_editor`, `terminal`, `grep`,
`glob`) execute in the container and see only `/workspace`; the host process
only drives the LLM conversation through `RemoteWorkspace`. The container
runs as the host user, `/workspace` is mounted read-only except for
`/workspace/elt` (the only place the task allows changes), and the
agent-server is published on a free `127.0.0.1` port per task.

## Setup

```bash
# conda-forge avoids the Anaconda default-channel ToS prompt
conda create -n openhands_eltbench -c conda-forge --override-channels python=3.12 -y
conda activate openhands_eltbench

# Install openhands-sdk and openhands-tools at matching versions.
# They are separate PyPI packages and MUST be the same version — tools 1.19.x
# imports symbols (e.g. openhands.sdk.utils.path) that exist only in sdk 1.19.x.
# lmnr is pinned to 0.7.52: sdk 1.19.1 passes `rollout_entrypoint` to
# lmnr's observe(), which lmnr removed in 0.7.53.
pip install -r requirements.txt

# Build the agent image (needs the same pins; see elt-swe-openhands/Dockerfile)
docker build -t elt-swe-openhands elt-swe-openhands

# Auth — provider key consumed by LiteLLM inside the container. Either
export LLM_API_KEY=sk-ant-...
# or the provider's own variable for the chosen --model:
export ANTHROPIC_API_KEY=sk-ant-...   # anthropic/... models
export OPENAI_API_KEY=sk-...          # openai/... models
```

The key is passed into the container by name, so it does not appear in the
host process list. Another provider's key is never used as a fallback.

If you upgrade later, upgrade both packages together (`pip install -U
openhands-sdk openhands-tools`) — installing only one will break imports.

Before first run, make sure the ELT-Bench setup is complete (Docker network
`elt-docker_elt_network`, Airbyte, and generated destination inputs). See the
top-level `../../README.md`.

## Run

```bash
# Snowflake: one shared database, one schema per task
python run.py --destination snowflake --database openhands_test --model anthropic/claude-opus-4-7

# Databricks, one task
python run.py --destination databricks --only books

# Redshift, rerun an existing result
python run.py --destination redshift --only books --overwrite

# Three runner processes in parallel (disjoint task slices)
for k in 0 1 2; do
  nohup python run.py --destination snowflake --database openhands_test --shard $k/3 \
    > logs/batch-shard$k.out 2>&1 &
done
```

The `--model` flag takes a LiteLLM-style `provider/model` string
(e.g. `anthropic/claude-opus-4-7`, `openai/gpt-4o`).

Results go to
`output/openhands-<model>-<suffix>-<destination>/<db>/openhands/result.json`
(with `stats.json` alongside), and logs go to `logs/`, both under this
directory.

`result.json` records a `status`: `success`, `error_max_turns` and `stuck`
(the agent itself ended the attempt) are kept; `error` / `exception`
(LLM/API failures, crashes) are rerun automatically by the next invocation
without `--overwrite`. A failed warehouse reset aborts the task before the
agent starts.

## Evaluation

Use the top-level evaluation scripts and select the same destination and
`--database` as the agent run. See `../../README.md` for the current
evaluation command.

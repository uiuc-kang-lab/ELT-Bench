# Reproducing the ELT-Bench++ experiments

This guide explains how to rerun the agents evaluated in the ELT-Bench++ paper
on Snowflake, Databricks and Amazon Redshift. It covers:

- the environment that the agents need and the exact command for each agent in
  Table 4 (Sections 1 and 2);
- how a run is evaluated (Section 3);
- how the numbers in Table 4 are computed from the evaluation output
  (Section 4);
- the transformation-only case study in Tables 7 and 8 (Section 5);
- the mutation test of the Stage 2 verifier in Table 1 (Section 6);
- the analysis programs behind Tables 6 and 10 (Section 7).

## 1. Before running an agent

Complete the setup in the top-level [README](README.md) first:

1. Docker, Conda and `psql` are installed.
2. Airbyte runs locally through `abctl`. Our runs used Airbyte 1.5.1.
3. The **Elt** custom source is published, and
   `setup/airbyte/airbyte_credential.json` is filled in
   (`python setup/setup_airbyte.py`).
4. The destination credential is filled in:
   `setup/destination/<warehouse>_credential.json`.
5. `bash setup/elt_setup.sh` has started the source services and loaded their
   data. The services are PostgreSQL, MongoDB, LocalStack S3 and the REST API,
   on the Docker network `elt-docker_elt_network`.
6. The per-task inputs are generated for each warehouse you evaluate:
   `python setup/write_config.py --destination <warehouse>`. The output goes to
   `inputs/`, `inputs_databricks/` or `inputs_redshift/`.
7. For the Claude and OpenHands runners, the user who runs them has
   passwordless `sudo` (`sudo -n`) for `nsenter`, `iptables-save`,
   `iptables-restore`, `ip6tables-save` and `ip6tables-restore`.

The generated inputs contain credentials. Do not commit them.

The paper used the same warehouse configuration for every agent:

| Warehouse | Configuration |
|---|---|
| Snowflake | X-Small, single-cluster warehouse |
| Databricks | 2X-Small SQL warehouse, autoscaling from 1 to 5 clusters |
| Amazon Redshift | Redshift Serverless workgroup with 8 RPUs |

## 2. Running the agents (Table 4)

### 2.1 Agents and models

Every agent runs through one entry point:

```bash
python agents/run.py <runner> --destination {snowflake|databricks|redshift} [runner options]
```

| Agent in Table 4 | `<runner>` | Model (`--model`) | Task image | API credential |
|---|---|---|---|---|
| OpenHands Agent (Kimi K3) | `openhands` | `together_ai/moonshotai/Kimi-K3` | `elt-swe-openhands:kimi-k3-restricted` | `TOGETHER_API_KEY` |
| Claude Agent (Opus 4.7) | `claude` | `claude-opus-4-7` (default) | `elt-swe-claude:restricted` | `CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_API_KEY` |
| OpenHands Agent (GLM-5.3) | `openhands` | `together_ai/zai-org/GLM-5.3` | `elt-swe-openhands:restricted` | `TOGETHER_API_KEY` |
| OpenHands Agent (GPT-5.4) | `openhands` | `openai/gpt-5.4-2026-03-05` (default) | `elt-swe-openhands:restricted` | `OPENAI_API_KEY` |
| JoyAgent (GPT-5.4) | `joyagent` | `gpt-5.4-2026-03-05` | `elt-swe-joyagent` + `joyagent-genie` | `OPENAI_API_KEY` |
| Codex Agent (GPT-5.4) | `codex` | `openai/gpt-5.4-2026-03-05` (default) | `elt-swe` | `OPENAI_API_KEY` |
| SWE-Agent (GPT-5.4) | `swe` | `gpt-5.4-2026-03-05` | `elt-swe` | `OPENAI_API_KEY` |
| DeepAnalyze (DeepAnalyze-8B) | `deepanalyze` | `DeepAnalyze-8B` (default; self-hosted) | `elt-swe` | none |

**Settings that hold for all agents**

- **Turn limit.** Each task is limited to 100 turns (`--max_turns 100`, the
  default), with these differences:
  - JoyAgent counts the tool calls of its execution agent.
  - DeepAnalyze counts executed code blocks. A run also ends when the context
    is full, because the history is never truncated or summarized.
  - SWE-Agent has no turn limit. A task ends at its per-task cost limit
    (`--cost-limit`, default 6.0 USD).
- **Sync delay.** On Databricks and Redshift, the task prompt tells the agent
  to wait at least one minute between Airbyte sync triggers. The runners add
  this rule automatically.
- **Reasoning effort.** We used each harness's default unless noted below:

| Agent | Effort |
|---|---|
| Claude Agent (Opus 4.7) | `xhigh` (the CLI default for Opus 4.7, adaptive thinking) |
| OpenHands, all models | `high` (the SDK default) |
| JoyAgent | `high` (set explicitly) |
| Codex Agent, SWE-Agent | No reasoning field is sent, so `gpt-5.4-2026-03-05` uses `none`. |
| DeepAnalyze | Not applicable |

### 2.2 Common runner options

**Warehouse namespace**

- **Snowflake:** all tasks of a run share one database (`--database`), with one
  schema per task. Give each run its own database, for example
  `--database openhands_gpt54`. The default is `elt`, and two runs that share a
  database drop each other's schemas.
- **Databricks and Redshift:** each run gets its own catalog (Databricks) or
  database (Redshift), named after the experiment id. `--database` is optional.

**Experiment id and outputs**

- The experiment id is `<runner>-<model>-<suffix>-<warehouse>`. The default
  suffix is `eltbench`; set another with `--suffix`.
- Results go to `agents/<runner dir>/output/<experiment id>/<task>/` and logs to
  `agents/<runner dir>/logs/`.
- SWE-Agent writes outputs to `agents/output/` and trajectories to
  `agents/SWE-agent/trajectories/`.
- Each task has a `result.json` with the final status, the number of turns and
  the cost.

**Task status and reruns**

- A task the agent ended itself is kept. These statuses are kept:
  - `success` and `error_max_turns` (all runners);
  - `stuck` and `error_tool_parse` (OpenHands);
  - `error_context_length` and `error_max_tokens` (DeepAnalyze).
- A task cut short by infrastructure (API errors, crashes) is rerun the next
  time you run the same command.
- `--overwrite` reruns every task.

**Task selection and parallelism**

- `--only a,b,c` runs selected tasks.
- `--shard K/N` runs a disjoint slice (start N processes with K = 0..N-1).
- On Databricks, use one or two processes.

### 2.3 Build the images

Run the following from the repository root:

```bash
# Base task image (Codex Agent, SWE-Agent, DeepAnalyze; base of the Claude and JoyAgent images)
docker build -t elt-swe agents/SWE-agent/docker/elt-swe

# Claude Agent (pins Claude Code CLI 2.1.119)
docker build -t elt-swe-claude agents/claude_agent/elt-swe-claude

# OpenHands Agent (openhands-sdk, -tools and -agent-server 1.19.1)
docker build -t elt-swe-openhands agents/openhands/elt-swe-openhands
# Kimi K3 variant: sends reasoning_content back on every turn (preserved thinking)
docker build -t elt-swe-openhands:kimi-k3 \
  -f agents/openhands/elt-swe-openhands/Dockerfile.kimi-k3 agents/openhands/elt-swe-openhands

# JoyAgent: task container with an MCP tool server, and the JoyAgent services
docker build -t elt-swe-joyagent agents/joyagent/elt-swe-joyagent
docker build -t joyagent-genie agents/joyagent/genie

# Images used by the Claude and OpenHands runners
docker build --build-arg BASE_IMAGE=elt-swe-claude \
  -f agents/common/offline-deps.Dockerfile -t elt-swe-claude:restricted agents/common
docker build --build-arg BASE_IMAGE=elt-swe-openhands \
  -f agents/common/offline-deps.Dockerfile -t elt-swe-openhands:restricted agents/common
docker build --build-arg BASE_IMAGE=elt-swe-openhands:kimi-k3 \
  -f agents/common/offline-deps.Dockerfile -t elt-swe-openhands:kimi-k3-restricted agents/common
```

### 2.4 Python environments

| Runner | Python | Install |
|---|---|---|
| `openhands` | 3.12 | `pip install -r agents/openhands/requirements.txt` (openhands-sdk 1.19.1) |
| `claude` | 3.10+ (we used 3.14) | `pip install -r agents/claude_agent/requirements.txt` (we used claude-agent-sdk 0.2.162) |
| `codex` | 3.12 | `pip install -r agents/codex_agent/requirements.txt` (exact pins: openai-agents 0.23.1, litellm 1.83.0) |
| `swe` | 3.11 | `pip install -e agents/SWE-agent` plus the connectors below (we used SWE-agent 1.0.0, SWE-ReX 1.4.0, litellm 1.105.1) |
| `joyagent`, `deepanalyze` | 3.12 | `pip install -r agents/<runner>/requirements.txt` plus the connectors below |

**Connectors.** Runs on Databricks and Redshift also need
`databricks-sql-connector`, `databricks-sdk` and `redshift-connector` in the
runner's environment. The `openhands`, `claude` and `codex` requirement files
already include them. Install them yourself for `swe`, `joyagent` and
`deepanalyze`.

### 2.5 Commands per agent

The examples below use Snowflake. For Databricks or Redshift, change
`--destination` and drop `--database`. Add `--shard K/N` to run several
processes.

#### OpenHands Agent (GPT-5.4, GLM-5.3, Kimi K3)

```bash
# GPT-5.4
export OPENAI_API_KEY=...
python agents/run.py openhands --destination snowflake --database openhands_gpt54

# GLM-5.3
export TOGETHER_API_KEY=...
python agents/run.py openhands --destination snowflake --database openhands_glm53 \
  --model together_ai/zai-org/GLM-5.3

# Kimi K3 (needs its own image)
export TOGETHER_API_KEY=...
python agents/run.py openhands --destination snowflake --database openhands_kimi_k3 \
  --model together_ai/moonshotai/Kimi-K3 --image elt-swe-openhands:kimi-k3-restricted
```

OpenHands uses its built-in LLM-based condenser to manage the history. The
default image is `elt-swe-openhands:restricted`.

#### Claude Agent (Opus 4.7)

```bash
export CLAUDE_CODE_OAUTH_TOKEN=...      # from `claude setup-token`; or export ANTHROPIC_API_KEY=...
python agents/run.py claude --destination snowflake --database claude_opus
```

- The Claude Code CLI runs inside the task container. Its version is pinned by
  the image (2.1.119).
- Claude uses the SDK's file tools and automatic context compaction. Your own
  Claude Code settings, plugins and MCP servers are not loaded.
- The default image is `elt-swe-claude:restricted`.

#### Codex Agent (GPT-5.4)

```bash
export OPENAI_API_KEY=...
python agents/run.py codex --destination snowflake --database codex_gpt54
```

- The default backend `--backend sdk` is the paper's configuration: the OpenAI
  Agents SDK with the `shell` and `apply_patch` tools, running inside the task
  container.
- `--backend cli` runs the Codex CLI instead. A ChatGPT login cannot use
  `gpt-5.4` with it, so it does not reproduce the paper.

#### SWE-Agent (GPT-5.4)

```bash
export OPENAI_API_KEY=...
python agents/run.py swe --destination snowflake --database swe_gpt54 \
  --model gpt-5.4-2026-03-05 \
  --completion-kwargs '{"_skip_responses_api_bridge": true}'
```

- **`--completion-kwargs` is required with recent litellm.** litellm sends
  GPT-5.4 calls that have function tools through its Responses-API bridge.
  That bridge drops tool calls when the reply also contains text, and the
  agent then stops after a few steps.
- **Long commands.** SWE-Agent's default limit is 30 seconds per command, and
  aiohttp caps each command at 300 seconds. Long Airbyte polls can therefore
  kill the shell session. `--execution-timeout 3600` raises both limits. We
  used it when we reran 15 Databricks tasks.
- SWE-Agent keeps the 25 most recent observations
  (`agents/SWE-agent/config/elt_fc.yaml`).

#### JoyAgent (GPT-5.4)

```bash
export OPENAI_API_KEY=...
python agents/run.py joyagent --destination snowflake --database joyagent_gpt54 \
  --model gpt-5.4-2026-03-05 --responses-api --drop-params temperature \
  --extra-params '{"reasoning_effort": "high"}' --max-tokens 32768 \
  --price-in 2.5 --price-out 15 --price-cached 0.25
```

- JoyAgent runs its default plan-and-execute mode. The task tools are `bash`,
  `read_file`, `write_file` and `edit_file`, served by an MCP server in the
  task container.
- GPT-5.4 rejects function tools combined with `reasoning_effort` on
  `/chat/completions`, so `--responses-api` sends the calls to `/responses`.
- The `--price-*` flags only compute `total_cost_usd`.
- The paper uses the default variant. See
  [agents/joyagent/README.md](agents/joyagent/README.md) for the patch applied
  to JoyAgent and for the `--variant dataagent` option.

#### DeepAnalyze (DeepAnalyze-8B)

DeepAnalyze needs an OpenAI-compatible vLLM server for
[RUC-DataLab/DeepAnalyze-8B](https://huggingface.co/RUC-DataLab/DeepAnalyze-8B).
Deploy it as described in the
[DeepAnalyze repository](https://github.com/ruc-datalab/DeepAnalyze).

- Serve the model under the name `DeepAnalyze-8B`.
- Keep the model's own chat template.
- Use a context of 131072 tokens. In our trials with a 32K context, runs ran
  out of context early.

```bash
# --base-url defaults to http://127.0.0.1:18000/v1
python agents/run.py deepanalyze --destination snowflake --database deepanalyze_8b \
  --base-url http://<vllm-host>:<port>/v1
```

- The model has no tool calls. The runner executes each `<Code>` block in the
  task container (at most 100 blocks, 1800 seconds each) and returns the output
  as the `execute` turn.
- The run uses DeepAnalyze's API settings: temperature 0.4 and at most 32768
  new tokens per generation.
- See [agents/deepanalyze/README.md](agents/deepanalyze/README.md) for details.

## 3. Evaluating a run (Tables 4, 7 and 8)

Install the evaluation requirements once:

```bash
pip install -r evaluation/requirements.txt
```

### 3.1 Ground truth

Download the ground truth as described under "Download the ground truth" in
the top-level [README](README.md). This gives `ground_truth/gt_snowflake`,
`ground_truth/gt_databricks` and `ground_truth/gt_redshift`.

### 3.2 Commands

Evaluate each run on each warehouse with two commands: `eva.py`, then the
warehouse's Stage 1 content check. The examples evaluate OpenHands Agent
(GPT-5.4) from the repository root:

```bash
# Snowflake: --database is the runner's --database
python evaluation/eva.py --folder openhands_gpt54_snowflake --db-type snowflake \
  --database openhands_gpt54 --gt-folder "$PWD/ground_truth/gt_snowflake"
python evaluation/eva_stage1_stored.py evaluate --database openhands_gpt54 \
  --folder openhands_gpt54_snowflake

# Databricks: the run's catalog
python evaluation/eva.py --folder openhands_gpt54_databricks --db-type databricks \
  --database openhands_gpt_5_4_2026_03_05_eltbench \
  --gt-folder "$PWD/ground_truth/gt_databricks"
python evaluation/eva_stage1_databricks.py evaluate \
  --catalog openhands_gpt_5_4_2026_03_05_eltbench --folder openhands_gpt54_databricks

# Redshift: the run's database
python evaluation/eva.py --folder openhands_gpt54_redshift --db-type redshift \
  --database openhands_gpt_5_4_2026_03_05_eltbench \
  --gt-folder "$PWD/ground_truth/gt_redshift"
python evaluation/eva_stage1_stored_redshift.py evaluate \
  --database openhands_gpt_5_4_2026_03_05_eltbench --folder openhands_gpt54_redshift
```

**Options**

- **`--database`** is where the run wrote its task schemas: the database on
  Snowflake and Redshift, the catalog on Databricks.
  - If you gave the runner `--database`, use the same value.
  - Otherwise, on Databricks and Redshift the runner names it after the
    experiment id. It drops the `-<warehouse>` ending, lowercases the rest and
    replaces every character other than `a-z`, `0-9` and `_` with `_`. For
    example, experiment `openhands-gpt-5.4-2026-03-05-eltbench-databricks`
    writes to catalog `openhands_gpt_5_4_2026_03_05_eltbench`.
- **`--gt-folder`** must be an absolute path, as above.
- **Credentials** default to `setup/destination/<warehouse>_credential.json`.
  Use `--credential` to change this.
- **`--only a,b`** evaluates selected tasks (both commands accept it).
- **Results** go to `evaluation/agent_results/<folder>/`. Use a new folder for
  every run.

## 4. Performance and execution cost (Table 4)

Table 4 reports two success rates for each agent and warehouse:

- **SR_DEL** is the percentage of the 100 tasks that pass Stage 1, that is,
  tasks with `"passed": true` in `stage1_stored.json`.
- **SR_DT** is the percentage of the 202 data models that belong to a task
  that passed Stage 1 and have `"match": true` in `stage2.json`. Data models
  of a task that failed Stage 1 count as failures.

```python
import json
from pathlib import Path

folder = Path("evaluation/agent_results/openhands_gpt54_snowflake")
stage1 = json.loads((folder / "stage1_stored.json").read_text())["tasks"]
passed = {task for task, result in stage1.items() if result["passed"]}
stage2 = json.loads((folder / "stage2.json").read_text())
matched = sum(r.get("match") is True
              for task, models in stage2.items() if task in passed
              for r in models.values())
print(f"SR_DEL {len(passed) / 100:.2%}  SR_DT {matched / 202:.2%}")
```

It also reports the mean LLM cost and the mean number of turns per task over
the 100 tasks. A turn is one model call. Each runner records both values next
to the task's `result.json`:

| Runner | Model calls | Cost (USD) |
|---|---|---|
| `claude` | `num_turns` in `stats.json` | `total_cost_usd` in `stats.json`, as reported by the Claude Agent SDK |
| `openhands` | Distinct `llm_response_id` values among the agent's `ActionEvent` and `MessageEvent` entries in `result.json`. Parallel tool calls share one response. | `total_cost_usd` in `stats.json` |
| `codex` | `usage.requests` in `stats.json` | `total_cost_usd` in `stats.json`, priced with LiteLLM's price table |
| `swe` | `info.model_stats.api_calls` in the task's `.traj` file (`agents/SWE-agent/trajectories/`) | `info.model_stats.instance_cost` in the same file |
| `joyagent` | `usage.llm_calls` in `stats.json` | `total_cost_usd` in `stats.json`, priced with the `--price-*` flags |
| `deepanalyze` | `usage.llm_calls` in `stats.json` | Not recorded, because the model is self-hosted. The paper estimates it as (`usage.prompt_tokens` + `usage.completion_tokens`) × 0.20 USD per million tokens, Fireworks AI's rate for 4B–16B models. |

If you rerun some tasks, count each task once and use its latest run. Do not
add up the costs of earlier attempts.

## 5. Transformation-only case study (Tables 7 and 8)

Tables 7 and 8 measure SR_DT with Stage 1 held fixed. In this study, each agent
starts with the source tables already loaded and builds only the dbt models.
Each agent runs for up to 100 turns per task.

**Requirements**

- **Runners.** The `claude` and `openhands` runners support this mode, on
  Snowflake only, through `--source_database <db>`.
- **Source database.** `<db>` is a Snowflake database with one schema per task
  that holds that task's correctly loaded source tables. One way to get it is
  a run that passes Stage 1 on all 100 tasks (Section 3).

```bash
python agents/run.py openhands --destination snowflake --database openhands_gpt54_tonly \
  --source_database <db> --suffix eltbench-tonly

python agents/run.py claude --destination snowflake --database claude_opus_tonly \
  --source_database <db> --suffix eltbench-tonly

# GLM-5.3 and Kimi K3 (Table 8) use the openhands runner with the models of Section 2.5
python agents/run.py openhands --destination snowflake --database openhands_kimi_k3_tonly \
  --source_database <db> --suffix eltbench-tonly \
  --model together_ai/moonshotai/Kimi-K3 --image elt-swe-openhands:kimi-k3-restricted

python evaluation/eva.py --folder openhands_gpt54_tonly --db-type snowflake \
  --database openhands_gpt54_tonly --gt-folder "$PWD/ground_truth/gt_snowflake"
```

**Benchmark versions.** The study uses six versions of the benchmark on
Snowflake: the original ELT-Bench and the snapshots after Audit Stages 1
to 5. The repairs are cumulative. Each version has its own data model
definitions, schemas and ground truth. A task that did not change from one
version to the next keeps the output from the previous version.

- **Table 7** reports SR_DT over all 202 data models for each version, for
  OpenHands Agent (GPT-5.4) and Claude Agent (Opus 4.7).
- **Table 8** compares the versions immediately before and after Audit Stage 2
  and Audit Stage 5. It adds OpenHands Agent with GLM-5.3 and with Kimi K3.
  Each comparison covers only the data models modified in that stage: 100
  for Stage 2 and 80 for Stage 5. ΔSR_DT is SR_DT after the repair minus SR_DT
  before it, both computed over that subset.

**Running an earlier version.** The Hugging Face dataset holds every version
under `versions/`: `original` and `after_stage1` to `after_stage5`. Each has
`definitions/`, `schemas/` and `gt/`. To run one, give the runner a copy of the
Snowflake inputs with that version's definitions and schemas, and evaluate
against that version's ground truth:

```bash
V=after_stage2
hf download tttjjj/elt_bench --repo-type dataset --include "versions/$V/**" --local-dir .

cp -r inputs inputs_$V
for task in $(ls inputs_$V); do
  cp versions/$V/definitions/$task/data_model.yaml inputs_$V/$task/
  rm -r inputs_$V/$task/schemas
  cp -r versions/$V/schemas/$task inputs_$V/$task/schemas
done

python agents/run.py openhands --destination snowflake --database openhands_gpt54_$V \
  --source_database <db> --suffix eltbench-tonly-$V --test_path "$PWD/inputs_$V"

python evaluation/eva.py --folder openhands_gpt54_$V --db-type snowflake \
  --database openhands_gpt54_$V --gt-folder "$PWD/versions/$V/gt"
```

## 6. Mutation testing of the Stage 2 verifier (Table 1)

[evaluation/mutation_testing/mutate.py](evaluation/mutation_testing/mutate.py)
contains the code that generates the mutants: the nine mutation operators that
are applied to a ground-truth query. We do not release the ground-truth SQL,
because it would reveal the reference solutions.

## 7. Analysis programs (Tables 6 and 10)

Two analyses use Codex with `gpt-6-astra` (reasoning effort `high`) to examine
agent runs. The repository contains the programs, prompts and schemas. It does
not contain the agent trajectories or our analysis outputs. Each directory's
README explains how to prepare the inputs, run the analysis and export the
table.

| Table | Directory | What it analyzes |
|---|---|---|
| 6 | [analysis/warehouse_semantics/](analysis/warehouse_semantics/README.md) | Final SQL, trajectories and audit replays of Claude Agent (Opus 4.7) on 100 tasks on each warehouse. It counts the data models whose output-column errors were caused by a warehouse-specific semantic. |
| 10 | [analysis/error_recovery/](analysis/error_recovery/README.md) | 500 trajectories from the runs in Table 4. It annotates failure episodes, verified recoveries and the decision turns needed to recover. |

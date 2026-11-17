# Error-recovery analysis (Table 10)

This program produces the autonomous-recovery analysis in Table 10 of the
ELT-Bench++ paper. It annotates ELT agent trajectories with Codex, using the
English prompt in [prompt.txt](prompt.txt) and a structured JSON output schema.

**What the paper analyzed**

- **Trajectories.** 500 trajectories from the runs in Table 4, 100 tasks per
  group:
  - Claude Agent (Opus 4.7) on Snowflake, Databricks and Redshift;
  - OpenHands Agent with Kimi K3 on Snowflake;
  - OpenHands Agent with GLM-5.3 on Snowflake.
- **Annotation model.** `gpt-6-astra` with reasoning effort `high` and
  provider `openai`. The runner's default effort is `ultra`, so pass
  `--effort high` as in the commands below.
- **Categories.** The recovery prompt ([prompt.txt](prompt.txt)) defines the
  seven failure categories reported in Table 10.

**Isolation.** Each trajectory uses a separate ephemeral session. Memories,
tools and multi-agent execution are disabled. The runner treats recorded ELT
commands as historical data and never executes them.

## Repository contents

| File | Purpose |
| --- | --- |
| [prompt.txt](prompt.txt) | Concise English annotation prompt |
| [single_trajectory.schema.json](single_trajectory.schema.json) | Full validation schema |
| [single_trajectory.output_schema.json](single_trajectory.output_schema.json) | Structured output schema supplied to the model |
| [single_trajectory_structured_output_template.json](single_trajectory_structured_output_template.json) | Output format example; placeholders are not annotations |
| [prepare_input.py](prepare_input.py) | Convert one raw trajectory into a sanitized input and manifest |
| [input_sanitization.py](input_sanitization.py) | Frozen v3 redaction and field-processing rules |
| [run.py](run.py) | Independent annotation, validation, and resume support |
| [aggregate.py](aggregate.py) | Validate results and calculate category statistics |
| [export_table.py](export_table.py) | Export a complete 500-trajectory table as CSV and LaTeX |
| [cohort.json](cohort.json) | Selected trajectory identities, relative source paths, and original file hashes |
| [runtime_utils.py](runtime_utils.py) | Local runtime helpers |
| [redaction.py](redaction.py) | Credential redaction rules |
| [sanitize_text.py](sanitize_text.py) | Shared text sanitization |

Raw trajectories, prepared inputs, private manifests, model outputs, and local
verification logs are not distributed with this repository. The corresponding
directories are excluded by `.gitignore`.
`cohort.json` identifies the selected files without storing workstation paths
or previous annotations.

All commands below run from this directory (`analysis/error_recovery`). Paths
are relative to it.

## Requirements

- Linux and Python 3.10 or later.
- Codex CLI installed and authenticated, with access to the selected model.
- The raw trajectory files you want to analyze.

The Python programs use only the standard library.

```bash
codex --version
codex login status
```

If your executable has a different name or location, pass it with `--codex`.
The runner explicitly selects the model, effort, and provider for each invocation
without changing global CLI settings.

## Prepare one raw trajectory

Place the raw file in a local data directory, for example
`data/opus_snowflake/asana/result.json`, then run:

```bash
python3 prepare_input.py \
  --source data/opus_snowflake/asana/result.json \
  --group opus_snowflake \
  --output-dir prepared/asana
```

The input must be a JSON object containing the original `trajectory` array.
`--task` defaults to its `db` field.

| `--group` | Agent | Warehouse |
| --- | --- | --- |
| `opus_snowflake` | Claude Opus 4.7 | Snowflake |
| `opus_databricks` | Claude Opus 4.7 | Databricks |
| `opus_redshift` | Claude Opus 4.7 | Redshift |
| `kimi_snowflake` | OpenHands Kimi K3 | Snowflake |
| `glm_snowflake` | OpenHands GLM 5.3 | Snowflake |

The converter writes the following files under the chosen output directory:

- `manifest.json`: input manifest consumed by the runner.
- `inputs/<trajectory_id>.json`: sanitized model input.
- `preparation_reports/<trajectory_id>.json`: mapping and sanitization report.

Conversion is entirely local and makes no model calls. It:

1. Computes the raw file SHA-256 and preserves the complete trajectory array in order.
2. Applies the original v3 credential redaction and ANSI cleanup rules.
3. Removes designated private reasoning and post-hoc annotation fields. Reasoning
   blocks become placeholders so array positions remain stable.
4. Pairs tool calls with their feedback and rebuilds tool and decision-turn indices.
5. Adds metadata, an input contract, and the reconstructed turn mapping.

No error filtering, summarization, truncation, or preliminary classification is
performed. Top-level completion status, result summaries, costs, and aggregate
usage fields are not copied into the model input.

Claude decisions group consecutive assistant fragments between feedback; source
entry coordinates start at 1. OpenHands decisions group actions and messages by
`llm_response_id`; source entry coordinates start at 0. Parallel actions from
one response share a turn. OpenHands `think` and `finish` actions remain
in the trajectory but do not receive external tool sequence numbers.
JSON pointer array indices always start at 0.

Missing OpenHands response IDs cause conversion to fail. Missing tool feedback
remains null and is recorded in the report. Native `num_turns` is used for
local cross-checking, not as a common turn definition across frameworks.

Use `--expected-source-sha256` to verify a previously recorded source hash.
Without it, the input contract reports `computed_before_sanitization`;
with a matching expected hash, it reports `matched_before_sanitization`.
`--compact` removes JSON indentation only.

## Check and annotate one trajectory

Check input hashes and request size without model inference:

```bash
python3 run.py \
  --manifest prepared/asana/manifest.json \
  --output-dir runs/asana \
  --concurrency 1 \
  --dry-run
```

A successful check reports `all_selected_ready: true`.
A dry run does not validate live inference or annotation semantics.

To annotate the trajectory:

```bash
python3 run.py \
  --manifest prepared/asana/manifest.json \
  --output-dir runs/asana \
  --model gpt-6-astra \
  --effort high \
  --concurrency 1 \
  --max-attempts 2 \
  --timeout 1800
```

The request contains the isolation instructions, `prompt.txt`, and exactly
one prepared input. The structured output schema is supplied separately through
the CLI. Each retry starts a new session without the previous response.

The default request limit is 1,048,576 characters. Requests that exceed this limit
are rejected before inference; they are not automatically truncated.

## Prepare and annotate the selected cohort

The selected cohort contains 100 trajectories in each of the five groups.
Acquire the raw files separately and arrange them at the relative paths listed
in [cohort.json](cohort.json). Its hashes identify the selected original files;
the repository does not download or synthesize them.

Prepare the selected files sequentially into one merged manifest:

```python
import json
import subprocess
import sys
from pathlib import Path

cohort = json.loads(Path("cohort.json").read_text())
for item in cohort["trajectories"]:
    subprocess.run(
        [
            sys.executable, "prepare_input.py",
            "--source", item["source"],
            "--group", item["group"],
            "--task", item["task"],
            "--expected-source-sha256", item["source_sha256"],
            "--output-dir", "prepared/cohort",
            "--compact",
        ],
        check=True,
    )
```

For a custom cohort, prepare your files with repeated `prepare_input.py`
invocations using the same output directory. Run preparation sequentially, or
use separate directories for parallel preparation. The runner can then annotate
the merged inputs concurrently. The cohort example uses compact JSON to reduce
request size without changing trajectory data.

Check and run the batch:

```bash
python3 run.py \
  --manifest prepared/cohort/manifest.json \
  --output-dir runs/cohort \
  --concurrency 16 \
  --dry-run

python3 run.py \
  --manifest prepared/cohort/manifest.json \
  --output-dir runs/cohort \
  --model gpt-6-astra \
  --effort high \
  --concurrency 16 \
  --max-attempts 2 \
  --timeout 1800
```

`--concurrency` limits simultaneous trajectory attempts.
`--max-attempts` limits attempts per unaccepted trajectory in this invocation.
`--timeout` limits the duration of each attempt in seconds.
Use `--limit N` or repeat `--trajectory-id` to select a smaller batch.

## Outputs and resuming

| Directory under the run output directory | Contents |
| --- | --- |
| `fresh_results/` | Validated per-trajectory annotations |
| `fresh_provenance/` | Model settings, request/output hashes, and run records |
| `fresh_attempts/` | Requests, raw responses, CLI events, errors, and attempt provenance |
| `fresh_runs/` | Batch progress and completion summaries |

Repeat the same run command to validate and reuse accepted results while retrying
failed or incomplete inputs. Completion requires `all_selected_accepted: true`.
Do not interpret missing or rejected results as zero-episode trajectories.

Two runners cannot share the same output directory concurrently. Use a new output
directory after changing the prompt, model, runner, or CLI. Incompatible protocol
hashes prevent reuse. Invalid raw outputs are retained; structural and pointer
errors are not silently repaired.

Prepared data and inference records are local experiment artifacts. They can
contain source and runtime paths and are excluded from version control.

## Aggregate and export

For a complete selected cohort:

```bash
python3 aggregate.py \
  --manifest prepared/cohort/manifest.json \
  --results runs/cohort/fresh_results \
  --provenance runs/cohort/fresh_provenance \
  --output-dir runs/cohort/aggregated

python3 export_table.py \
  --table runs/cohort/aggregated/table.json
```

For a single trajectory, a custom subset, or interim results, use
`--allow-partial`:

```bash
python3 aggregate.py \
  --manifest prepared/asana/manifest.json \
  --results runs/asana/fresh_results \
  --provenance runs/asana/fresh_provenance \
  --output-dir runs/asana/aggregated \
  --allow-partial
```

Partial tables are marked `PROVISIONAL`. Full aggregation requires 500
validated trajectories, with 100 in each group. The CSV/LaTeX exporter accepts
only a complete 500-trajectory table and refuses to overwrite existing exports.

Each cell reports:

- Number of observed failure episodes.
- Verified recovery rate, as a percentage of all included episodes.
- Mean decision-turn span among recovered episodes with known endpoints.

The span equals the recovery decision turn minus the first-failure decision turn.
Missing spans are reported separately and excluded from the mean.

Outputs include `table.txt`, `table.csv`, `table.json`,
`cohort_accounting.json`, and `validation.json`. The exporter adds
`table_wide.csv` and `table.tex`.

Add `--verify-raw-sources` to aggregation to verify the original files at the
locations recorded during preparation. Ordinary annotation and aggregation use
the prepared inputs. Their payload paths are relative to the manifest directory.

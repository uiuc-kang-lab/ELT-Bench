# Warehouse-specific semantics analysis (Table 6)

This program produces Table 6 of the ELT-Bench++ paper. Table 6 counts the
data models in which a warehouse-specific SQL semantic caused an output-column
error. It covers the 300 runs of Claude Agent (Opus 4.7): 100 tasks on each of
Snowflake, Databricks and Redshift.

The program works in three steps:

1. It builds one input per task with the evidence from all three warehouses.
2. Codex analyzes each task in an isolated session. The paper used
   `gpt-6-astra` with reasoning effort `high`. A local validator checks every
   answer before accepting it.
3. It aggregates the accepted answers and recounts each cell of Table 6 from
   the evidence they cite.

The table in the paper:

| Challenge | Snowflake | Databricks | Redshift |
|---|---:|---:|---:|
| Numeric identifier text and comparison | 1 | 7 | 7 |
| Decimal division precision | 0 | 1 | 4 |
| Integer averages | 0 | 0 | 3 |
| Default NULL ordering | 1 | 1 | 1 |
| Time-difference units | 0 | 2 | 0 |
| Trailing-space comparison | 1 | 1 | 0 |

A model can appear in more than one row, so the rows do not add up to a number
of distinct models.

## What this directory contains

The directory contains the programs, prompt, taxonomy and output schema. It
does not contain:

- the agent trajectories and final SQL;
- the audit replays, that is, the corrected SQL and the evaluation results
  before and after each correction;
- the prepared inputs, model outputs or reports of our run.

To rerun the analysis, you need your own copies of the first two.

| File | Purpose |
|---|---|
| [prompt.txt](prompt.txt) | Analysis instructions given to the model |
| [taxonomy.json](taxonomy.json) | Definitions of the six challenges |
| [single_task.output_schema.json](single_task.output_schema.json) | Structured output schema passed to the Codex CLI |
| [single_task.output_template.json](single_task.output_template.json) | Example of the output structure. Its placeholders are not expected findings. |
| [prepare_input.py](prepare_input.py) | Builds one input per task from the trajectories, final SQL, task inputs and audit replays |
| [protocol.py](protocol.py) | Validates identities, the schema, quoted evidence with line numbers, replay evidence and provenance |
| [run.py](run.py) | Analyzes each task in its own session, with input-size checks, concurrency, retries and result archiving |
| [aggregate.py](aggregate.py), [aggregate_run_set.py](aggregate_run_set.py) | Validate each run directory with its own protocol and merge non-overlapping, complete sets of tasks |
| [export_table7.py](export_table7.py) | Recomputes the table from a complete report and exports it. The name comes from an earlier draft, where this was Table 7. |
| [protocols/numbered/](protocols/numbered/), [protocols/packed/](protocols/packed/) | The same protocol with other request formats (see Step 2) |

## Challenges

| `category_id` | Row in Table 6 |
|---|---|
| `numeric_identifier` | Numeric identifier text and comparison |
| `division_precision` | Decimal division precision |
| `integer_avg` | Integer averages |
| `null_ordering` | Default NULL ordering |
| `time_units` | Time-difference units |
| `trailing_spaces` | Trailing-space comparison |

## How a model is counted

A model counts in the cell for challenge `c` and warehouse `w` when the saved
evidence shows all of the following:

1. **A matching baseline.** A replay of the model's submitted SQL reproduces
   the output that was evaluated.
2. **A full-column fix.** A corrected SQL that changes only the mechanism of
   challenge `c` makes at least one failing output column pass, under the same
   evaluator.
3. **Traceable evidence.** The corrected SQL, both scores, the fixed columns
   and the warehouse and model identities all trace back to records in the
   input.

The following do not count on their own: a failed evaluation, suspicious
syntax, a few improved cells, a changed sample of rows, or a synthetic
experiment. The model may still fail after the correction; one fixed column
is enough.

Each cell is a set of `(task_id, model_id)` pairs:

```text
F(c, w) = | direct_replay_confirmed_models(c, w) ∪ verified_downstream_models(c, w) |
```

- **Direct models** come from the sites in `sites.json` with
  `inclusion == "counted"` and `failure_attributed == true`. A model counts once
  even when it has several sites.
- **Downstream models** come from `propagated_failures.json`. A downstream
  model needs its own baseline and its own full-column fix, linked to a counted
  site of the same warehouse and challenge.

## Requirements

- Linux and Python 3.10 or later. The programs use only the standard library;
  the runner uses POSIX `fcntl`.
- The Codex CLI, logged in, with access to `gpt-6-astra`. Only Step 2 needs it.

All commands below run from this directory (`analysis/warehouse_semantics`).

## Step 1: prepare the inputs

```bash
python prepare_input.py --all \
  --audit-root <audit replay archive> \
  --trajectory-root <Claude Agent trajectories and SQL logs> \
  --inputs-root <ELT-Bench repository> \
  --output-dir prepared/cohort \
  --max-payload-characters 2097152
```

The default values of the three `--*-root` options point to the authors'
machine, so always pass all three.

The audit archive's `scoring_inventory.json` defines the tasks and models.
Each task's payload holds the evidence from all three warehouses:

| Evidence | Content |
|---|---|
| Final SQL | The final and the compiled SQL of every model (606 of each), never truncated |
| Task | Task specification, the physical types seen in the trajectory, and the source schema descriptions |
| Evaluation | The agent's output, a sample of the ground-truth CSV, the scoring records and the evaluator contract |
| Trajectory | Diagnostic SQL the agent ran, the feedback it received, and type information |
| Audit replays | Baseline, corrected SQL, scores before and after, and result samples |
| Limitations | What is missing from the payload, also listed in `preparation_reports/` |

Original and replay SQL are never truncated. The other evidence has budgets:

- CSV samples: the first 5 rows;
- trajectory evidence and query observations: 100,000 characters each;
- source schema descriptions: 60,000 characters;
- task specification: 150,000 characters.

The inputs contain no earlier labels or counts. They do contain the audit
replays, so the analysis is not a blind search of the trajectories.

## Step 2: run the analysis

The protocol exists in three request formats. They differ only in `run.py`.
The prompt, taxonomy, schema, validator and aggregation are identical.

| Format | Location |
|---|---|
| Original | this directory |
| Numbered: artifacts with visible line numbers | `protocols/numbered/` |
| Packed: numbered, with replay SQL stored as a diff | `protocols/packed/` |

For a new run, use the numbered format for 98 tasks. Use the packed format for
Mailchimp and Marketo. In the numbered format, the Mailchimp request has
1,224,447 characters, which exceeds the Codex CLI limit of 1,048,576.

**Create the two run directories.** The aggregator validates each run
directory against its own `protocol_snapshot/`, so copy the protocol there
before running:

```bash
python - <<'PY'
import copy, json, shutil
from pathlib import Path

source = Path("prepared/cohort/manifest.json").resolve()
original = json.loads(source.read_text())
groups = {
    "numbered_98": (lambda task: task not in {"mailchimp", "marketo"}, "protocols/numbered", 98),
    "packed_2": (lambda task: task in {"mailchimp", "marketo"}, "protocols/packed", 2),
}
Path("prepared/manifests").mkdir(parents=True, exist_ok=False)
for name, (wanted, protocol, count) in groups.items():
    manifest = copy.deepcopy(original)
    manifest["targets"] = [t for t in manifest["targets"] if wanted(t["task_id"])]
    assert len(manifest["targets"]) == count
    for t in manifest["targets"]:
        path = Path(t["payload_path"])
        t["payload_path"] = str(path if path.is_absolute() else (source.parent / path).resolve())
    Path(f"prepared/manifests/{name}.json").write_text(json.dumps(manifest, indent=2) + "\n")
    shutil.copytree(protocol, f"runs/{name}/protocol_snapshot")
PY
```

**Check the requests without calling the model:**

```bash
python runs/numbered_98/protocol_snapshot/run.py \
  --manifest prepared/manifests/numbered_98.json --output-dir runs/numbered_98/preflight \
  --model gpt-6-astra --effort high --concurrency 16 \
  --max-input-characters 1048576 --dry-run
```

To see the full request of one task, add
`--task donor --render-prompt donor.request.txt`. This mode also makes no
model call.

**Run the analysis.** The runner's default effort is `ultra`, so always pass
`--effort high`. Run the two groups one after the other, so that at most 16
sessions run at once.

```bash
python runs/numbered_98/protocol_snapshot/run.py \
  --manifest prepared/manifests/numbered_98.json --output-dir runs/numbered_98 \
  --model gpt-6-astra --effort high --concurrency 16 \
  --max-input-characters 1048576 --max-attempts 2

python runs/packed_2/protocol_snapshot/run.py \
  --manifest prepared/manifests/packed_2.json --output-dir runs/packed_2 \
  --model gpt-6-astra --effort high --concurrency 2 \
  --max-input-characters 1048576 --max-attempts 2
```

Each attempt runs in a new ephemeral session with an empty working directory.
Shell, apps, plugins, web, memories and sub-agents are disabled. The runner
rejects an answer if it sees a tool-call event. An answer moves to the
accepted directory only after the local validator passes. The analysis never
connects to a warehouse.

**Resuming.**

- Rerunning the same command validates and skips accepted tasks, then retries
  the others. Two runners cannot use the same directory at once.
- To analyze a task again from scratch, use a new run directory, and make sure
  each task is accepted in exactly one directory. The aggregator rejects
  overlapping sources.
- After changing the prompt, taxonomy, schema, validator, runner or inputs,
  use a new run directory.
- Failed attempts are kept under `attempts/<target>/<attempt>/`, with
  `provenance.json`, `stderr.txt` and the raw output.

## Step 3: aggregate and export Table 6

```bash
python -B aggregate_run_set.py \
  --manifest prepared/cohort/manifest.json \
  --run-dir runs/numbered_98 --run-dir runs/packed_2 \
  --output-dir reports/verified

python -B export_table7.py --report-dir reports/verified --output-dir reports/table6
```

**What the aggregator does.** It revalidates every source with its own
protocol snapshot, including:

- payloads, requests, outputs, attempt provenance and SQL references;
- that the sources share the same semantic protocol;
- that no task is accepted twice;
- that every review is complete.

Do not use `--allow-partial` for the table. Missing or incomplete tasks do not
count as zero.

**What the exporter does.** It refuses a report unless it covers all 100 tasks
and all 606 model–warehouse records. It recomputes every cell from the direct
sites and the downstream failures and compares the result with `summary.json`.
Its output directory must be new or empty.

**Outputs** (in `reports/table6/`):

| File | Content |
|---|---|
| `table7.md`, `table7.csv`, `table7.tex` | The table |
| `table7_members.json` | The models in each cell, with their direct and downstream evidence |
| `table7_provenance.json` | Input and output hashes, model settings and coverage |
| `coverage.json` | Accepted and complete status of the 100 tasks |

**Tracing a cell back to the evidence.**

- Each member in `table7_members.json` lists its `direct_sites`.
- Look up each site by `(target_id, site_id)` in
  `reports/verified/case_listings.json`. That file has the original SQL, the
  corrected SQL, line numbers, quotes and the saved scores before and after
  the correction.

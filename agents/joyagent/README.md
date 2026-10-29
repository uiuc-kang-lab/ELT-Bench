# JoyAgent-JDGenie on ELT-Bench

[JoyAgent-JDGenie](https://github.com/jd-opensource/joyagent-jdgenie) (main
branch, commit `3cc29a6`) is a multi-agent product. In its default
plan-and-execute mode ("deep think" in its UI) a planner splits the task into
sub-tasks and an executor solves each one with tool calls; `--mode react` uses
its single ReAct agent instead.

Its built-in tools (web search, a restricted Python interpreter, report
generation) cannot run shell commands, so they are switched off. The task tools
come in through JoyAgent's own extension point, MCP: an MCP server in the task
container provides `bash`, `read_file`, `write_file` and `edit_file`.
JoyAgent's planning tool and its file tool stay, because they are built in.

## Changes to JoyAgent

All changes are in `genie/joyagent-elt.patch`:

- MCP tool calls had a fixed 30 s HTTP timeout in `McpTool`, and genie-client
  had a fixed 5 min read timeout. Both are now configurable, because
  `terraform apply`, `dbt run` and job polling take longer.
- The `/AutoAgent` stream was capped at 60 minutes. That cap is now
  configurable.
- The planner prompt had two rules that make the last sub-task a web report.
  They are removed, because there is no report tool.

The runner also overrides some settings per run (`genie_override` in
`run.py`):

- step limits;
- model;
- MCP server URL;
- tool list.

The step limit applies to the executor's tool-call steps over the whole task,
not per sub-task. The default is 100, the same as the other agents.

## Images

```bash
docker build -t elt-swe-joyagent agents/joyagent/elt-swe-joyagent   # task container (FROM elt-swe)
docker build -t joyagent-genie agents/joyagent/genie                 # backend + genie-tool + genie-client
```

## Running

The model is reached through an OpenAI-compatible API. JoyAgent sends its
calls to a proxy in the runner. The proxy:

- adds the API key, so JoyAgent never sees it;
- records token usage in `joyagent/llm_calls.jsonl`;
- applies `--drop-params`, `--rename-params` and `--extra-params`.

```bash
export TOGETHER_API_KEY=...
python agents/run.py joyagent --database joyagent_glm53 --model zai-org/GLM-5.3 \
    --base-url https://api.together.xyz/v1 --api-key-env TOGETHER_API_KEY

# GPT-5.4, the same model and reasoning effort as the other agents' defaults.
# GPT-5.4 rejects tools + reasoning_effort on /chat/completions, so the proxy
# talks to /responses (responses_bridge.py); it also rejects temperature.
export OPENAI_API_KEY=...
python agents/run.py joyagent --database joyagent_gpt54 --model gpt-5.4-2026-03-05 \
    --responses-api --drop-params temperature \
    --extra-params '{"reasoning_effort": "high"}' --max-tokens 32768 \
    --price-in 2.5 --price-out 15 --price-cached 0.25
```

Each task writes these files under `output/<experiment>/<db>/joyagent/`:

| File | Contents |
|---|---|
| `result.json` | Final status and summary |
| `stats.json` | Turn and token counts |
| `events.jsonl` | JoyAgent's SSE events: plan, tool calls, results |
| `llm_calls.jsonl` | Every model response |
| `genie-logs/` | Backend, genie-tool and genie-client logs |

The task container cannot read this directory, because an empty tmpfs covers
it.

## DataAgent variant (`--variant dataagent`)

JoyAgent's `data_agent` branch (commit `2417e0b`) adds JoyDataAgent, a data
agent that answers questions over registered "data models" (tables or SQL
views) with its own NL2SQL pipeline. A data model carries governance metadata:
name, remark, business prompt, ignored / recalled / suggested / forbidden
fields, fields whose values are synced for few-shot examples, and column
aliases. The NL2SQL pipeline rewrites the question, splits it into
sub-questions, filters tables and columns (table RAG), writes an analysis
("think") and then the SQL for each sub-question.

The variant runs the web UI's 智能问数 product with deep thinking: the request
has `outputStyle: dataAgent` and the plan-and-execute agent (`--mode
plan_solve`, the default). In this mode upstream gives the executor the report
tool and the `data_analysis` tool (an analysis agent that fetches data through
NL2SQL) instead of the file tool. The MCP task tools are added as in the
default variant, and the task prompt is the same.

### Why two tools were added

Upstream configures the data models statically in `application.yml`, and only
the UI's chat endpoint runs NL2SQL. The agent itself cannot register a model
or get the SQL of a question, and in ELT-Bench the tables only exist after
stage 1. Two tools expose the existing upstream code to the agent:

- `register_models` takes the upstream `DataAgentModelConfig` fields and runs
  upstream's registration (read the schema, sample values, save the model).
- `nl2sql_query` runs upstream's NL2SQL for a question on the registered
  models and returns, per sub-question, the SQL, the row count, the first 20
  rows and any error.

The runner registers no models (`model-list: []` replaces upstream's two demo
models) and writes no descriptions. The agent registers models and writes all
metadata itself.

### Changes to JoyAgent

All changes are in `genie-dataagent/joyagent-dataagent-elt.patch`:

- The three changes of the default variant (MCP timeouts, `/AutoAgent` stream
  cap, planner report rules).
- Warehouse support, because upstream only has MySQL-like JDBC sources and H2:
  - JDBC dialects and catalogs for Snowflake, Databricks and Redshift (driver,
    identifier quoting, paging, table and column listing);
  - `db-config.url` for a full JDBC URL;
  - connection pools for the three warehouses;
  - the SQL parser treats them like the other JDBC sources;
  - the data agent writes MySQL-style backtick identifiers. On Snowflake they
    become double-quoted, and plain identifiers are upper-cased, which is how
    Snowflake resolves unquoted names. Without this, a lower-case field such as
    `city` did not match the column CITY created by Airbyte and dbt. Redshift
    folds quoted names to lower case anyway.
- JOINs in NL2SQL. Upstream allowed one table per SQL, which cannot express
  most data models. The prompts now allow JOINs on the provided fields, and
  execution maps every model code in the SQL to its table. Splitting a
  question into sub-questions is unchanged.
- Bug fix in the column filter: answers without a fenced JSON block were
  rejected, and retries appended to the previous answer.
- No registered model: upstream always has models from its configuration,
  so it never handles an empty model list. `data_analysis` then ran its whole
  loop (minutes of failing NL2SQL fetches) and ended with
  `IndexError: list index out of range`. Now `data_analysis` and
  `nl2sql_query` return at once that no model is registered and that
  `register_models` registers one. With registered models nothing changes.
- Bug fix in the analysis: its result file was named after the full task
  text, which failed for texts with `/` or over 255 bytes. The name now has
  `/` replaced and is cut to 200 bytes.
- Timeouts that assume a fast model are configurable:
  - NL2SQL HTTP read (60 s), set by the runner to 900 s;
  - an analysis call (300 s), set to 1800 s;
  - the analysis's data fetch (90 s), set to 900 s.
- The two tools above, and `POST /data/registerModels`.

### Runner settings

- Image `joyagent-genie-dataagent`. The experiment id is
  `joyagent-dataagent-<model>-<suffix>-<destination>`, so results and the
  Redshift database or Databricks catalog are separate from the default
  variant.
- The data agent connects to the task schema with the credentials of the
  task's own `config.yaml` (the agent's credentials, not the runner's).
  - Snowflake: upper-case database and schema, with the config's warehouse and
    role.
  - Redshift: the run's database.
  - Databricks: OAuth machine-to-machine, with `ConnCatalog` and `ConnSchema`.
  - After the run, the kept `joyagent/config/override.yml` has the secrets
    masked.
- genie-tool's LLM calls (NL2SQL, table RAG, analysis, report) also go through
  the proxy and use the run's model.
- genie-tool uses upstream's `.env_template` as its `.env`. The model,
  endpoint and file settings are overridden; everything else is as shipped:
  - `SENSITIVE_WORD_REPLACE=true` masks e-mail addresses, phone, ID and bank
    numbers in genie-tool's LLM inputs;
  - Elasticsearch and Qdrant recall are off.
- genie-tool's SQLite file table is created at start, as in upstream's setup.
  The default variant's image skips this step, so its file tool cannot save
  files.
- `sopPrompt` is empty, as in the default variant. The UI sends `{{sop}}`,
  which SOP recall fills. Without an SOP library, it gets a generic planning
  example whose last step is a web report, the kind of rule removed from the
  planner.

### Proxy

These proxy changes apply to both variants. The default variant never streams
and never sends `stop`, so it is unaffected.

- Streaming requests (genie-tool streams NL2SQL's think step and its reports)
  are sent upstream without streaming. The answer is replayed as an SSE
  stream. Before this change, the think step received an empty text.
- With `--responses-api`, `stop` (sent by the analysis agent) is applied to
  the returned text, because `/responses` has no such parameter.

### Running

```bash
docker build -t joyagent-genie-dataagent agents/joyagent/genie-dataagent

export OPENAI_API_KEY=...
python agents/run.py joyagent --variant dataagent --destination redshift \
    --model gpt-5.4-2026-03-05 --responses-api --drop-params temperature,top_p \
    --extra-params '{"reasoning_effort": "high"}' --max-tokens 32768 \
    --price-in 2.5 --price-out 15 --price-cached 0.25
# Snowflake runs share one database unless --database is given:
#   --destination snowflake --database joyagent_dataagent_gpt54
```

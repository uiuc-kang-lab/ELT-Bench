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

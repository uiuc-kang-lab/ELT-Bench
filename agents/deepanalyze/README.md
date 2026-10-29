# DeepAnalyze on ELT-Bench

[DeepAnalyze](https://github.com/ruc-datalab/DeepAnalyze) (main branch, commit
`d4dd5cf`) is an agentic LLM for data science,
[DeepAnalyze-8B](https://huggingface.co/RUC-DataLab/DeepAnalyze-8B). It has no
tool calls. The agent loop is the model's own output format:

- The model writes `<Analyze>`, `<Understand>`, `<Code>` and `<Answer>` blocks.
- The harness runs each `<Code>` block (Python).
- The output goes back as an `execute` message. The chat template renders it
  as `<Execute>…</Execute>` inside the same assistant turn.

`run.py` follows the loop of DeepAnalyze's OpenAI-compatible API
(`API/chat_api.py`, `API/utils.py`):

- The prompt has an `# Instruction` section and a `# Data` section that lists
  the workspace files.
- Requests use `add_generation_prompt: false` and stop at `</Code>` and at the
  end-of-sentence token (ids 151676 and 151645). The temperature is 0.4.
- Each `<Code>` block runs as a new `python` process.
- The run ends when the model writes `</Answer>`, or when a response contains
  no code.

## Changes for ELT-Bench

- **Where the code runs.** DeepAnalyze runs the code on its own host. Here it
  runs in the task container, a fresh `elt-swe` container with working
  directory `/workspace`. `/workspace` is read-only except `/workspace/elt`,
  the same as for the other agents. Shell commands (terraform, dbt) go through
  `subprocess`, as the prompt explains.
- **Limits per code block.** DeepAnalyze allows 120 s per block and returns
  all output. Here a block may run for 1800 s, and its output is cut to the
  first and last 5000 characters. These are the limits of JoyAgent's bash
  tool. A timeout kills the whole process group.
- **Turn limit.** At most 100 code blocks are run (`--max_turns`), the same as
  the other agents.
- **Generation limit.** Each generation may produce at most 32768 tokens
  (`--max-new-tokens`, DeepAnalyze's own default). Normal steps produce at
  most a few thousand tokens. A generation that reaches the limit is a runaway
  that repeats itself, and the run ends with status `error_max_tokens`. When
  less context is left than the limit, the generation may run until the
  context is full.
- **Context.** DeepAnalyze has no context management. When the conversation
  no longer fits into the server's `max_model_len`, the run ends with status
  `error_context_length`.
- **Prompt.** The task text is the same as for the other runners. The system
  part describes the `<Code>` environment instead of tool calls, and asks for
  the `RESULT:` line in `<Answer>`.

## Model server

The runner needs a vLLM server that serves DeepAnalyze-8B with the model's
own chat template (the template handles the `execute` role). The GPU server
only listens on its own 127.0.0.1:8000, so it is reached through an SSH
tunnel:

```bash
ssh -p <port> -i ~/.ssh/id_rsa -f -N -L 127.0.0.1:18000:127.0.0.1:8000 \
    -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 <user>@<gpu-server>
curl -s http://127.0.0.1:18000/v1/models   # check
```

If the tunnel drops, LLM calls are retried for about 6 minutes. After that the
task ends with status `error_llm`, and the next invocation runs it again.

The model supports 131072 tokens of context (YaRN). The server's
`--max-model-len` sets the context available to the agent. The runner logs
this value at startup.

## Running

The task container is the shared `elt-swe` image (see `agents/README.md`). No
other image is needed.

```bash
/mydata/miniconda/envs/codex_eltbench/bin/python agents/run.py deepanalyze \
    --database deepanalyze_8b --only address
```

Each task writes these files under `output/<experiment>/<db>/deepanalyze/`:

| File | Contents |
|---|---|
| `result.json` | Final status, the `<Answer>` text, and token usage |
| `stats.json` | Turn and token counts |
| `trajectory.jsonl` | One line per generation step: the model output, the code, and its output |
| `transcript.md` | The whole conversation as the model saw it |

The `num_turns` field counts executed code blocks. The model is self-hosted,
so `total_cost_usd` is `null`.

These statuses are kept: `success` (an `<Answer>`, or a response without
code), `error_max_turns`, `error_context_length`, `error_max_tokens` and
`timeout`. Other
statuses are rerun by the next invocation without `--overwrite`.

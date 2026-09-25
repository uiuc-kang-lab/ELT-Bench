"""Claude Code Agent runner for ELT-Bench.

Uses the `claude-agent-sdk` Python SDK to drive Claude against each ELT task
in `../../elt-bench/`. For every database it:

  1. Resets the configured Snowflake, Databricks, or Redshift namespace.
  2. Copies the destination-specific task inputs into the per-run output
     directory, which is mounted as `/workspace` inside a fresh
     `elt-swe-claude` Docker container on the `elt-docker_elt_network`.
  3. Runs the Claude Code CLI inside that container. The SDK spawns
     `docker_claude.sh`, which execs `claude` in the container, so every tool
     the CLI offers (Bash, Read, Write, Edit, Glob, Grep) executes in the
     container and sees only `/workspace`. The host filesystem, including the
     task generator's release bundles, is not reachable. A PreToolUse hook
     refuses writes outside `/workspace/elt`, the rule the task states.
     The operator's own Claude Code settings, plugins and MCP servers are not
     loaded (`setting_sources=[]`, `strict_mcp_config`).
  4. Audits the finished trajectory (`claude/sandbox_audit.json`): writes
     attempted outside `/workspace/elt` and any reference to a release path
     are recorded, and the run is marked `sandbox_clean`.
  5. Streams the trajectory and writes `claude/result.json` with the
     transcript, turn count, cost, and final status.

Usage:
    export ANTHROPIC_API_KEY=...           # passed into the container
    docker build -t elt-swe-claude agents/claude_agent/elt-swe-claude
    python run.py --destination databricks --suffix eltbench --model claude-opus-4-7
"""

from __future__ import annotations

import argparse
import asyncio
import posixpath
import datetime
import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    HookMatcher,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    query,
)

AGENTS_DIR = Path(__file__).resolve().parents[1]
if str(AGENTS_DIR) not in sys.path:
    sys.path.insert(0, str(AGENTS_DIR))

from common import (  # noqa: E402
    DestinationPreparationError,
    adapt_prompt,
    destination_choices,
    get_destination,
    prepare_destination,
    resolve_benchmark_path,
    resolve_inputs_path,
)


# ---------- logging ----------

logger = logging.getLogger("claude_agent")
logger.setLevel(logging.DEBUG)

LOG_DIR = AGENTS_DIR / "logs/claude"
LOG_DIR.mkdir(parents=True, exist_ok=True)
_ts = datetime.datetime.now().strftime("%Y%m%d@%H%M%S")
_fmt = logging.Formatter(
    "[%(asctime)s %(levelname)s %(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
_file = logging.FileHandler(LOG_DIR / f"run-{_ts}.log", encoding="utf-8")
_file.setFormatter(_fmt)
_file.setLevel(logging.DEBUG)
_std = logging.StreamHandler(sys.stdout)
_std.setFormatter(_fmt)
_std.setLevel(logging.INFO)
logger.addHandler(_file)
logger.addHandler(_std)


# ---------- constants ----------

IMAGE_NAME = "elt-swe-claude"
NETWORK_NAME = "elt-docker_elt_network"
CONTAINER_WORKDIR = "/workspace"
CONTAINER_ELT_DIR = f"{CONTAINER_WORKDIR}/elt"

# The SDK spawns this script instead of a local `claude`; it execs the CLI
# inside the task container named by $CLAUDE_CONTAINER. The image pins the
# CLI version (2.1.282, see elt-swe-claude/Dockerfile).
CLI_WRAPPER = Path(__file__).resolve().parent / "docker_claude.sh"

# Host environment variables copied into the container when present: the
# API key and the alternative auth/endpoint settings Claude Code reads.
CONTAINER_ENV_PASSTHROUGH = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_CUSTOM_HEADERS",
    "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "AWS_REGION",
    "HTTPS_PROXY",
    "HTTP_PROXY",
    "NO_PROXY",
)
# Fixed container environment: terraform apply and dbt run exceed Claude
# Code's default 2-minute Bash timeout, and nothing else should leave the
# container.
CONTAINER_ENV_FIXED = {
    "BASH_DEFAULT_TIMEOUT_MS": "600000",
    "BASH_MAX_TIMEOUT_MS": "1800000",
    "DISABLE_AUTOUPDATER": "1",
    "DISABLE_TELEMETRY": "1",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
}

SYSTEM_PROMPT_TEMPLATE = """You are a data engineer skilled in databases, SQL, and building ELT pipelines.
You are running inside a Docker container named `{container}` ({image} image on the `{network}` network). Your working directory is `{container_workdir}`; it contains all the necessary information for your tasks. However, you are only allowed to modify files in `{container_workdir}/elt`.
Your goal is to build an ELT pipeline by extracting data from multiple sources, such as custom APIs, PostgreSQL, MongoDB, flat files, and the cloud service S3.
The extracted data will be loaded into a target system, Databricks, followed by writing transformation queries to construct final tables for downstream use.
This task is divided into two stages:
1. Data Extraction and Loading – Using Airbyte's Terraform provider.
2. Data Transformation – Using the DBT Project workflow for Databricks.

TOOL USAGE:
  - Read / Write / Edit / Glob / Grep: operate on files under `{container_workdir}`. Prefer these over shell utilities for file I/O.
  - Bash: run a shell command in the container (cwd = `{container_workdir}`). All commands — terraform, dbt, python, psql, etc. — run here.

First, you should _always_ include a general thought about what you're going to do next.
Then issue the corresponding tool call. Wait for the tool result before continuing with more discussion and commands.
"""

TASK_INSTRUCTION = """We're currently building the ELT pipeline using Airbyte Terraform and DBT. Here's the detailed instruction:

INSTRUCTIONS:
 # Stage 1: Data Extraction and Loading Hints#
1. Initialize the Airbyte Provider: Use /workspace/config.yaml to configure the username, password, and server URL in /workspace/elt/main.tf. You can refer to /workspace/documentation/airbyte_Provider.md, then run `terraform init`.
• Important: You must not modify any provided code in /workspace/elt/main.tf.
2. Configure Sources and Destinations: Use /workspace/config.yaml to set up the listed sources and destinations in in Terraform file located in /workspace/elt. The values in config.yaml represent the actual configurations required for the project.
3. Refer to Documentation for Configuration Guidance: You must consult the Airbyte documentation located in /workspace/documentation to understand how to configure sources and destinations.
• Important: The values in the documentation are for reference only. DO NOT use them directly. And you must not fill the fields with random values or placeholders. Instead, fill in the fields based on the field names in /workspace/documentation and the realistic values specified in /workspace/config.yaml. The field names in /workspace/documentation and /workspace/config.yaml may not match exactly. In such cases, you need to infer values for certain fields. If you forget the realistic values for configuring sources and destinations in Terraform file located in /workspace/elt, you must go back and read /workspace/config.yaml to retrieve them.
4. Establish Connections: After creating sources and destinations, establish connections between them by following /workspace/documentation/connection.md. For each connection, include the name and sync_mode fields in configuration.streams to streamline only the tables defined in /workspace/config.yaml.
5. Apply the Configuration: Once all necessary configurations are written, run `terraform apply` to create the resources.
6. Retrieve Connection IDs: After successfully creating sources, destinations and connections, obtain the connection IDs for all newly created connections from the terraform.tfstate file, as these will be needed to trigger the jobs.
7. Trigger Sync Jobs One by One with Delay: Due to warehouse resource limitations, you must trigger sync jobs one at a time with a 1-minute delay between each trigger. For each connection ID, trigger the job using the Airbyte API (refer to /workspace/documentation/trigger_job.md and use /workspace/config.yaml to retrieve the required values), then wait at least 1 minute (e.g., `sleep 60`) before triggering the next job. Do NOT wait for a job to complete before triggering the next one — just ensure the 1-minute gap between triggers.
8. Monitor Job Status: After all jobs have been triggered, check the status of all jobs by running `python /workspace/check_job_status.py --server <server> --username <username> --password <password>` (replace <server>, <username>, and <password> with the actual values). Keep checking until all jobs have completed. Proceed to the next stage only if all data extraction and loading jobs are successful. If any job fails, fix it and retry before moving on.
9. Error Handling: If an error occurs, DO NOT modify any provided files. Instead, verify the configuration against the provided documentation and review previous steps to identify and resolve the issue. If the issue persists after multiple retries, terminate the task.

#  Stage 2: Data Transformation Hints#
1. Initialize the DBT Project: Set up a new DBT project by configuring it with /workspace/config.yaml, and remove the example directory under the models directory. When you need to connect to Databricks, you must connect through the OAuth machine-to-machine (M2M) authentication method. Refer to databricks_authentication.md for the required configuration details.
2. Understand the Data Model: Review data_model.yaml in /workspace to understand the required data models and their column descriptions. Then, write SQL queries to generate these defined data models, referring to the files in the /workspace/schemas directory to understand the schemas of source tables.
• Important: Write a separate query for each data model, and if using any DBT project variables, ensure they have already been declared.
3. Validate Table Locations: Ensure all SQL queries reference the correct database and schema names for source tables. If you encounter a "table not found" error, refer to /workspace/config.yaml to obtain the correct configuration. If the table does not exist, the issue is likely due to a failure in data extraction and loading in Stage 1, and you should return to Stage 1 to resolve it.
4. Run the DBT Project: Execute `dbt run` to apply transformations and generate the final data models in Databricks, fixing any errors reported by DBT.
5. Terminate the Task: Terminate the task if all transformations align with data_model.yaml and the final tables in Databricks are accurate and verified. Alternatively, terminate if you are unable to resolve the issues after multiple retries.

When done (or giving up), print a single final line:
    RESULT: SUCCESS   — pipeline built and final tables populated
    RESULT: FAIL: <short reason>
"""

# Tools the agent may use, all executed inside the container. Listing Bash
# here approves every shell command without a prompt.
ALLOWED_TOOLS = ["Read", "Write", "Edit", "Glob", "Grep", "Bash"]
# Tools removed from the session: web access, sub-agents, and planning tools
# the benchmark does not provide.
DISALLOWED_TOOLS = [
    "WebFetch",
    "WebSearch",
    "Agent",
    "Task",
    "NotebookEdit",
    "NotebookRead",
    "TodoWrite",
    "Skill",
    "EnterPlanMode",
    "ExitPlanMode",
]
# File tools that modify files; the guard limits them to /workspace/elt.
WRITE_TOOL_MATCHER = "Write|Edit|MultiEdit|NotebookEdit"
WRITE_TOOLS = frozenset(WRITE_TOOL_MATCHER.split("|"))
PATH_INPUT_KEYS = ("file_path", "notebook_path")
# Substrings that identify the task generator's release bundles, which hold
# the answer keys. They cannot exist in the container; a tool input that
# names one is reported by the audit.
FORBIDDEN_PATH_MARKERS = ("answer_key", "/releases/", "ELT-taskgen")


def _hook_deny(reason: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


class SandboxGuard:
    """Enforce the task's write rule on the container-side file tools.

    The tools run inside the container, so the host is unreachable without
    any check here. This guard refuses Write/Edit calls whose target is not
    under `/workspace/elt`, which the task instruction forbids. Reads are not
    restricted. Every refusal is recorded for the post-run audit.
    """

    def __init__(self, workdir: str = CONTAINER_WORKDIR) -> None:
        self.workdir = workdir
        self.elt = posixpath.join(workdir, "elt")
        self.denials: list[dict[str, Any]] = []

    def normalize(self, raw: str) -> str:
        """Absolute, `..`-free container path for a model-supplied path."""
        path = raw if raw.startswith("/") else posixpath.join(self.workdir, raw)
        return posixpath.normpath(path)

    def check(self, tool_name: str, tool_input: dict[str, Any]) -> str | None:
        """Return the denial reason, or None when the call is allowed."""
        if tool_name not in WRITE_TOOLS:
            return None
        for key in PATH_INPUT_KEYS:
            raw = tool_input.get(key)
            if not isinstance(raw, str) or not raw:
                continue
            path = self.normalize(raw)
            if path != self.elt and not path.startswith(self.elt + "/"):
                return (
                    f"{tool_name} may only modify files under {self.elt}; "
                    f"refused {raw!r}"
                )
        return None

    async def pre_tool_use(self, input_data: Any, tool_use_id: str | None, context: Any) -> dict[str, Any]:
        """PreToolUse hook for the write tools: deny with a reason, or no-op."""
        tool_name = str(input_data.get("tool_name", ""))
        tool_input = input_data.get("tool_input") or {}
        if not isinstance(tool_input, dict):
            tool_input = {}
        reason = self.check(tool_name, tool_input)
        if reason is None:
            return {}
        self.denials.append({"tool": tool_name, "input": tool_input, "reason": reason})
        logger.warning("sandbox denied %s: %s", tool_name, reason)
        return _hook_deny(reason)

    def hooks(self) -> dict[str, list[HookMatcher]]:
        """The hook table to pass as `ClaudeAgentOptions.hooks`."""
        return {"PreToolUse": [HookMatcher(matcher=WRITE_TOOL_MATCHER, hooks=[self.pre_tool_use])]}


def audit_trajectory(turns: list[dict[str, Any]], guard: SandboxGuard) -> dict[str, Any]:
    """Scan a finished trajectory for writes outside /workspace/elt.

    A flagged call whose tool result is an error was refused and is recorded
    as an attempt. A flagged call that returned normally, or has no recorded
    result, is recorded as an escape. Only escapes and release-path markers
    make the run unclean.
    """
    # tool_use id -> whether its result was an error. Tool results arrive in
    # user turns and reference the tool_use by id.
    results: dict[str, bool] = {}
    for turn in turns:
        if turn.get("role") != "user":
            continue
        for block in turn.get("content", []):
            if block.get("type") == "tool_result" and block.get("tool_use_id"):
                results[str(block["tool_use_id"])] = bool(block.get("is_error"))
    attempts: list[dict[str, Any]] = []
    escapes: list[dict[str, Any]] = []
    forbidden_markers: list[dict[str, Any]] = []
    for turn in turns:
        if turn.get("role") != "assistant":
            continue
        for block in turn.get("content", []):
            if block.get("type") != "tool_use":
                continue
            name = str(block.get("name", ""))
            tool_input = block.get("input") or {}
            if isinstance(tool_input, dict):
                reason = guard.check(name, tool_input)
                if reason is not None:
                    record = {"tool": name, "input": tool_input, "reason": reason}
                    # An error result means the hook or the CLI refused the
                    # call. A normal result, or a missing result, means it ran.
                    if results.get(str(block.get("id")), False):
                        attempts.append(record)
                    else:
                        escapes.append(record)
            text = json.dumps(tool_input, default=str)
            hits = [marker for marker in FORBIDDEN_PATH_MARKERS if marker in text]
            if hits:
                forbidden_markers.append({"tool": name, "markers": hits, "input": text[:400]})
    return {
        "workdir": guard.workdir,
        "denied_attempts": attempts,
        "escapes": escapes,
        "forbidden_markers": forbidden_markers,
        "hook_denials": guard.denials,
        "sandbox_clean": not (escapes or forbidden_markers),
    }


# ---------- helpers ----------

def _run(cmd: list[str], check: bool = True, **kw: Any) -> subprocess.CompletedProcess:
    logger.debug("$ %s", " ".join(cmd))
    return subprocess.run(cmd, check=check, text=True, capture_output=True, **kw)


def ensure_container(container_name: str, mnt_dir: Path) -> None:
    """(Re)create a fresh ELT container with `mnt_dir` bind-mounted to /workspace.

    The API key and related settings are passed by name (`-e NAME`), so their
    values do not appear in the process list.
    """
    existing = _run(
        ["docker", "ps", "-aq", "-f", f"name=^{container_name}$"], check=False
    ).stdout.strip()
    if existing:
        logger.info("Removing existing container %s", container_name)
        _run(["docker", "rm", "-f", container_name], check=False)

    mnt_abs = str(mnt_dir.resolve())
    env_args: list[str] = []
    for name in CONTAINER_ENV_PASSTHROUGH:
        if os.environ.get(name):
            env_args += ["-e", name]
    for name, value in CONTAINER_ENV_FIXED.items():
        env_args += ["-e", f"{name}={value}"]
    logger.info("Starting container %s (mount %s -> %s)", container_name, mnt_abs, CONTAINER_WORKDIR)
    _run([
        "docker", "run", "-d", "--rm",
        "--name", container_name,
        "--network", NETWORK_NAME,
        *env_args,
        "-v", f"{mnt_abs}:{CONTAINER_WORKDIR}",
        "-w", CONTAINER_WORKDIR,
        IMAGE_NAME,
        "sleep", "infinity",
    ])


def stop_container(container_name: str) -> None:
    _run(["docker", "rm", "-f", container_name], check=False)


def copy_initial_files(src: Path, dst: Path) -> None:
    """Mirror `src` contents into `dst` (like `cp -r src/. dst/`)."""
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        if item.name.endswith("_credential.json"):
            continue
        target = dst / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)


# ---------- trajectory capture ----------

class TrajectoryRecorder:
    """Collects SDK messages into a JSON-serializable transcript."""

    def __init__(self) -> None:
        self.turns: list[dict[str, Any]] = []
        self.num_turns: int = 0
        self.total_cost_usd: float | None = None
        self.usage: dict[str, Any] | None = None
        self.is_error: bool = False
        self.final_text: str = ""

    def _serialize_block(self, block: Any) -> dict[str, Any]:
        if isinstance(block, TextBlock):
            return {"type": "text", "text": block.text}
        if isinstance(block, ToolUseBlock):
            return {
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": block.input,
            }
        if isinstance(block, ToolResultBlock):
            return {
                "type": "tool_result",
                "tool_use_id": block.tool_use_id,
                "content": block.content,
                "is_error": block.is_error,
            }
        return {"type": "unknown", "repr": repr(block)}

    @staticmethod
    def _tool_result_text(block: ToolResultBlock) -> str:
        content = block.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(str(item.get("text", "")))
                else:
                    parts.append(json.dumps(item, default=str))
            return "\n".join(parts)
        return str(content)

    def record(self, message: Any) -> None:
        if isinstance(message, AssistantMessage):
            blocks = [self._serialize_block(b) for b in message.content]
            self.turns.append({"role": "assistant", "content": blocks})
            for b in message.content:
                if isinstance(b, TextBlock):
                    self.final_text = b.text
                    # Full thought to file (DEBUG); short preview to stdout (INFO).
                    logger.debug("assistant thought:\n%s", b.text)
                    logger.info("assistant: %s", b.text.strip()[:500])
                elif isinstance(b, ToolUseBlock):
                    full = json.dumps(b.input, default=str)
                    logger.debug("tool_use %s input:\n%s", b.name, full)
                    logger.info("tool_use %s: %s", b.name, full[:300])
        elif isinstance(message, UserMessage):
            # UserMessage wraps tool_result blocks (environment feedback).
            content = message.content
            if isinstance(content, list):
                blocks = [self._serialize_block(b) for b in content]
                for b in content:
                    if isinstance(b, ToolResultBlock):
                        text = self._tool_result_text(b)
                        tag = " [ERROR]" if b.is_error else ""
                        logger.debug(
                            "tool_result %s%s:\n%s",
                            b.tool_use_id, tag, text,
                        )
                        preview = text.strip().replace("\n", " ⏎ ")[:500]
                        logger.info("tool_result %s%s: %s", b.tool_use_id, tag, preview)
            else:
                blocks = [{"type": "text", "text": str(content)}]
            self.turns.append({"role": "user", "content": blocks})
        elif isinstance(message, SystemMessage):
            # Init / meta messages — log but don't add to transcript.
            logger.debug("system: %r", message)
        elif isinstance(message, ResultMessage):
            self.num_turns = message.num_turns
            self.total_cost_usd = message.total_cost_usd
            self.usage = message.usage
            self.is_error = bool(message.is_error)
            logger.info(
                "result: turns=%d cost=$%s error=%s",
                self.num_turns,
                self.total_cost_usd,
                self.is_error,
            )


# ---------- the main loop ----------

async def run_task(
    db: str,
    destination: str,
    credential: str | None,
    experiment_id: str,
    output_root: Path,
    inputs_root: Path,
    model: str,
    max_turns: int,
    overwrite: bool,
) -> None:
    instance_id = f"{experiment_id}/{db}"
    out_dir = output_root / instance_id
    result_path = out_dir / "claude" / "result.json"

    if result_path.exists() and not overwrite:
        logger.info("Skipping %s (result exists)", instance_id)
        return
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    db_ts = datetime.datetime.now().strftime("%Y%m%d@%H%M%S")
    db_log_path = LOG_DIR / f"{experiment_id}-{db}-{db_ts}.log"
    db_handler = logging.FileHandler(db_log_path, encoding="utf-8")
    db_handler.setFormatter(_fmt)
    db_handler.setLevel(logging.DEBUG)
    logger.addHandler(db_handler)

    logger.info("=== Running %s (log: %s) ===", instance_id, db_log_path)

    try:
        await _run_task_body(
            db=db,
            destination=destination,
            credential=credential,
            instance_id=instance_id,
            experiment_id=experiment_id,
            out_dir=out_dir,
            result_path=result_path,
            inputs_root=inputs_root,
            model=model,
            max_turns=max_turns,
        )
    finally:
        logger.removeHandler(db_handler)
        db_handler.close()


async def _run_task_body(
    db: str,
    destination: str,
    credential: str | None,
    instance_id: str,
    experiment_id: str,
    out_dir: Path,
    result_path: Path,
    inputs_root: Path,
    model: str,
    max_turns: int,
) -> None:
    task_input_dir = inputs_root / db

    # A failed reset means stale warehouse state: abort this attempt before
    # any container, agent session, or evaluation can observe it.
    namespace = prepare_destination(destination, task_input_dir, credential)
    logger.info("Prepared %s destination namespace %s", destination, namespace)

    # Copy seed files into the mount dir.
    copy_initial_files(task_input_dir, out_dir)

    # Spin up the container.
    container_name = f"{experiment_id}-{db}"
    ensure_container(container_name, out_dir)

    system_prompt = adapt_prompt(SYSTEM_PROMPT_TEMPLATE, destination).format(
        db=db,
        container=container_name,
        image=IMAGE_NAME,
        network=NETWORK_NAME,
        container_workdir=CONTAINER_WORKDIR,
    )

    # The CLI runs inside the container through the wrapper, so every tool is
    # container-scoped. The remaining options remove web and sub-agent tools
    # and the operator's own Claude Code settings, plugins, and MCP servers.
    guard = SandboxGuard()
    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        cwd=str(out_dir.resolve()),
        allowed_tools=ALLOWED_TOOLS,
        disallowed_tools=DISALLOWED_TOOLS,
        strict_mcp_config=True,
        setting_sources=[],
        hooks=guard.hooks(),
        permission_mode="acceptEdits",
        max_turns=max_turns,
        model=model,
        cli_path=str(CLI_WRAPPER),
        env={"CLAUDE_CONTAINER": container_name},
    )

    recorder = TrajectoryRecorder()
    destination_name = get_destination(destination).display_name
    prompt = (
        f"Build the ELT pipeline for the `{db}` now. All configuration values "
        f"(including the {destination_name} namespace) must come from "
        f"/workspace/config.yaml.\n\n{adapt_prompt(TASK_INSTRUCTION, destination)}"
    )

    try:
        async for message in query(prompt=prompt, options=options):
            recorder.record(message)
    except Exception as e:
        logger.exception("Claude session raised: %s", e)
        recorder.is_error = True
        recorder.final_text = f"ERROR: {e}"
    finally:
        stop_container(container_name)

    # Persist result.
    (out_dir / "claude").mkdir(parents=True, exist_ok=True)
    # The audit is written even when the session raised, so a partial
    # trajectory is still checked.
    audit = audit_trajectory(recorder.turns, guard)
    with open(out_dir / "claude" / "sandbox_audit.json", "w") as f:
        json.dump(audit, f, indent=2, default=str)
    if audit["sandbox_clean"]:
        logger.info("sandbox audit clean (%d hook denials)", len(audit["hook_denials"]))
    else:
        logger.error("SANDBOX AUDIT FAILED for %s: %s", instance_id,
                     json.dumps({k: audit[k] for k in ("escapes", "forbidden_markers")}, default=str)[:2000])
    result_json = {
        "instance_id": instance_id,
        "db": db,
        "model": model,
        "finished": not recorder.is_error,
        "num_turns": recorder.num_turns,
        "total_cost_usd": recorder.total_cost_usd,
        "usage": recorder.usage,
        "result": recorder.final_text,
        "sandbox_clean": audit["sandbox_clean"],
        "trajectory": recorder.turns,
    }
    with open(result_path, "w") as f:
        json.dump(result_json, f, indent=2, default=str)
    logger.info("Wrote %s", result_path)

    stats_path = out_dir / "claude" / "stats.json"
    stats_json = {
        "instance_id": instance_id,
        "db": db,
        "model": model,
        "num_turns": recorder.num_turns,
        "total_cost_usd": recorder.total_cost_usd,
        "usage": recorder.usage,
    }
    with open(stats_path, "w") as f:
        json.dump(stats_json, f, indent=2, default=str)
    logger.info("Wrote %s", stats_path)


async def main_async(args: argparse.Namespace) -> None:
    base_id = f"{args.model.split('/')[-1]}-{args.suffix}" if args.suffix else args.model
    experiment_id = f"claude-{base_id}-{args.destination}"
    output_root = Path(args.output_dir)
    inputs_root = resolve_inputs_path(args.destination, args.test_path)
    elt_bench_root = resolve_benchmark_path(args.destination, args.elt_bench)

    if not inputs_root.is_dir():
        raise SystemExit(f"inputs dir not found: {inputs_root}")
    if not elt_bench_root.is_dir():
        raise SystemExit(f"elt-bench dir not found: {elt_bench_root}")

    databases = sorted(p.name for p in elt_bench_root.iterdir() if p.is_dir())
    if args.only:
        wanted = set(args.only.split(","))
        databases = [d for d in databases if d in wanted]
    if args.limit and args.limit > 0:
        databases = databases[: args.limit]

    logger.info("Experiment %s — %d tasks", experiment_id, len(databases))
    failures = 0
    for db in databases:
        try:
            await run_task(
                db=db,
                destination=args.destination,
                credential=args.credential,
                experiment_id=experiment_id,
                output_root=output_root,
                inputs_root=inputs_root,
                model=args.model,
                max_turns=args.max_turns,
                overwrite=args.overwrite,
            )
        except DestinationPreparationError as exc:
            failures += 1
            logger.error("Task %s aborted before the agent session: %s", db, exc)
        except Exception:
            logger.exception("Task %s failed", db)
    if failures:
        raise SystemExit(f"{failures} task(s) aborted: destination preparation failed")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run Claude Code Agent on ELT-Bench.")
    p.add_argument("--destination", choices=destination_choices(), default="snowflake")
    p.add_argument(
        "--credential",
        help="Optional host-side destination credential JSON override.",
    )
    p.add_argument("--model", default="claude-opus-4-7",
                   help="Claude model id (e.g. claude-opus-4-7, claude-sonnet-4-6).")
    p.add_argument("--suffix", "-s", default="eltbench", help="Experiment id suffix.")
    p.add_argument("--max_turns", type=int, default=100)
    p.add_argument("--test_path", "-t",
                   help="Per-task inputs directory (default: destination-specific).")
    p.add_argument("--elt_bench",
                   help="Task directory (default: elt-bench/<destination>).")
    p.add_argument("--output_dir", default=str(AGENTS_DIR / "output"))
    p.add_argument("--only", default="", help="Comma-separated DBs to run (default: all).")
    p.add_argument("--limit", type=int, default=100,
                   help="Run only the first N DBs (after --only filter). "
                        "Default 20; pass 0 for no limit.")
    p.add_argument("--overwrite", action="store_true",
                   help="Rerun tasks even if result.json already exists.")
    p.add_argument("--image", default=IMAGE_NAME,
                   help="Container image with the Claude Code CLI installed.")
    return p.parse_args()


def main() -> None:
    global IMAGE_NAME
    args = parse_args()
    IMAGE_NAME = args.image
    if not CLI_WRAPPER.is_file() or not os.access(CLI_WRAPPER, os.X_OK):
        raise SystemExit(f"CLI wrapper is missing or not executable: {CLI_WRAPPER}")
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()

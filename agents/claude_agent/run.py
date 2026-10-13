"""Claude Code Agent runner for ELT-Bench.

Uses the `claude-agent-sdk` Python SDK to drive Claude against each ELT task
in `../../elt-bench/`. For every database it:

  1. Copies the destination-specific task inputs into the per-run output
     directory and points the task at its own schema (`--database` holds one
     schema per task), then resets that namespace in the warehouse.
  2. Starts a fresh `elt-swe-claude` container on `elt-docker_elt_network`
     with the output directory mounted at `/workspace`, running as the host
     user so every file it creates stays host-owned.
  3. Launches a Claude Agent SDK session whose CLI runs *inside* the container:
     `cli_path` is `docker_claude.sh`, which execs `claude` in the container,
     so every tool (Bash, Read, Write, Edit, Glob, Grep) executes there and
     sees only `/workspace`; the host filesystem is not reachable. A PreToolUse
     hook refuses Write/Edit outside `/workspace/elt`, the rule the task
     states. The operator's own Claude Code settings, plugins and MCP servers
     are not loaded (`setting_sources=[]`, `strict_mcp_config`).
  4. Audits the finished trajectory (`claude/sandbox_audit.json`) and writes
     `claude/result.json` with the transcript, turn count, cost, and status.

Usage:
    ~/.local/bin/claude setup-token        # once; OAuth token for the container
    export CLAUDE_CODE_OAUTH_TOKEN=...      # or ANTHROPIC_API_KEY=...
    docker build -t elt-swe-claude agents/claude_agent/elt-swe-claude
    python run.py --destination snowflake --database claude_opus_test2 --model claude-opus-4-7
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import datetime
import json
import logging
import os
import posixpath
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import yaml

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    HookMatcher,
    RateLimitEvent,
    ResultError,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    query,
)

AGENT_DIR = Path(__file__).resolve().parent
AGENTS_DIR = AGENT_DIR.parent
REPO_ROOT = AGENTS_DIR.parent
if str(AGENTS_DIR) not in sys.path:
    sys.path.insert(0, str(AGENTS_DIR))

from common import (  # noqa: E402
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

LOG_DIR = AGENT_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
_ts = datetime.datetime.now().strftime("%Y%m%d@%H%M%S")
_fmt = logging.Formatter(
    "[%(asctime)s %(levelname)s %(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
_file = logging.FileHandler(LOG_DIR / f"run-{_ts}-{os.getpid()}.log", encoding="utf-8")
_file.setFormatter(_fmt)
_file.setLevel(logging.DEBUG)
_std = logging.StreamHandler(sys.stdout)
_std.setFormatter(_fmt)
_std.setLevel(logging.INFO)
logger.addHandler(_file)
logger.addHandler(_std)


# ---------- constants ----------

# Default image: CLI 2.1.119 (the original runs). Newer models may need a newer
# CLI, e.g. `--image elt-swe-claude:2.1.287` built with
# `--build-arg CLAUDE_CODE_VERSION=2.1.287`.
IMAGE_NAME = "elt-swe-claude"
NETWORK_NAME = "elt-docker_elt_network"
CONTAINER_WORKDIR = "/workspace"
CONTAINER_HOME = "/tmp/home"

# The SDK spawns this script instead of a local `claude`; it execs the CLI
# inside the task container named by $CLAUDE_CONTAINER. The image pins the
# CLI version (2.1.119, see elt-swe-claude/Dockerfile).
CLI_WRAPPER = AGENT_DIR / "docker_claude.sh"

# Host environment variables copied into the container when present (passed
# by name, so values never appear in the process list). The CLI needs one of
# the auth variables; CLAUDE_CODE_OAUTH_TOKEN comes from `claude setup-token`.
AUTH_ENV = (
    "CLAUDE_CODE_OAUTH_TOKEN",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX",
)
CONTAINER_ENV_PASSTHROUGH = AUTH_ENV + (
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_CUSTOM_HEADERS",
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
    "HOME": CONTAINER_HOME,
    "USER": "agent",
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
1. Initialize the DBT Project: Set up a new DBT project by configuring it with /workspace/config.yaml, and remove the example directory under the models directory.
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
# Final statuses that count as a completed attempt; anything else is retried
# on the next invocation without --overwrite.
KEEP_STATUSES = frozenset({"success", "error_max_turns"})
# Subscription usage limits: when an attempt ends because the limit was hit,
# the runner sleeps until the reported reset (plus a margin) and reruns the
# task from scratch. The floor lets syncs the aborted attempt triggered finish
# before the rerun resets the schema; the fallback is used when the CLI gave
# no reset time.
RATE_LIMIT_MARGIN_SEC = 120
RATE_LIMIT_MIN_PAUSE_SEC = 600
RATE_LIMIT_FALLBACK_PAUSE_SEC = 1800
RATE_LIMIT_TEXT = re.compile(
    r"usage limit reached|limit reached.{0,40}reset|rate_limit_error|hit your limit",
    re.IGNORECASE,
)
# File tools that modify files; the guard limits them to /workspace/elt.
WRITE_TOOL_MATCHER = "Write|Edit|MultiEdit|NotebookEdit"
WRITE_TOOLS = frozenset(WRITE_TOOL_MATCHER.split("|"))
PATH_INPUT_KEYS = ("file_path", "notebook_path")
# Host locations that hold answer keys or credentials. They do not exist in
# the container; a tool input that names one is reported by the audit.
FORBIDDEN_PATH_MARKERS = (str(REPO_ROOT), "evaluation/gt", "agent_results", "setup/destination")


# ---------- helpers ----------

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
    result, is recorded as an escape. Only escapes and forbidden-path markers
    make the run unclean.
    """
    # tool_use id -> whether its result was an error.
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


def _run(cmd: list[str], check: bool = True, **kw: Any) -> subprocess.CompletedProcess:
    logger.debug("$ %s", " ".join(cmd))
    return subprocess.run(cmd, check=check, text=True, capture_output=True, **kw)


def ensure_container(container_name: str, mnt_dir: Path, image: str = IMAGE_NAME) -> None:
    """(Re)create a fresh ELT container with `mnt_dir` bind-mounted to /workspace.

    Auth and related settings are passed by name (`-e NAME`), so their values
    do not appear in the process list.
    """
    env_args: list[str] = []
    for name in CONTAINER_ENV_PASSTHROUGH:
        if os.environ.get(name):
            env_args += ["-e", name]
    for name, value in CONTAINER_ENV_FIXED.items():
        env_args += ["-e", f"{name}={value}"]
    # Remove any existing container with this name.
    existing = _run(
        ["docker", "ps", "-aq", "-f", f"name=^{container_name}$"], check=False
    ).stdout.strip()
    if existing:
        logger.info("Removing existing container %s", container_name)
        _run(["docker", "rm", "-f", container_name], check=False)

    mnt_abs = str(mnt_dir.resolve())
    uid, gid = os.getuid(), os.getgid()
    logger.info("Starting container %s (mount %s -> %s)", container_name, mnt_abs, CONTAINER_WORKDIR)
    _run([
        "docker", "run", "-d", "--rm",
        "--name", container_name,
        "--network", NETWORK_NAME,
        # Run as the host user so files created in the container (dbt project,
        # .terraform, tfstate) stay editable by the host-side file tools and
        # removable by `--overwrite`. HOME must be writable for ~/.claude,
        # ~/.dbt etc.
        "--user", f"{uid}:{gid}",
        *env_args,
        "-v", f"{mnt_abs}:{CONTAINER_WORKDIR}",
        "-w", CONTAINER_WORKDIR,
        image,
        "sleep", "infinity",
    ])
    # The host uid has no passwd entry in the image; add one so tools that look
    # up the current user (Node's os.userInfo, Python's getpass) work.
    _run([
        "docker", "exec", "-u", "0", container_name, "sh", "-c",
        f"echo 'agent:x:{uid}:{gid}::{CONTAINER_HOME}:/bin/bash' >> /etc/passwd"
        f" && (getent group {gid} >/dev/null || echo 'agent:x:{gid}:' >> /etc/group)"
        f" && mkdir -p {CONTAINER_HOME} && chown {uid}:{gid} {CONTAINER_HOME}",
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


def set_task_namespace(
    config_path: Path, destination: str, db: str, database: str | None
) -> None:
    """Place the task in schema `db` of the shared `database`.

    Snowflake task templates default to one database per task with a fixed
    AIRBYTE_SCHEMA; Databricks/Redshift templates already use schema = task.
    """
    with config_path.open(encoding="utf-8") as f:
        config = yaml.safe_load(f)
    dest_config = config[destination]["config"]
    if database:
        dest_config["database"] = database
    dest_config["schema"] = db
    with config_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, sort_keys=False)


# ---------- trajectory capture ----------

class TrajectoryRecorder:
    """Collects SDK messages into a JSON-serializable transcript."""

    def __init__(self) -> None:
        self.turns: list[dict[str, Any]] = []
        self.num_turns: int = 0
        self.total_cost_usd: float | None = None
        self.usage: dict[str, Any] | None = None
        self.is_error: bool = False
        # ResultMessage subtype ("success", "error_max_turns", ...), or
        # "exception" when the session raised before producing one.
        self.status: str | None = None
        self.final_text: str = ""
        # Set when the CLI reports the usage limit as hit (rate_limit_event
        # with status "rejected", or an assistant message with error
        # "rate_limit"); resets_at is the Unix time the window reopens.
        self.rate_limited: bool = False
        self.rate_limit_resets_at: int | None = None
        # The CLI's error text for a failed run (ResultMessage.result or the
        # ResultError raised after it), kept apart from the agent's last text.
        self.error_text: str = ""

    def record_result_error(self, error: ResultError) -> None:
        """Absorb the ResultError the SDK raises after an error ResultMessage.

        The status already recorded from the ResultMessage (e.g.
        "error_max_turns") is kept rather than replaced by "exception".
        """
        logger.warning("Claude session ended with an error result: %s", error)
        self.is_error = True
        if self.status is None:
            self.status = error.subtype or "exception"
        self.error_text = error.result or self.error_text or str(error)
        if error.api_error_status == 429:
            self.rate_limited = True

    def finalize(self) -> None:
        """Derive the attempt status once the session has ended."""
        text = f"{self.final_text}\n{self.error_text}"
        match = RATE_LIMIT_TEXT.search(text)
        if self.is_error and (self.rate_limited or match):
            self.status = "rate_limited"
            if self.rate_limit_resets_at is None and match:
                # e.g. "Claude AI usage limit reached|1759212000"
                epoch = re.search(r"\|(\d{10})\b", text)
                if epoch:
                    self.rate_limit_resets_at = int(epoch.group(1))
        elif self.is_error and self.status == "success":
            # The CLI reports API failures as subtype "success" with
            # is_error set; those must be retried, not kept.
            self.status = "error_api"

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
        if isinstance(message, RateLimitEvent):
            info = message.rate_limit_info
            logger.info(
                "rate limit: status=%s type=%s utilization=%s resets_at=%s overage=%s",
                info.status, info.rate_limit_type, info.utilization,
                info.resets_at, info.overage_status,
            )
            if info.status == "rejected":
                self.rate_limited = True
                self.rate_limit_resets_at = info.resets_at or self.rate_limit_resets_at
            return
        if isinstance(message, AssistantMessage):
            if message.error == "rate_limit":
                self.rate_limited = True
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
            self.status = message.subtype
            if self.is_error and isinstance(getattr(message, "result", None), str):
                self.error_text = message.result
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
    database: str | None,
    experiment_id: str,
    output_root: Path,
    inputs_root: Path,
    model: str,
    max_turns: int,
    allow_overage: bool,
    image: str,
    overwrite: bool,
) -> "TrajectoryRecorder | None":
    """Run one task; returns its recorder, or None when it was skipped."""
    instance_id = f"{experiment_id}/{db}"
    out_dir = output_root / instance_id
    result_path = out_dir / "claude" / "result.json"

    if result_path.exists() and not overwrite:
        # Keep attempts the agent itself ended (including hitting max_turns);
        # rerun ones cut short by infrastructure (API/usage-limit errors, a
        # crashed CLI), which would otherwise be skipped forever.
        try:
            with open(result_path) as f:
                previous = json.load(f)
        except (OSError, json.JSONDecodeError):
            previous = {}
        status = previous.get("status") or ("success" if previous.get("finished") else None)
        if status in KEEP_STATUSES:
            logger.info("Skipping %s (result exists, status=%s)", instance_id, status)
            return None
        logger.info("Rerunning %s (previous status=%s)", instance_id, status)
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
        return await _run_task_body(
            db=db,
            destination=destination,
            credential=credential,
            database=database,
            instance_id=instance_id,
            experiment_id=experiment_id,
            out_dir=out_dir,
            result_path=result_path,
            inputs_root=inputs_root,
            model=model,
            max_turns=max_turns,
            allow_overage=allow_overage,
            image=image,
        )
    finally:
        logger.removeHandler(db_handler)
        db_handler.close()


async def _run_task_body(
    db: str,
    destination: str,
    credential: str | None,
    database: str | None,
    instance_id: str,
    experiment_id: str,
    out_dir: Path,
    result_path: Path,
    inputs_root: Path,
    model: str,
    max_turns: int,
    allow_overage: bool,
    image: str,
) -> TrajectoryRecorder:
    task_input_dir = inputs_root / db

    # Copy seed files into the mount dir, then point the task at its own
    # schema inside the shared experiment database.
    copy_initial_files(task_input_dir, out_dir)
    set_task_namespace(out_dir / "config.yaml", destination, db, database)

    # Reset the task namespace using the rewritten config. Credentials are not
    # copied into the mount, so resolve them from the task inputs.
    if credential is None:
        generated = task_input_dir / f"{destination}_credential.json"
        credential = str(generated) if generated.is_file() else None
    # A failed reset means stale warehouse state: abort this attempt before
    # any container, agent session, or evaluation can observe it.
    namespace = prepare_destination(destination, out_dir, credential)
    logger.info("Prepared %s destination namespace %s", destination, namespace)

    # Spin up the container.
    container_name = f"{experiment_id}-{db}"
    ensure_container(container_name, out_dir, image)

    system_prompt = adapt_prompt(SYSTEM_PROMPT_TEMPLATE, destination).format(
        db=db,
        container=container_name,
        # Name without the tag, so the prompt is identical across CLI versions.
        image=image.split(":", 1)[0],
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
        # `tools` fixes the built-in tool set (the CLI otherwise also offers
        # Cron*, worktree, AskUserQuestion, ...); `allowed_tools` only
        # auto-approves, and `disallowed_tools` is a second line of defense.
        tools=ALLOWED_TOOLS,
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
        await consume_session(
            query(prompt=prompt, options=options), recorder,
            stop_on_limit=not allow_overage,
        )
    except ResultError as e:
        recorder.record_result_error(e)
    except Exception as e:
        logger.exception("Claude session raised: %s", e)
        recorder.is_error = True
        recorder.status = "exception"
        recorder.final_text = f"ERROR: {e}"
    finally:
        stop_container(container_name)
    recorder.finalize()

    # Persist result. The audit is written even when the session raised, so a
    # partial trajectory is still checked.
    (out_dir / "claude").mkdir(parents=True, exist_ok=True)
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
        "status": recorder.status,
        "rate_limit_resets_at": recorder.rate_limit_resets_at,
        "num_turns": recorder.num_turns,
        "total_cost_usd": recorder.total_cost_usd,
        "usage": recorder.usage,
        "result": recorder.final_text,
        "error": recorder.error_text or None,
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
    return recorder


async def consume_session(
    messages: Any, recorder: TrajectoryRecorder, stop_on_limit: bool
) -> None:
    """Record a session's messages, optionally stopping at the usage limit.

    With `stop_on_limit`, the session is closed as soon as the CLI reports the
    limit as hit, instead of letting it continue on extra (pay-as-you-go)
    usage or fall back to another model; the attempt then ends as
    "rate_limited" and is paused and rerun.
    """
    async with contextlib.aclosing(messages) as stream:
        async for message in stream:
            recorder.record(message)
            if stop_on_limit and recorder.rate_limited:
                logger.warning(
                    "Usage limit reached (resets_at=%s); stopping the session "
                    "instead of continuing on extra usage",
                    recorder.rate_limit_resets_at,
                )
                recorder.is_error = True
                recorder.error_text = recorder.error_text or (
                    "Usage limit reached; session stopped by the runner"
                )
                break


def rate_limit_pause_seconds(resets_at: int | None, now: float | None = None) -> float:
    """Seconds to sleep before retrying after the usage limit was hit."""
    now = time.time() if now is None else now
    if resets_at is None:
        return RATE_LIMIT_FALLBACK_PAUSE_SEC
    return max(resets_at - now + RATE_LIMIT_MARGIN_SEC, RATE_LIMIT_MIN_PAUSE_SEC)


async def main_async(args: argparse.Namespace) -> None:
    base_id = f"{args.model.split('/')[-1]}-{args.suffix}" if args.suffix else args.model
    experiment_id = f"claude-{base_id}-{args.destination}"
    output_root = Path(args.output_dir)
    inputs_root = resolve_inputs_path(args.destination, args.test_path)
    elt_bench_root = resolve_benchmark_path(args.destination, args.elt_bench)

    if not any(os.environ.get(name) for name in AUTH_ENV):
        raise SystemExit(
            "No Claude auth for the container CLI. Run `~/.local/bin/claude "
            "setup-token` and export CLAUDE_CODE_OAUTH_TOKEN (or set "
            "ANTHROPIC_API_KEY)."
        )
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
    if args.shard:
        # Disjoint slices for running several runner processes in parallel.
        k, n = args.shard
        databases = databases[k::n]

    logger.info("Experiment %s — %d tasks", experiment_id, len(databases))
    for db in databases:
        overwrite = args.overwrite
        while True:
            try:
                recorder = await run_task(
                    db=db,
                    destination=args.destination,
                    credential=args.credential,
                    database=args.database,
                    experiment_id=experiment_id,
                    output_root=output_root,
                    inputs_root=inputs_root,
                    model=args.model,
                    max_turns=args.max_turns,
                    allow_overage=args.allow_overage,
                    image=args.image,
                    overwrite=overwrite,
                )
            except Exception:
                logger.exception("Task %s failed", db)
                break
            if recorder is None or recorder.status != "rate_limited":
                break
            pause = rate_limit_pause_seconds(recorder.rate_limit_resets_at)
            resume_at = datetime.datetime.fromtimestamp(time.time() + pause)
            logger.warning(
                "Usage limit reached during %s (resets_at=%s); pausing %.0f min "
                "until %s, then rerunning it from scratch",
                db, recorder.rate_limit_resets_at, pause / 60,
                resume_at.strftime("%Y-%m-%d %H:%M:%S"),
            )
            await asyncio.sleep(pause)
            # The rate-limited result is not a kept status, so the rerun
            # happens without --overwrite as well.
            overwrite = False


def _parse_shard(value: str) -> tuple[int, int]:
    try:
        k, n = (int(x) for x in value.split("/"))
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected K/N, got {value!r}")
    if not 0 <= k < n:
        raise argparse.ArgumentTypeError(f"need 0 <= K < N, got {value!r}")
    return k, n


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run Claude Code Agent on ELT-Bench.")
    p.add_argument("--destination", choices=destination_choices(), default="snowflake")
    p.add_argument(
        "--credential",
        help="Optional host-side destination credential JSON override.",
    )
    p.add_argument(
        "--database",
        help="Shared database/catalog holding one schema per task "
             "(default: 'elt' for snowflake; config value otherwise).",
    )
    p.add_argument("--model", default="claude-opus-4-7",
                   help="Claude model id (e.g. claude-opus-4-7, claude-sonnet-4-6).")
    p.add_argument("--suffix", "-s", default="eltbench", help="Experiment id suffix.")
    p.add_argument("--max_turns", type=int, default=100)
    p.add_argument("--test_path", "-t",
                   help="Per-task inputs directory (default: destination-specific).")
    p.add_argument("--elt_bench",
                   help="Task directory (default: elt-bench/<destination>).")
    p.add_argument("--output_dir", default=str(AGENT_DIR / "output"))
    p.add_argument("--only", default="", help="Comma-separated DBs to run (default: all).")
    p.add_argument("--limit", type=int, default=100,
                   help="Run only the first N DBs (after --only filter). "
                        "Default 20; pass 0 for no limit.")
    p.add_argument("--image", default=IMAGE_NAME,
                   help="Agent image (its tag pins the Claude Code CLI version); "
                        f"default {IMAGE_NAME} = CLI 2.1.119.")
    p.add_argument("--allow_overage", action="store_true",
                   help="Keep running on extra usage after the plan's usage "
                        "limit is hit (default: stop the task, pause until "
                        "the limit resets, then rerun it).")
    p.add_argument("--overwrite", action="store_true",
                   help="Rerun tasks even if result.json already exists.")
    p.add_argument("--shard", type=_parse_shard, default=None, metavar="K/N",
                   help="Run only every N-th task starting at K (0-based), e.g. "
                        "0/3, 1/3, 2/3 in three parallel processes.")
    args = p.parse_args()
    if args.database is None and args.destination == "snowflake":
        args.database = "elt"
    return args


def main() -> None:
    args = parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()

"""Codex Agent runner for ELT-Bench.

Uses the OpenAI Agents SDK (`openai-agents`) to drive a Codex-family model
(e.g. ``gpt-5-codex``) against each ELT task in ``../../elt-bench/``. For
every database it:

  1. Copies the destination-specific task inputs into the per-run output
     directory, points the task at its own schema (``--database`` holds one
     schema per task), and resets that namespace on the host (the agent
     never sees the separate credential file).
  2. Mounts that directory as ``/workspace`` in a fresh ``elt-swe``
     container on the ``elt-docker_elt_network`` network, running as the
     host user, read-only except for ``/workspace/elt`` (the only place the
     task allows changes).
  3. Drives an ``Agent`` with the two Codex-native tools shipped by the
     SDK — ``shell`` (``ShellTool`` in local-environment mode) and
     ``apply_patch`` (``ApplyPatchTool``). The ``ShellExecutor`` and
     ``ApplyPatchEditor`` we plug in route every operation through
     ``docker exec`` into the per-task container, so the agent only sees
     paths under ``/workspace`` and only its own container's filesystem.
     The host process owns the LLM call but never executes agent-issued
     work itself.
  4. Streams the run, captures the trajectory, and writes
     ``codex/result.json`` plus ``codex/stats.json`` with the transcript,
     turn count, token usage, and final status.

Usage:
    # API key, OpenAI Agents SDK harness (parallel --shard runs are fine)
    export OPENAI_API_KEY=...
    python run.py --destination snowflake --database codex_test --model openai/gpt-5-codex

    # ChatGPT plan via the Codex CLI (`codex exec` in the container; one
    # process per login, see codex_cli.py; image elt-swe-codex/Dockerfile)
    codex login --device-auth
    python run.py --backend cli --destination snowflake --database codex_cli_test --model gpt-6-astra
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import logging
import os
import posixpath
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import yaml
from agents import (
    Agent,
    ApplyPatchOperation,
    ApplyPatchResult,
    ApplyPatchTool,
    MaxTurnsExceeded,
    ModelSettings,
    Runner,
    ShellCallOutcome,
    ShellCommandOutput,
    ShellCommandRequest,
    ShellResult,
    ShellTool,
    apply_diff,
)

AGENT_DIR = Path(__file__).resolve().parent
AGENTS_DIR = AGENT_DIR.parent
if str(AGENTS_DIR) not in sys.path:
    sys.path.insert(0, str(AGENTS_DIR))

import codex_cli  # noqa: E402
from common import (  # noqa: E402
    adapt_prompt,
    destination_choices,
    get_destination,
    prepare_destination,
    resolve_benchmark_path,
    resolve_inputs_path,
)


# ---------- logging ----------

logger = logging.getLogger("codex_agent")
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

IMAGE_NAME = "elt-swe"
NETWORK_NAME = "elt-docker_elt_network"
CONTAINER_WORKDIR = "/workspace"
CONTAINER_ELT_DIR = f"{CONTAINER_WORKDIR}/elt"
CONTAINER_HOME = "/tmp/home"
DEFAULT_BASH_TIMEOUT_SEC = 600
FILE_IO_TIMEOUT_SEC = 120

SYSTEM_PROMPT_TEMPLATE = """You are a data engineer skilled in databases, SQL, and building ELT pipelines.

You are running inside Docker container `{container}` ({image} image on the
{network} network). Your working directory is `{container_workdir}`. Your
tools (`shell`, `apply_patch`) execute inside this container — relative paths
are resolved against {container_workdir}, and only files under
{container_workdir} are visible. You may only modify files under
{container_workdir}/elt.

Your goal is to build an ELT pipeline by extracting data from multiple sources, such as custom APIs, PostgreSQL, MongoDB, flat files, and the cloud service S3.
The extracted data will be loaded into a target system, Snowflake, followed by writing transformation queries to construct final tables for downstream use.
This task is divided into two stages:
1. Data Extraction and Loading – Using Airbyte's Terraform provider.
2. Data Transformation – Using the DBT Project workflow for Snowflake.

TOOL USAGE:
  - shell: run shell commands inside the container — terraform, dbt, python,
    psql, plus everyday utilities (cat, ls, grep, find, rg, head, tail) for
    reading and searching files.
  - apply_patch: create, update, move, or delete files using the V4A diff
    format. Use this for all file edits.

First, you should _always_ include a general thought about what you're going to do next.
Then issue the corresponding tool call. Wait for the tool result before continuing with more discussion and commands.
"""

# For the Codex CLI backend (passed as developer instructions on top of the
# CLI's own system prompt): same framing, the CLI's tool names.
CLI_SYSTEM_PROMPT_TEMPLATE = SYSTEM_PROMPT_TEMPLATE.replace(
    """TOOL USAGE:
  - shell: run shell commands inside the container — terraform, dbt, python,
    psql, plus everyday utilities (cat, ls, grep, find, rg, head, tail) for
    reading and searching files.
  - apply_patch: create, update, move, or delete files using the V4A diff
    format. Use this for all file edits.""",
    """TOOL USAGE:
  - Run shell commands inside the container — terraform, dbt, python, psql,
    plus everyday utilities (cat, ls, grep, find, rg, head, tail) for reading
    and searching files.
  - Use apply_patch for all file edits.""",
)
assert CLI_SYSTEM_PROMPT_TEMPLATE != SYSTEM_PROMPT_TEMPLATE

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
7. Trigger Sync Jobs: For each connection ID, trigger the job using the Airbyte API (refer to /workspace/documentation/trigger_job.md and use /workspace/config.yaml to retrieve the required values).
8. Monitor Job Status: After all jobs have been triggered, check the status of all jobs by running `python /workspace/check_job_status.py --server <server> --username <username> --password <password>` (replace <server>, <username>, and <password> with the actual values). Keep checking until all jobs have completed. Proceed to the next stage only if all data extraction and loading jobs are successful. If any job fails, fix it and retry before moving on.
9. Error Handling: If an error occurs, DO NOT modify any provided files. Instead, verify the configuration against the provided documentation and review previous steps to identify and resolve the issue. If the issue persists after multiple retries, terminate the task.

#  Stage 2: Data Transformation Hints#
1. Initialize the DBT Project: Set up a new DBT project by configuring it with /workspace/config.yaml, and remove the example directory under the models directory.
2. Understand the Data Model: Review data_model.yaml in /workspace to understand the required data models and their column descriptions. Then, write SQL queries to generate these defined data models, referring to the files in the /workspace/schemas directory to understand the schemas of source tables.
• Important: Write a separate query for each data model, and if using any DBT project variables, ensure they have already been declared.
3. Validate Table Locations: Ensure all SQL queries reference the correct database and schema names for source tables. If you encounter a "table not found" error, refer to /workspace/config.yaml to obtain the correct configuration. If the table does not exist, the issue is likely due to a failure in data extraction and loading in Stage 1, and you should return to Stage 1 to resolve it.
4. Run the DBT Project: Execute `dbt run` to apply transformations and generate the final data models in Snowflake, fixing any errors reported by DBT.
5. Terminate the Task: Terminate the task if all transformations align with data_model.yaml and the final tables in Snowflake are accurate and verified. Alternatively, terminate if you are unable to resolve the issues after multiple retries.

When done (or giving up), print a single final line:
    RESULT: SUCCESS   — pipeline built and final tables populated
    RESULT: FAIL: <short reason>
"""


# Final statuses that count as a completed attempt (the agent itself ended:
# it finished, or ran out of turns); anything else (API errors such as rate
# limits, crashes) is retried on the next invocation without --overwrite.
KEEP_STATUSES = frozenset({"success", "error_max_turns", "timeout"})
# CLI backend: pause after the plan's usage limit, as the Claude runner does.
RATE_LIMIT_MARGIN_SEC = 120
RATE_LIMIT_MIN_PAUSE_SEC = 600
RATE_LIMIT_FALLBACK_PAUSE_SEC = 1800
DEFAULT_MODEL = {"sdk": "openai/gpt-5.4-2026-03-05", "cli": "gpt-6-astra"}


# ---------- helpers ----------

def _run(cmd: list[str], check: bool = True, **kw: Any) -> subprocess.CompletedProcess:
    logger.debug("$ %s", " ".join(cmd))
    return subprocess.run(cmd, check=check, text=True, capture_output=True, **kw)


def ensure_container(
    container_name: str, mnt_dir: Path, image: str = IMAGE_NAME, home: str = CONTAINER_HOME
) -> None:
    """(Re)create a fresh ELT container with `mnt_dir` bind-mounted to /workspace."""
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
        # Run as the host user so files the agent creates stay host-owned
        # (editable, and removable by --overwrite).
        "--user", f"{uid}:{gid}",
        "-e", f"HOME={home}",
        "-e", "USER=agent",
        # Read-only task dir with only elt/ writable: enforces "you may only
        # modify files under /workspace/elt" for every tool, shell included.
        "-v", f"{mnt_abs}:{CONTAINER_WORKDIR}:ro",
        "-v", f"{mnt_abs}/elt:{CONTAINER_ELT_DIR}",
        "-w", CONTAINER_WORKDIR,
        image,
        "sleep", "infinity",
    ])
    # The host uid has no passwd entry in the image; add one so tools that look
    # up the current user work, and create a writable HOME (~/.dbt etc.).
    _run([
        "docker", "exec", "-u", "0", container_name, "sh", "-c",
        f"echo 'agent:x:{uid}:{gid}::{home}:/bin/bash' >> /etc/passwd"
        f" && (getent group {gid} >/dev/null || echo 'agent:x:{gid}:' >> /etc/group)"
        f" && mkdir -p {home} && chown {uid}:{gid} {home}",
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


async def _docker_exec(
    container_name: str,
    argv: list[str],
    *,
    stdin_data: str | None = None,
    timeout_sec: int = DEFAULT_BASH_TIMEOUT_SEC,
) -> tuple[int, str, str]:
    """Run `argv` inside `container_name` via `docker exec`. Returns (rc, stdout, stderr)."""
    flags = ["-w", CONTAINER_WORKDIR]
    if stdin_data is not None:
        flags.append("-i")
    proc = await asyncio.create_subprocess_exec(
        "docker", "exec", *flags, container_name, *argv,
        stdin=asyncio.subprocess.PIPE if stdin_data is not None else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out_b, err_b = await asyncio.wait_for(
            proc.communicate(stdin_data.encode("utf-8") if stdin_data is not None else None),
            timeout=timeout_sec,
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        raise
    return (
        proc.returncode if proc.returncode is not None else -1,
        out_b.decode("utf-8", errors="replace"),
        err_b.decode("utf-8", errors="replace"),
    )


# ---------- Codex-native tools (closed over the per-task container) ----------

def _resolve_writable(path: str) -> tuple[str, str | None]:
    """Resolve a model-supplied path for a file write.

    Relative paths are taken relative to /workspace (as the prompt says).
    Returns (absolute path, None) when the target is under /workspace/elt,
    else (path, error message) — the task forbids changes anywhere else.
    """
    real = posixpath.normpath(
        path if path.startswith("/") else posixpath.join(CONTAINER_WORKDIR, path)
    )
    if not real.startswith(CONTAINER_ELT_DIR + "/"):
        return real, f"you may only modify files under {CONTAINER_ELT_DIR}, got: {path}"
    return real, None


def make_shell_tool(container_name: str) -> ShellTool:
    """Return a ShellTool (next-generation) whose executor runs commands inside `container_name`.

    The model emits a list of shell command strings; we run each via
    ``docker exec bash -lc`` and return a ``ShellResult`` with per-command
    stdout/stderr/exit-code.
    """

    async def executor(req: ShellCommandRequest) -> ShellResult:
        action = req.data.action
        commands = list(action.commands)
        timeout_sec = (
            DEFAULT_BASH_TIMEOUT_SEC
            if not action.timeout_ms
            else max(1, int(action.timeout_ms / 1000))
        )
        outputs: list[ShellCommandOutput] = []
        for cmd in commands:
            try:
                rc, out, err = await _docker_exec(
                    container_name,
                    ["bash", "-lc", cmd],
                    timeout_sec=timeout_sec,
                )
            except asyncio.TimeoutError:
                outputs.append(
                    ShellCommandOutput(
                        command=cmd,
                        stdout="",
                        stderr=f"TIMEOUT after {timeout_sec}s",
                        outcome=ShellCallOutcome(type="timeout"),
                    )
                )
                # Stop running further commands after a timeout.
                break
            outputs.append(
                ShellCommandOutput(
                    command=cmd,
                    stdout=out,
                    stderr=err,
                    outcome=ShellCallOutcome(type="exit", exit_code=rc),
                )
            )
        return ShellResult(output=outputs, max_output_length=action.max_output_length)

    return ShellTool(executor=executor, environment={"type": "local"})


class ContainerApplyPatchEditor:
    """ApplyPatchEditor that performs file ops inside a Docker container.

    Uses ``apply_diff`` from the Agents SDK to materialize V4A diffs, then
    routes the resulting reads/writes through ``docker exec``. All paths are
    constrained to /workspace.
    """

    def __init__(self, container_name: str) -> None:
        self.container_name = container_name

    async def _read(self, path: str) -> str:
        rc, out, err = await _docker_exec(
            self.container_name, ["cat", path], timeout_sec=FILE_IO_TIMEOUT_SEC
        )
        if rc != 0:
            raise RuntimeError(f"cat {path} failed (rc={rc}): {err.strip()}")
        return out

    async def _write(self, path: str, text: str) -> None:
        qpath = shlex.quote(path)
        cmd = f"mkdir -p \"$(dirname {qpath})\" && cat > {qpath}"
        rc, _, err = await _docker_exec(
            self.container_name,
            ["bash", "-lc", cmd],
            stdin_data=text,
            timeout_sec=FILE_IO_TIMEOUT_SEC,
        )
        if rc != 0:
            raise RuntimeError(f"write {path} failed (rc={rc}): {err.strip()}")

    async def _delete(self, path: str) -> None:
        rc, _, err = await _docker_exec(
            self.container_name, ["rm", "-f", path], timeout_sec=FILE_IO_TIMEOUT_SEC
        )
        if rc != 0:
            raise RuntimeError(f"rm {path} failed (rc={rc}): {err.strip()}")

    async def _move(self, src: str, dst: str) -> None:
        qsrc, qdst = shlex.quote(src), shlex.quote(dst)
        rc, _, err = await _docker_exec(
            self.container_name,
            ["bash", "-lc", f"mkdir -p \"$(dirname {qdst})\" && mv {qsrc} {qdst}"],
            timeout_sec=FILE_IO_TIMEOUT_SEC,
        )
        if rc != 0:
            raise RuntimeError(f"mv {src} -> {dst} failed (rc={rc}): {err.strip()}")

    async def create_file(self, op: ApplyPatchOperation) -> ApplyPatchResult:
        path, bad = _resolve_writable(op.path)
        if bad:
            return ApplyPatchResult(status="failed", output=bad)
        try:
            text = apply_diff("", op.diff or "", mode="create")
            await self._write(path, text)
        except Exception as e:
            return ApplyPatchResult(status="failed", output=f"create_file failed: {e}")
        return ApplyPatchResult(status="completed", output=f"created {path}")

    async def update_file(self, op: ApplyPatchOperation) -> ApplyPatchResult:
        path, bad = _resolve_writable(op.path)
        if bad:
            return ApplyPatchResult(status="failed", output=bad)
        move_to = None
        if op.move_to is not None:
            move_to, bad = _resolve_writable(op.move_to)
            if bad:
                return ApplyPatchResult(status="failed", output=bad)
        try:
            existing = await self._read(path)
            new_text = apply_diff(existing, op.diff or "")
            await self._write(path, new_text)
            if move_to and move_to != path:
                await self._move(path, move_to)
                return ApplyPatchResult(
                    status="completed",
                    output=f"updated and moved {path} -> {move_to}",
                )
        except Exception as e:
            return ApplyPatchResult(status="failed", output=f"update_file failed: {e}")
        return ApplyPatchResult(status="completed", output=f"updated {path}")

    async def delete_file(self, op: ApplyPatchOperation) -> ApplyPatchResult:
        path, bad = _resolve_writable(op.path)
        if bad:
            return ApplyPatchResult(status="failed", output=bad)
        try:
            await self._delete(path)
        except Exception as e:
            return ApplyPatchResult(status="failed", output=f"delete_file failed: {e}")
        return ApplyPatchResult(status="completed", output=f"deleted {path}")


def make_apply_patch_tool(container_name: str) -> ApplyPatchTool:
    return ApplyPatchTool(editor=ContainerApplyPatchEditor(container_name))


def build_tools(container_name: str) -> list[Any]:
    return [
        make_shell_tool(container_name),
        make_apply_patch_tool(container_name),
    ]


# ---------- trajectory capture ----------

class TrajectoryRecorder:
    """Collects Agents SDK stream events into a JSON-serializable transcript."""

    def __init__(self) -> None:
        self.turns: list[dict[str, Any]] = []
        self.num_turns: int = 0
        self.total_cost_usd: float | None = None
        self.usage: dict[str, Any] | None = None
        self.is_error: bool = False
        # "success", "error_max_turns", or "error" (API/model failures, worth
        # retrying); set by finalize().
        self.status: str | None = None
        self.final_text: str = ""
        self.error_text: str = ""

    def finalize(self, exc: BaseException | None) -> None:
        """Derive the attempt status once the run has ended."""
        if exc is None:
            self.status = "success"
        elif isinstance(exc, MaxTurnsExceeded):
            self.status = "error_max_turns"
        else:
            self.status = "error"
        self.is_error = self.status != "success"

    @staticmethod
    def _safe_dump(obj: Any) -> Any:
        if hasattr(obj, "model_dump"):
            try:
                return obj.model_dump(mode="json")
            except Exception:
                pass
        if hasattr(obj, "to_dict"):
            try:
                return obj.to_dict()
            except Exception:
                pass
        return repr(obj)

    @staticmethod
    def _attr(obj: Any, key: str, default: Any = None) -> Any:
        """Read `key` from either a pydantic-style attr or a plain dict."""
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    def record_run_item(self, item: Any) -> None:
        item_type = getattr(item, "type", item.__class__.__name__)
        raw = getattr(item, "raw_item", None)

        if item_type == "message_output_item":
            text = ""
            content = self._attr(raw, "content")
            if isinstance(content, list):
                for c in content:
                    t = self._attr(c, "text")
                    if isinstance(t, str):
                        text += t
            elif isinstance(content, str):
                text = content
            if text:
                self.final_text = text
                logger.debug("assistant message:\n%s", text)
                logger.info("assistant: %s", text.strip()[:500])
            self.turns.append({
                "type": "message",
                "role": "assistant",
                "text": text,
                "raw": self._safe_dump(raw),
            })

        elif item_type == "tool_call_item":
            self.num_turns += 1
            raw_type = self._attr(raw, "type")
            is_shell_call = (
                raw_type in ("local_shell_call", "shell_call")
                or (isinstance(raw_type, str) and raw_type.endswith("shell_call"))
                or self._attr(raw, "action") is not None
                and isinstance(self._attr(self._attr(raw, "action"), "commands"), list)
            )
            if is_shell_call:
                name = "shell"
                action = self._attr(raw, "action")
                args = self._safe_dump(action) if action is not None else None
            else:
                name = (
                    self._attr(raw, "name")
                    or self._attr(raw, "tool_name")
                    or raw_type
                    or "?"
                )
                args = self._attr(raw, "arguments")
                if args is None:
                    args = self._attr(raw, "input")
            args_preview = args if isinstance(args, str) else json.dumps(args, default=str)
            logger.debug("tool_call %s args:\n%s", name, args_preview)
            logger.info("tool_call %s: %s", name, args_preview[:300])
            self.turns.append({
                "type": "tool_call",
                "name": name,
                "arguments": args,
                "raw": self._safe_dump(raw),
            })

        elif item_type == "tool_call_output_item":
            output = getattr(item, "output", None)
            if output is None:
                output = self._attr(raw, "output")
            text = output if isinstance(output, str) else json.dumps(output, default=str)
            preview = text.strip().replace("\n", " ⏎ ")[:500]
            logger.debug("tool_output:\n%s", text)
            logger.info("tool_output: %s", preview)
            self.turns.append({
                "type": "tool_output",
                "output": output,
                "raw": self._safe_dump(raw),
            })

        elif item_type == "reasoning_item":
            self.turns.append({
                "type": "reasoning",
                "raw": self._safe_dump(raw),
            })

        else:
            self.turns.append({"type": item_type, "raw": self._safe_dump(raw)})

    def record_error(self, exc: BaseException) -> None:
        # Kept apart from final_text, which stays the agent's last message.
        self.error_text = f"{type(exc).__name__}: {exc}"
        logger.warning("run ended with %s", self.error_text)
        self.turns.append({"type": "error", "error": repr(exc)})

    def finalize_usage(self, run_result: Any) -> None:
        usage_obj: Any = None
        try:
            ctx = getattr(run_result, "context_wrapper", None)
            if ctx is not None:
                usage_obj = getattr(ctx, "usage", None)
        except Exception:
            usage_obj = None
        if usage_obj is None:
            return
        snapshot: dict[str, Any] = {}
        for field in (
            "requests",
            "input_tokens",
            "output_tokens",
            "total_tokens",
        ):
            val = getattr(usage_obj, field, None)
            if val is not None:
                snapshot[field] = val
        details = getattr(usage_obj, "input_tokens_details", None)
        if details is not None:
            snapshot["input_tokens_details"] = self._safe_dump(details)
        details = getattr(usage_obj, "output_tokens_details", None)
        if details is not None:
            snapshot["output_tokens_details"] = self._safe_dump(details)
        if snapshot:
            self.usage = snapshot

    def compute_cost(self, model: str) -> None:
        """Price the run's usage with LiteLLM's model price table, if known."""
        if not self.usage:
            return
        try:
            import litellm
            info = litellm.get_model_info(model.split("/", 1)[-1])
        except Exception:
            logger.warning("no price information for %s; total_cost_usd left empty", model)
            return
        input_tokens = self.usage.get("input_tokens") or 0
        cached = ((self.usage.get("input_tokens_details") or {}).get("cached_tokens")) or 0
        output_tokens = self.usage.get("output_tokens") or 0
        input_cost = info.get("input_cost_per_token") or 0
        cache_cost = info.get("cache_read_input_token_cost")
        if cache_cost is None:
            cache_cost = input_cost
        self.total_cost_usd = (
            (input_tokens - cached) * input_cost
            + cached * cache_cost
            + output_tokens * (info.get("output_cost_per_token") or 0)
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
    overwrite: bool,
    backend: str = "sdk",
    image: str = IMAGE_NAME,
    task_timeout: int = 7200,
    reasoning_effort: str | None = None,
) -> Any:
    instance_id = f"{experiment_id}/{db}"
    out_dir = output_root / instance_id
    result_path = out_dir / "codex" / "result.json"

    if result_path.exists() and not overwrite:
        # Keep attempts the agent itself ended; rerun ones cut short by
        # infrastructure (API errors, crashes), which would otherwise be
        # skipped forever.
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
            backend=backend,
            image=image,
            task_timeout=task_timeout,
            reasoning_effort=reasoning_effort,
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
    backend: str = "sdk",
    image: str = IMAGE_NAME,
    task_timeout: int = 7200,
    reasoning_effort: str | None = None,
) -> Any:
    task_input_dir = inputs_root / db

    # Copy seed files into the mount dir, then point the task at its own
    # schema inside the shared experiment database.
    copy_initial_files(task_input_dir, out_dir)
    (out_dir / "elt").mkdir(exist_ok=True)
    set_task_namespace(out_dir / "config.yaml", destination, db, database)

    # Reset the task namespace using the rewritten config. Credentials are not
    # copied into the mount, so resolve them from the task inputs. A failed
    # reset means stale warehouse state: abort this attempt.
    if credential is None:
        generated = task_input_dir / f"{destination}_credential.json"
        credential = str(generated) if generated.is_file() else None
    namespace = prepare_destination(destination, out_dir, credential)
    logger.info("Prepared %s destination namespace %s", destination, namespace)

    # Spin up the container.
    container_name = f"{experiment_id}-{db}"
    cli = backend == "cli"
    ensure_container(container_name, out_dir, image, codex_cli.CLI_HOME if cli else CONTAINER_HOME)

    system_prompt = adapt_prompt(
        CLI_SYSTEM_PROMPT_TEMPLATE if cli else SYSTEM_PROMPT_TEMPLATE, destination
    ).format(
        db=db,
        container=container_name,
        # Name without the tag, so the prompt does not change with the CLI version.
        image=image.split(":", 1)[0],
        network=NETWORK_NAME,
        container_workdir=CONTAINER_WORKDIR,
    )
    destination_name = get_destination(destination).display_name
    prompt = (
        f"Build the ELT pipeline for the `{db}` now. "
        f"All configuration values (including the {destination_name} namespace) "
        "must come from /workspace/config.yaml.\n\n"
        f"{adapt_prompt(TASK_INSTRUCTION, destination)}"
    )

    if cli:
        recorder = await _run_cli(
            container_name, model, system_prompt, prompt, task_timeout, reasoning_effort
        )
        return _persist(recorder, instance_id, db, model, out_dir, result_path)

    tools = build_tools(container_name)

    agent = Agent(
        name=f"codex-{db}",
        instructions=system_prompt,
        tools=tools,
        model=model,
        model_settings=ModelSettings(),
    )

    recorder = TrajectoryRecorder()

    run_result: Any = None
    run_exc: BaseException | None = None
    try:
        run_result = Runner.run_streamed(agent, input=prompt, max_turns=max_turns)
        async for event in run_result.stream_events():
            etype = getattr(event, "type", "")
            if etype == "run_item_stream_event":
                try:
                    recorder.record_run_item(event.item)
                except Exception:
                    logger.exception("recorder failed for item %r", event.item)
            elif etype == "agent_updated_stream_event":
                new_agent = getattr(event, "new_agent", None)
                logger.debug("agent updated: %r", new_agent)
            # raw_response_event tokens are noisy; ignore.
    except Exception as e:
        run_exc = e
        recorder.record_error(e)
    finally:
        if run_result is not None:
            try:
                recorder.finalize_usage(run_result)
            except Exception:
                logger.exception("failed to read run usage")
            if not recorder.final_text:
                final = getattr(run_result, "final_output", None)
                if final:
                    recorder.final_text = str(final)
        stop_container(container_name)
    recorder.finalize(run_exc)
    recorder.compute_cost(model)
    logger.info("run status: %s", recorder.status)
    return _persist(recorder, instance_id, db, model, out_dir, result_path)


async def _run_cli(
    container_name: str,
    model: str,
    system_prompt: str,
    prompt: str,
    task_timeout: int,
    reasoning_effort: str | None,
) -> Any:
    """Run the task with the Codex CLI and the host's ChatGPT-plan login."""
    codex_cli.seed_auth(container_name, os.getuid(), os.getgid())
    try:
        recorder = await codex_cli.run_codex_exec(
            container_name, model, system_prompt, prompt, task_timeout, reasoning_effort
        )
    finally:
        codex_cli.sync_auth_back(container_name)
        stop_container(container_name)
    # Same pricing as the SDK backend (notional: the plan is billed by usage
    # limits, not per token); stays empty for models without a known price.
    pricing = TrajectoryRecorder()
    pricing.usage = recorder.sdk_style_usage()
    pricing.compute_cost(model)
    recorder.total_cost_usd = pricing.total_cost_usd
    recorder.reasoning_effort = reasoning_effort or "model default"
    if recorder.unexpected_items:
        logger.warning("unexpected item types: %s", sorted(set(recorder.unexpected_items)))
    logger.info("run status: %s", recorder.status)
    return recorder


def _persist(recorder: Any, instance_id: str, db: str, model: str, out_dir: Path, result_path: Path) -> Any:
    (out_dir / "codex").mkdir(parents=True, exist_ok=True)
    result_json = {
        "instance_id": instance_id,
        "db": db,
        "model": model,
        "finished": not recorder.is_error,
        "status": recorder.status,
        "error": recorder.error_text or None,
        "num_turns": recorder.num_turns,
        "total_cost_usd": recorder.total_cost_usd,
        "usage": recorder.usage,
        "result": recorder.final_text,
        "trajectory": recorder.turns,
    }
    if hasattr(recorder, "unexpected_items"):
        result_json["unexpected_items"] = sorted(set(recorder.unexpected_items))
        result_json["rate_limit_resets_at"] = recorder.rate_limit_resets_at
        result_json["reasoning_effort"] = getattr(recorder, "reasoning_effort", None)
    with open(result_path, "w") as f:
        json.dump(result_json, f, indent=2, default=str)
    logger.info("Wrote %s", result_path)

    stats_path = out_dir / "codex" / "stats.json"
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


def rate_limit_pause_seconds(resets_at: int | None, now: float | None = None) -> float:
    """Seconds to sleep before retrying after the plan's usage limit was hit."""
    now = time.time() if now is None else now
    if resets_at is None:
        return RATE_LIMIT_FALLBACK_PAUSE_SEC
    return max(resets_at - now + RATE_LIMIT_MARGIN_SEC, RATE_LIMIT_MIN_PAUSE_SEC)


async def main_async(args: argparse.Namespace) -> None:
    base_id = f"{args.model.split('/')[-1]}-{args.suffix}" if args.suffix else args.model.split("/")[-1]
    prefix = "codex-cli" if args.backend == "cli" else "codex"
    experiment_id = f"{prefix}-{base_id}-{args.destination}"
    output_root = Path(args.output_dir)
    inputs_root = resolve_inputs_path(args.destination, args.test_path)
    elt_bench_root = resolve_benchmark_path(args.destination, args.elt_bench)

    if args.backend == "cli":
        # One process per login: refresh tokens rotate (see codex_cli).
        login_lock = codex_cli.LoginLock()
        login_lock.acquire()
    elif not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is not set.")
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
                    overwrite=overwrite,
                    backend=args.backend,
                    image=args.image,
                    task_timeout=args.task_timeout,
                    reasoning_effort=args.reasoning_effort,
                )
            except Exception:
                logger.exception("Task %s failed", db)
                break
            status = getattr(recorder, "status", None)
            if status == "auth_error":
                raise SystemExit(
                    f"Codex login failed during {db}; run `codex login --device-auth` "
                    "and start the runner again (finished tasks are skipped)."
                )
            if status != "rate_limited":
                break
            pause = rate_limit_pause_seconds(recorder.rate_limit_resets_at)
            logger.warning(
                "Usage limit reached during %s (resets_at=%s); pausing %.0f min, "
                "then rerunning it from scratch", db, recorder.rate_limit_resets_at, pause / 60,
            )
            await asyncio.sleep(pause)
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
    p = argparse.ArgumentParser(description="Run Codex on ELT-Bench (Agents SDK + API key, or Codex CLI + ChatGPT plan).")
    p.add_argument("--backend", choices=("sdk", "cli"), default="sdk",
                   help="sdk: OpenAI Agents SDK with OPENAI_API_KEY; cli: `codex exec` in the "
                        "container with the ChatGPT-plan login in ~/.codex/auth.json "
                        "(single process only).")
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
    p.add_argument("--model", default=None,
                   help="Model id (default: openai/gpt-5.4-2026-03-05 for sdk, gpt-6-astra for cli).")
    p.add_argument("--image", default=None,
                   help=f"Agent image (default: {IMAGE_NAME} for sdk, {codex_cli.CLI_IMAGE} for cli).")
    p.add_argument("--task_timeout", type=int, default=7200,
                   help="cli: wall-clock limit per task in seconds (codex exec has no turn limit).")
    p.add_argument("--reasoning_effort", default=None,
                   help="cli: model_reasoning_effort override (default: the model's own).")
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
                        "Default 100; pass 0 for no limit.")
    p.add_argument("--overwrite", action="store_true",
                   help="Rerun tasks even if result.json already exists.")
    p.add_argument("--shard", type=_parse_shard, default=None, metavar="K/N",
                   help="Run only every N-th task starting at K (0-based), e.g. "
                        "0/3, 1/3, 2/3 in three parallel processes.")
    args = p.parse_args()
    args.model = args.model or DEFAULT_MODEL[args.backend]
    args.image = args.image or (codex_cli.CLI_IMAGE if args.backend == "cli" else IMAGE_NAME)
    if args.database is None and args.destination == "snowflake":
        args.database = "elt"
    return args


def main() -> None:
    args = parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()

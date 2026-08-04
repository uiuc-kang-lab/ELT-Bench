"""Claude Code Agent runner for ELT-Bench.

Uses the `claude-agent-sdk` Python SDK to drive Claude against each ELT task
in `../../elt-bench/`. For every database it:

  1. Resets the configured Snowflake, Databricks, or Redshift namespace.
  2. Copies the destination-specific task inputs into the
     per-run output directory, which is mounted as `/workspace` inside a
     fresh `elt_agent-image` Docker container on the `elt-docker_elt_network`.
  3. Launches a Claude Agent SDK session with its `cwd` set to that output
     directory. File tools (Read/Write/Edit/Glob/Grep) operate on the host
     bind mount and appear inside the container automatically. Shell commands
     are routed through a custom `container_bash` MCP tool that runs
     `docker exec` inside the task's container — the native Bash tool is NOT
     exposed, so the agent cannot run arbitrary host commands.
  4. Streams the trajectory and writes `claude/result.json` with the
     transcript, turn count, cost, and final status.

Usage:
    export ANTHROPIC_API_KEY=...           # or use any Claude Code-supported auth
    python run.py --destination databricks --suffix eltbench --model claude-opus-4-7
"""

from __future__ import annotations

import argparse
import asyncio
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
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    create_sdk_mcp_server,
    query,
    tool,
)

AGENTS_DIR = Path(__file__).resolve().parents[1]
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

IMAGE_NAME = "elt-swe"
NETWORK_NAME = "elt-docker_elt_network"
CONTAINER_WORKDIR = "/workspace"

# Pinned to match the Claude Code CLI version used in the original benchmark
# runs (claude_code_version=2.1.119 in logs/*.log init messages), rather than
# the claude-agent-sdk's bundled CLI version.
CLI_PATH = os.path.expanduser("~/.local/bin/claude")

SYSTEM_PROMPT_TEMPLATE = """You are a data engineer skilled in databases, SQL, and building ELT pipelines.
Your working directory (`cwd`) is the host-side mount of `{container_workdir}` inside a Docker container named `{container}`, running the `{image}` image on the `{network}` network. Any file you create or edit in the cwd appears immediately inside the container at `{container_workdir}`. The cwd contains all the necessary information for your tasks. However, you are only allowed to modify files in `/workspace/elt` (i.e. `<cwd>/elt` on the host).
Your goal is to build an ELT pipeline by extracting data from multiple sources, such as custom APIs, PostgreSQL, MongoDB, flat files, and the cloud service S3.
The extracted data will be loaded into a target system, Databricks, followed by writing transformation queries to construct final tables for downstream use.
This task is divided into two stages:
1. Data Extraction and Loading – Using Airbyte's Terraform provider.
2. Data Transformation – Using the DBT Project workflow for Databricks.

TOOL USAGE:
  - Read / Write / Edit / Glob / Grep: operate on files under the cwd. Prefer these over shell utilities for file I/O.
  - container_bash: run a shell command inside the `{container}` container (cwd = `{container_workdir}`). All commands — terraform, dbt, airbyte-cli, python, psql, etc. — must go through this tool. You do NOT have a host shell; do not try to call `docker`, `docker exec`, or any other host command directly.

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

# Subset of native Claude Code tools we expose to the agent. Bash is deliberately
# excluded — the agent must run shell commands inside the container via the
# `container_bash` MCP tool registered per task in `run_task`.
NATIVE_ALLOWED_TOOLS = ["Read", "Write", "Edit", "Glob", "Grep"]
CONTAINER_BASH_MCP_SERVER = "elt"
CONTAINER_BASH_TOOL = f"mcp__{CONTAINER_BASH_MCP_SERVER}__container_bash"
DEFAULT_BASH_TIMEOUT_SEC = 600


# ---------- helpers ----------

def _run(cmd: list[str], check: bool = True, **kw: Any) -> subprocess.CompletedProcess:
    logger.debug("$ %s", " ".join(cmd))
    return subprocess.run(cmd, check=check, text=True, capture_output=True, **kw)


def ensure_container(container_name: str, mnt_dir: Path) -> None:
    """(Re)create a fresh ELT container with `mnt_dir` bind-mounted to /workspace."""
    # Remove any existing container with this name.
    existing = _run(
        ["docker", "ps", "-aq", "-f", f"name=^{container_name}$"], check=False
    ).stdout.strip()
    if existing:
        logger.info("Removing existing container %s", container_name)
        _run(["docker", "rm", "-f", container_name], check=False)

    mnt_abs = str(mnt_dir.resolve())
    logger.info("Starting container %s (mount %s -> %s)", container_name, mnt_abs, CONTAINER_WORKDIR)
    _run([
        "docker", "run", "-d", "--rm",
        "--name", container_name,
        "--network", NETWORK_NAME,
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
    # Prep Databricks DB.
    task_input_dir = inputs_root / db
    try:
        namespace = prepare_destination(destination, task_input_dir, credential)
        logger.info("Prepared %s destination namespace %s", destination, namespace)
    except Exception as e:  # pragma: no cover
        logger.warning("Destination preparation for %s failed: %s", db, e)

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

    @tool(
        "container_bash",
        (
            f"Run a bash command inside the Docker container `{container_name}` "
            f"(cwd = {CONTAINER_WORKDIR}). Returns stdout, stderr, and exit code. "
            "Use this for terraform, dbt, python, psql, and any other shell work. "
            f"Optional `timeout_sec` (default {DEFAULT_BASH_TIMEOUT_SEC}s)."
        ),
        {"command": str, "timeout_sec": int},
    )
    async def container_bash(args: dict[str, Any]) -> dict[str, Any]:
        command = args["command"]
        timeout_sec = int(args.get("timeout_sec") or DEFAULT_BASH_TIMEOUT_SEC)
        proc = await asyncio.create_subprocess_exec(
            "docker", "exec", "-w", CONTAINER_WORKDIR, container_name,
            "bash", "-lc", command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(), timeout=timeout_sec
            )
            exit_code = proc.returncode
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return {
                "content": [{
                    "type": "text",
                    "text": f"TIMEOUT after {timeout_sec}s: {command!r}",
                }],
                "isError": True,
            }
        out = stdout_b.decode("utf-8", errors="replace")
        err = stderr_b.decode("utf-8", errors="replace")
        body = f"exit_code: {exit_code}\n"
        if out:
            body += f"stdout:\n{out}"
        if err:
            body += ("\n" if out else "") + f"stderr:\n{err}"
        return {
            "content": [{"type": "text", "text": body}],
            "isError": exit_code != 0,
        }

    mcp_server = create_sdk_mcp_server(
        name=CONTAINER_BASH_MCP_SERVER,
        version="1.0.0",
        tools=[container_bash],
    )

    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        cwd=str(out_dir.resolve()),
        allowed_tools=NATIVE_ALLOWED_TOOLS + [CONTAINER_BASH_TOOL],
        mcp_servers={CONTAINER_BASH_MCP_SERVER: mcp_server},
        permission_mode="acceptEdits",
        max_turns=max_turns,
        model=model,
        cli_path=CLI_PATH,
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
    result_json = {
        "instance_id": instance_id,
        "db": db,
        "model": model,
        "finished": not recorder.is_error,
        "num_turns": recorder.num_turns,
        "total_cost_usd": recorder.total_cost_usd,
        "usage": recorder.usage,
        "result": recorder.final_text,
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
        except Exception:
            logger.exception("Task %s failed", db)


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
    return p.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()

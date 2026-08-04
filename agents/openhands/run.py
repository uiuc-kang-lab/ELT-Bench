"""OpenHands Agent runner for ELT-Bench.

Uses the OpenHands Agent SDK (`openhands-sdk`) to drive an OpenHands agent
against each ELT task in `../../elt-bench/`. For every database it:

  1. Resets the configured Snowflake, Databricks, or Redshift namespace on
     the host (the agent never sees the separate credential file).
  2. Copies the destination-specific task inputs into the
     per-run output directory, which is mounted as `/workspace` inside a
     fresh `elt-swe` Docker container on the `elt-docker_elt_network`.
  3. Inside that container, starts `openhands-agent-server` on port 8000
     (published to the host as `AGENT_SERVER_PORT`). All agent tool calls
     (file_editor / terminal / grep / glob) execute INSIDE the container,
     sandboxed by the bind-mount: they cannot see anything on the host
     other than `/workspace`.
  4. The host process drives the LLM and Conversation, talks to the
     in-container agent-server via `RemoteWorkspace`, and writes
     `openhands/result.json` with the trajectory, turn count, cost, and
     final status.

Usage:
    export LLM_API_KEY=...                 # provider key (Anthropic, OpenAI, ...)
    python run.py --destination redshift --model anthropic/claude-opus-4-7
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import logging
import os
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from openhands.sdk import (
    LLM,
    Agent,
    Conversation,
    Message,
    TextContent,
)
from openhands.sdk.event import (
    ActionEvent,
    AgentErrorEvent,
    Event,
    MessageEvent,
    ObservationEvent,
)
from openhands.sdk.tool import Tool
from openhands.sdk.workspace.remote.base import RemoteWorkspace

# Even though tool *execution* happens inside the container, the host still
# needs the Action/Observation classes registered with pydantic so the
# RemoteConversation websocket loop can deserialize events the server emits
# (FileEditorAction, TerminalObservation, etc.). Importing these modules
# triggers their registration via DiscriminatedUnionMixin.
import openhands.tools.file_editor  # noqa: F401
import openhands.tools.terminal  # noqa: F401
import openhands.tools.grep  # noqa: F401
import openhands.tools.glob  # noqa: F401

from openhands.sdk.context.condenser import LLMSummarizingCondenser

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

logger = logging.getLogger("openhands_agent")
logger.setLevel(logging.DEBUG)

LOG_DIR = AGENTS_DIR / "logs/openhands"
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

IMAGE_NAME = "elt-swe-openhands"
NETWORK_NAME = "elt-docker_elt_network"
CONTAINER_WORKDIR = "/workspace"
AGENT_SERVER_PORT = 18000  # host port; 8000 is taken by airbyte-abctl-control-plane
AGENT_SERVER_READY_TIMEOUT_SEC = 120  # cold start ~10s; padded for slower hosts

SYSTEM_PROMPT_TEMPLATE = """You are a data engineer skilled in databases, SQL, and building ELT pipelines.

You are running inside Docker container `{container}` ({image} image on the
{network} network). Your working directory is `{container_workdir}`. All your
tools (file_editor / terminal / grep / glob) operate inside this container —
paths are relative to {container_workdir}, and only files under
{container_workdir} are visible. You may only modify files under
{container_workdir}/elt.

Your goal is to build an ELT pipeline by extracting data from multiple sources, such as custom APIs, PostgreSQL, MongoDB, flat files, and the cloud service S3.
The extracted data will be loaded into a target system, Snowflake, followed by writing transformation queries to construct final tables for downstream use.
This task is divided into two stages:
1. Data Extraction and Loading – Using Airbyte's Terraform provider.
2. Data Transformation – Using the DBT Project workflow for Snowflake.


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

# ---------- helpers ----------

def _run(cmd: list[str], check: bool = True, **kw: Any) -> subprocess.CompletedProcess:
    logger.debug("$ %s", " ".join(cmd))
    return subprocess.run(cmd, check=check, text=True, capture_output=True, **kw)


def ensure_container(
    container_name: str,
    mnt_dir: Path,
    port: int,
    session_key: str,
    env_extra: dict[str, str] | None = None,
) -> None:
    """(Re)create a fresh ELT container running the OpenHands agent-server.

    `mnt_dir` is bind-mounted to `/workspace`. The container exposes the
    agent-server on `port`. SESSION_API_KEY is set inside the container; the
    host must send the same value as `X-Session-API-Key` (RemoteWorkspace
    handles this when you pass `api_key=<session_key>`).
    """
    existing = _run(
        ["docker", "ps", "-aq", "-f", f"name=^{container_name}$"], check=False
    ).stdout.strip()
    if existing:
        logger.info("Removing existing container %s", container_name)
        _run(["docker", "rm", "-f", container_name], check=False)

    mnt_abs = str(mnt_dir.resolve())
    logger.info(
        "Starting container %s (mount %s -> %s, agent-server on host port %d)",
        container_name, mnt_abs, CONTAINER_WORKDIR, port,
    )
    # The agent-server runs the LLM call *inside* the container, and litellm reads
    # the provider key from the container's own environment (the host-side LLM
    # api_key is a SecretStr and is NOT serialized to the remote). Forward the
    # resolved key here, otherwise the run dies with
    # "litellm.AuthenticationError: Missing Anthropic API Key".
    env_args: list[str] = ["-e", f"SESSION_API_KEY={session_key}"]
    for k, v in (env_extra or {}).items():
        if v:
            env_args += ["-e", f"{k}={v}"]
    _run([
        "docker", "run", "-d", "--rm",
        "--name", container_name,
        "--network", NETWORK_NAME,
        "-v", f"{mnt_abs}:{CONTAINER_WORKDIR}",
        "-w", CONTAINER_WORKDIR,
        "-p", f"{port}:8000",
        *env_args,
        IMAGE_NAME,
        "python", "-m", "openhands.agent_server",
        "--host", "0.0.0.0", "--port", "8000",
    ])
    _wait_for_agent_server(f"http://localhost:{port}/", AGENT_SERVER_READY_TIMEOUT_SEC)


def _wait_for_agent_server(url: str, timeout_sec: int) -> None:
    """Poll `url` until it returns HTTP 200 or `timeout_sec` elapses."""
    deadline = time.monotonic() + timeout_sec
    last_err: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return
        except (urllib.error.URLError, OSError) as e:
            last_err = e
        time.sleep(0.5)
    raise RuntimeError(f"agent-server not ready at {url} (last error: {last_err})")


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
    """Collects OpenHands events into a JSON-serializable transcript."""

    def __init__(self) -> None:
        self.turns: list[dict[str, Any]] = []
        self.num_turns: int = 0
        self.total_cost_usd: float | None = None
        self.usage: dict[str, Any] | None = None
        self.is_error: bool = False
        self.final_text: str = ""

    def _serialize(self, event: Event) -> dict[str, Any]:
        # Prefer pydantic dump where available; fall back to repr.
        if hasattr(event, "model_dump"):
            try:
                return {"type": event.__class__.__name__, **event.model_dump(mode="json")}
            except Exception:
                pass
        return {"type": event.__class__.__name__, "repr": repr(event)}

    def _action_text(self, event: ActionEvent) -> str:
        # Some Action events have .action with a tool name + input; others have .thought.
        bits = []
        thought = getattr(event, "thought", None)
        if thought:
            bits.append(str(thought))
        tool_name = getattr(event, "tool_name", None) or getattr(getattr(event, "action", None), "tool_name", None)
        if tool_name:
            bits.append(f"[tool_use {tool_name}]")
        return " ".join(bits) or repr(event)

    def _observation_text(self, event: ObservationEvent) -> str:
        obs = getattr(event, "observation", None)
        if obs is None:
            return repr(event)
        if hasattr(obs, "to_text"):
            try:
                return obs.to_text()
            except Exception:
                pass
        if hasattr(obs, "model_dump_json"):
            try:
                return obs.model_dump_json()
            except Exception:
                pass
        return str(obs)

    def record(self, event: Event) -> None:
        self.turns.append(self._serialize(event))
        if isinstance(event, ActionEvent):
            self.num_turns += 1

        if isinstance(event, MessageEvent):
            text = ""
            msg = getattr(event, "message", None) or getattr(event, "llm_message", None)
            if msg is not None and getattr(msg, "content", None):
                for c in msg.content:
                    if isinstance(c, TextContent):
                        text += c.text
            if text:
                self.final_text = text
                logger.debug("assistant message:\n%s", text)
                logger.info("assistant: %s", text.strip()[:500])
        elif isinstance(event, ActionEvent):
            txt = self._action_text(event)
            logger.debug("action:\n%s", txt)
            logger.info("action: %s", txt[:300])
        elif isinstance(event, ObservationEvent):
            txt = self._observation_text(event)
            preview = txt.strip().replace("\n", " ⏎ ")[:500]
            logger.debug("observation:\n%s", txt)
            logger.info("observation: %s", preview)
        elif isinstance(event, AgentErrorEvent):
            self.is_error = True
            err = getattr(event, "error", None) or repr(event)
            self.final_text = f"ERROR: {err}"
            logger.error("agent error: %s", err)


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
    result_path = out_dir / "openhands" / "result.json"

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
    try:
        namespace = prepare_destination(destination, task_input_dir, credential)
        logger.info("Prepared %s destination namespace %s", destination, namespace)
    except Exception as e:  # pragma: no cover
        logger.warning("Destination preparation for %s failed: %s", db, e)

    # Copy seed files into the mount dir.
    copy_initial_files(task_input_dir, out_dir)

    api_key = (
        os.environ.get("LLM_API_KEY")
        or os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )
    # litellm (running inside the container) reads the key from the provider's
    # canonical env var, picked from the model's provider prefix.
    provider = model.split("/", 1)[0].lower() if "/" in model else ""
    key_env = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}.get(
        provider, "ANTHROPIC_API_KEY"
    )
    if not api_key:
        raise SystemExit(
            "No LLM API key found in the environment. Export LLM_API_KEY or "
            f"{key_env} (for {provider or 'the chosen'} models) before running."
        )
    container_env = {key_env: api_key}

    # Spin up the container running the openhands-agent-server.
    container_name = f"{experiment_id}-{db}"
    session_key = secrets.token_urlsafe(24)
    ensure_container(
        container_name, out_dir, AGENT_SERVER_PORT, session_key, env_extra=container_env
    )

    system_prompt = adapt_prompt(SYSTEM_PROMPT_TEMPLATE, destination).format(
        db=db,
        container=container_name,
        image=IMAGE_NAME,
        network=NETWORK_NAME,
        container_workdir=CONTAINER_WORKDIR,
    )
    # The agent and the condenser each register their LLM in the agent-server's
    # LLM registry. Distinct `usage_id`s are required — sharing the default
    # makes the second registration fail with "Usage ID 'default' already
    # exists in registry."
    agent_llm = LLM(model=model, api_key=api_key, usage_id="agent")
    condenser_llm = LLM(model=model, api_key=api_key, usage_id="condenser")

    # All four tools execute inside the container, sandboxed to /workspace
    # by the bind-mount. There is no host-side execute_bash exposed.
    agent = Agent(
        llm=agent_llm,
        tools=[
            Tool(name="file_editor"),
            Tool(name="terminal"),
            Tool(name="grep"),
            Tool(name="glob"),
        ],
        system_prompt=system_prompt,
        condenser=LLMSummarizingCondenser(llm=condenser_llm, max_size=240, keep_first=4)
    )

    recorder = TrajectoryRecorder()

    def on_event(event: Event) -> None:
        try:
            recorder.record(event)
        except Exception:
            logger.exception("recorder failed for event %r", event)

    workspace = RemoteWorkspace(
        working_dir=CONTAINER_WORKDIR,
        host=f"http://localhost:{AGENT_SERVER_PORT}",
        api_key=session_key,
    )
    conversation = Conversation(
        agent=agent,
        workspace=workspace,
        callbacks=[on_event],
        max_iteration_per_run=max_turns,
    )

    destination_name = get_destination(destination).display_name
    prompt = (
        f"Build the ELT pipeline for the `{db}` now. "
        f"All configuration values (including the {destination_name} namespace) "
        "must come from /workspace/config.yaml.\n\n"
        f"{adapt_prompt(TASK_INSTRUCTION, destination)}"
    )

    try:
        conversation.send_message(
            Message(role="user", content=[TextContent(text=prompt)])
        )
        # `Conversation.run()` is synchronous in the SDK; offload so we don't
        # block the event loop.
        await asyncio.to_thread(conversation.run)
    except Exception as e:
        logger.exception("OpenHands session raised: %s", e)
        recorder.is_error = True
        recorder.final_text = f"ERROR: {e}"
    finally:
        # Pull cost/usage off the conversation stats. Cost lives on each
        # per-usage_id Metrics (we register two: "agent" and "condenser");
        # ConversationStats.get_combined_metrics() sums them.
        try:
            stats = conversation.conversation_stats
            combined = stats.get_combined_metrics()
            recorder.total_cost_usd = combined.accumulated_cost
            recorder.usage = {
                "combined": combined.get_snapshot().model_dump(mode="json"),
                "by_usage_id": {
                    uid: m.get_snapshot().model_dump(mode="json")
                    for uid, m in stats.usage_to_metrics.items()
                },
            }
        except Exception:
            logger.exception("failed to read conversation_stats")
        stop_container(container_name)

    # Persist result.
    (out_dir / "openhands").mkdir(parents=True, exist_ok=True)
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

    stats_path = out_dir / "openhands" / "stats.json"
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
    base_id = f"{args.model.split('/')[-1]}-{args.suffix}" if args.suffix else args.model.split("/")[-1]
    experiment_id = f"openhands-{base_id}-{args.destination}"
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
    p = argparse.ArgumentParser(description="Run OpenHands Agent on ELT-Bench.")
    p.add_argument("--destination", choices=destination_choices(), default="snowflake")
    p.add_argument(
        "--credential",
        help="Optional host-side destination credential JSON override.",
    )
    p.add_argument("--model", default="openai/gpt-5.4-2026-03-05",
                   help="LiteLLM-style provider/model id (e.g. anthropic/claude-opus-4-7, openai/gpt-4o).")
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
                        "Default 100; pass 0 for no limit.")
    p.add_argument("--overwrite", action="store_true",
                   help="Rerun tasks even if result.json already exists.")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()

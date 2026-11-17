"""DeepAnalyze runner for ELT-Bench.

DeepAnalyze (github.com/ruc-datalab/DeepAnalyze, main branch, commit d4dd5cf)
is an agentic LLM for data science (DeepAnalyze-8B). Its agent loop is the
model's own output format: the model writes <Analyze>, <Understand>, <Code>
and <Answer> blocks; the harness runs each <Code> block (Python) and returns
the output as an `execute` message, which the model's chat template renders
as <Execute>...</Execute> inside the same assistant turn. This runner follows
the loop of DeepAnalyze's OpenAI-compatible API (API/chat_api.py and
API/utils.py), with the code run in the ELT task container. For every
database it:

  1. Copies the destination-specific task inputs into the per-run output
     directory, points the task at its own schema and resets that namespace
     on the host (the agent never sees the credential file).
  2. Starts a fresh `elt-swe` task container on `elt-docker_elt_network`,
     running as the host user with `/workspace` read-only except
     `/workspace/elt`.
  3. Sends the task in DeepAnalyze's prompt format ("# Instruction", then
     "# Data" with the workspace files) to a vLLM server running the model,
     with DeepAnalyze's stop tokens (</Code> and end of sentence).
  4. Runs each <Code> block as a new `python` process in the container
     (working directory /workspace), until the model gives an <Answer> or
     stops without code, the step limit is reached, or the context is full.
     DeepAnalyze has no context management, so a full context ends the run.

Usage:
    # vLLM serving DeepAnalyze-8B, e.g. through an SSH tunnel on port 18000
    python run.py --destination snowflake --database deepanalyze_8b \
        --base-url http://127.0.0.1:18000/v1
"""

from __future__ import annotations

import argparse
import datetime
import http.client
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import yaml

AGENT_DIR = Path(__file__).resolve().parent
AGENTS_DIR = AGENT_DIR.parent
if str(AGENTS_DIR) not in sys.path:
    sys.path.insert(0, str(AGENTS_DIR))

from common import (  # noqa: E402
    adapt_prompt,
    default_database,
    destination_choices,
    get_destination,
    prepare_destination,
    resolve_benchmark_path,
    resolve_inputs_path,
)


# ---------- logging ----------

logger = logging.getLogger("deepanalyze")
logger.setLevel(logging.DEBUG)
logger.propagate = False

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

TASK_IMAGE = "elt-swe"
NETWORK_NAME = "elt-docker_elt_network"
CONTAINER_WORKDIR = "/workspace"
CONTAINER_HOME = "/tmp/home"
# Per-attempt runner files inside the task output directory.
AGENT_SUBDIR = "deepanalyze"
# DeepAnalyze's API (API/config.py): stop at </Code> and <｜end▁of▁sentence｜>
# (DeepAnalyze-8B token ids), default temperature 0.4, at most 32768 new
# tokens per generation (also deepanalyze.py's max_tokens).
STOP_TOKEN_IDS = [151676, 151645]
DEFAULT_TEMPERATURE = 0.4
MAX_NEW_TOKENS = 32768
# Same limits as the other agents' shell tools (JoyAgent's bash tool: at most
# 1800 s per command, 10000 characters of output, head and tail).
EXEC_TIMEOUT_SEC = 1800
MAX_OUTPUT_CHARS = 10000

SYSTEM_PROMPT_TEMPLATE = """You are a data engineer skilled in databases, SQL, and building ELT pipelines.

The task workspace is `{container_workdir}` inside Docker container `{container}`
({image} image on the {network} network). Each <Code> block you write is run
as a new `python` process in this container with working directory
{container_workdir}, and its output is returned in <Execute>. Variables do not
persist between blocks. Use subprocess with the command as one string (for
example `subprocess.run("terraform version", shell=True, capture_output=True, text=True)`)
to run shell commands such as terraform, dbt and psql. Only files under {container_workdir}
are visible, and you may only modify files under {container_workdir}/elt. A
block is killed after {exec_timeout} seconds, and long output is shortened to
its first and last {half_output} characters. The deliverables are the
Terraform and DBT projects under {container_workdir}/elt and the resulting
tables in Snowflake; no report or other output file is needed. When the task is
finished (or you give up), give the final RESULT line in <Answer>.

Your goal is to build an ELT pipeline by extracting data from multiple sources, such as custom APIs, PostgreSQL, MongoDB, flat files, and the cloud service S3.
The extracted data will be loaded into a target system, Snowflake, followed by writing transformation queries to construct final tables for downstream use.
This task is divided into two stages:
1. Data Extraction and Loading – Using Airbyte's Terraform provider.
2. Data Transformation – Using the DBT Project workflow for Snowflake.
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

# Attempts the agent itself ended are kept; anything else (LLM server errors,
# crashes) is retried on the next invocation without --overwrite.
KEEP_STATUSES = frozenset({"success", "error_max_turns", "error_context_length",
                           "error_max_tokens", "timeout"})
# How the agent loop ended -> attempt status.
STATUS_BY_END = {
    "answer": "success",
    "no_code": "success",
    "max_turns": "error_max_turns",
    "context_length": "error_context_length",
    "max_tokens": "error_max_tokens",
    "timeout": "timeout",
    "llm_error": "error_llm",
}
# Server answers worth retrying (the vLLM server is reached through a tunnel).
RETRY_STATUS = frozenset({408, 429, 500, 502, 503, 504})
# vLLM's 400 answer when the conversation no longer fits into max_model_len.
CONTEXT_ERROR_RE = re.compile(r"context length|model length|max_model_len", re.IGNORECASE)
# vLLM's 400 answer when max_tokens exceeds the context left (it does not clip).
MAX_TOKENS_ERROR_RE = re.compile(r"'max_tokens'.*too large", re.IGNORECASE | re.DOTALL)


# ---------- the model server ----------

class ContextLengthError(Exception):
    """The conversation no longer fits into the model's context."""


class LLMError(Exception):
    """The model server failed after all retries."""


class VLLMClient:
    """Chat completions on a vLLM server with DeepAnalyze's request parameters."""

    def __init__(self, base_url: str, model: str, api_key: str | None,
                 timeout_sec: int = 1800, max_retries: int = 8) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_sec = timeout_sec
        self.max_retries = max_retries

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def model_info(self) -> dict[str, Any]:
        """The served model's entry in /models (raises SystemExit if absent)."""
        request = urllib.request.Request(f"{self.base_url}/models", headers=self._headers())
        try:
            with urllib.request.urlopen(request, timeout=30) as resp:
                models = json.load(resp).get("data") or []
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise SystemExit(f"model server {self.base_url} not reachable ({e}); is the SSH tunnel up?")
        for entry in models:
            if entry.get("id") == self.model:
                return entry
        raise SystemExit(f"model {self.model!r} not served at {self.base_url}; "
                         f"served: {[m.get('id') for m in models]}")

    def chat(self, messages: list[dict[str, str]], temperature: float,
             max_tokens: int | None) -> dict[str, Any]:
        """One generation step; retries transient errors (tunnel, overload)."""
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            # DeepAnalyze's chat template opens the assistant turn after the
            # user message and continues it after each execute message.
            "add_generation_prompt": False,
            "stop_token_ids": STOP_TOKEN_IDS,
        }
        if max_tokens:
            body["max_tokens"] = max_tokens
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions", data=json.dumps(body).encode(),
            method="POST", headers=self._headers())
        error = ""
        for attempt in range(self.max_retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_sec) as resp:
                    return json.load(resp)
            except urllib.error.HTTPError as e:
                text = e.read().decode("utf-8", errors="replace")
                if e.code == 400 and max_tokens and MAX_TOKENS_ERROR_RE.search(text):
                    # Less context left than the cap: generate until it is full.
                    return self.chat(messages, temperature, None)
                if e.code == 400 and CONTEXT_ERROR_RE.search(text):
                    raise ContextLengthError(text[:500])
                error = f"HTTP {e.code}: {text[:500]}"
                if e.code not in RETRY_STATUS:
                    break
            except (urllib.error.URLError, OSError, http.client.HTTPException, ValueError) as e:
                error = f"{type(e).__name__}: {e}"
            if attempt < self.max_retries:
                wait = min(60, 2 ** attempt * 2)
                logger.warning("LLM call failed (%s); retry %d in %ds", error[:200], attempt + 1, wait)
                time.sleep(wait)
        raise LLMError(error)


# ---------- helpers ----------

def _run(cmd: list[str], check: bool = True, **kw: Any) -> subprocess.CompletedProcess:
    logger.debug("$ %s", " ".join(cmd))
    return subprocess.run(cmd, check=check, text=True, capture_output=True, **kw)


def remove_container(name: str) -> None:
    _run(["docker", "rm", "-f", name], check=False)


def copy_initial_files(src: Path, dst: Path) -> None:
    """Mirror `src` contents into `dst`, without credential files."""
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        if item.name.endswith("_credential.json"):
            continue
        target = dst / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)


def set_task_namespace(config_path: Path, destination: str, db: str, database: str | None) -> None:
    """Place the task in schema `db` of the shared `database`."""
    with config_path.open(encoding="utf-8") as f:
        config = yaml.safe_load(f)
    dest_config = config[destination]["config"]
    if database:
        dest_config["database"] = database
    dest_config["schema"] = db
    with config_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, sort_keys=False)


def start_task_container(name: str, mnt_dir: Path, image: str) -> None:
    """Fresh task container in which the <Code> blocks run.

    `/workspace` is read-only except `/workspace/elt`, which enforces the
    task rule ("you may only modify files under /workspace/elt"). Code runs
    as the host user, so created files stay host-owned.
    """
    remove_container(name)
    mnt = str(mnt_dir.resolve())
    uid, gid = os.getuid(), os.getgid()
    _run([
        "docker", "run", "-d", "--name", name, "--network", NETWORK_NAME,
        "--user", f"{uid}:{gid}", "-e", f"HOME={CONTAINER_HOME}", "-e", "USER=agent",
        "-v", f"{mnt}:{CONTAINER_WORKDIR}:ro", "-v", f"{mnt}/elt:{CONTAINER_WORKDIR}/elt",
        # The runner's files for this attempt are not part of the task.
        "--mount", f"type=tmpfs,destination={CONTAINER_WORKDIR}/{AGENT_SUBDIR}",
        "-w", CONTAINER_WORKDIR, image, "sleep", "infinity",
    ])
    _run([
        "docker", "exec", "-u", "0", name, "sh", "-c",
        f"echo 'agent:x:{uid}:{gid}::{CONTAINER_HOME}:/bin/bash' >> /etc/passwd"
        f" && (getent group {gid} >/dev/null || echo 'agent:x:{gid}:' >> /etc/group)"
        f" && mkdir -p {CONTAINER_HOME} && chown {uid}:{gid} {CONTAINER_HOME}",
    ])


def workspace_file_info(task_dir: Path) -> str:
    """The "# Data" section of DeepAnalyze's prompt (API/utils.py
    collect_file_info), listing every task file by its path under /workspace."""
    files = sorted(p for p in task_dir.rglob("*")
                   if p.is_file() and p.relative_to(task_dir).parts[0] != AGENT_SUBDIR)
    info = ""
    for idx, path in enumerate(files, start=1):
        entry = {"name": path.relative_to(task_dir).as_posix(),
                 "size": f"{path.stat().st_size / 1024:.1f}KB"}
        info += f"File {idx}:\n{json.dumps(entry, indent=4, ensure_ascii=False)}\n\n"
    return info


def extract_code(segment: str) -> str | None:
    """Python code between <Code> and </Code>, optionally fenced (API/utils.py)."""
    code_match = re.search(r"<Code>(.*?)</Code>", segment, re.DOTALL)
    if not code_match:
        return None
    code_content = code_match.group(1).strip()
    md_match = re.search(r"```(?:python)?(.*?)```", code_content, re.DOTALL)
    return md_match.group(1).strip() if md_match else code_content


def clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    half = limit // 2
    return f"{text[:half]}\n... [{len(text) - limit} characters omitted] ...\n{text[-half:]}"


def execute_code(container: str, code: str, timeout_sec: int) -> tuple[str, int | None]:
    """Run `code` as a new python process in the task container.

    Returns stdout and stderr (interleaved) and the exit code. `timeout`
    kills the whole process group, so commands started with subprocess end
    too.
    """
    cmd = ["docker", "exec", "-i", "-w", CONTAINER_WORKDIR, "-e", "MPLBACKEND=Agg", container,
           "timeout", "-k", "10", str(timeout_sec), "python", "-"]
    started = time.monotonic()
    try:
        proc = subprocess.run(cmd, input=code.encode("utf-8"), stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, timeout=timeout_sec + 60)
    except subprocess.TimeoutExpired as e:
        output = (e.output or b"").decode("utf-8", errors="replace")
        return f"{output}\n[Timeout]: execution exceeded {timeout_sec} seconds", None
    output = proc.stdout.decode("utf-8", errors="replace")
    # `timeout` exits with 124 (TERM) or 137 (KILL after the grace period).
    if proc.returncode in (124, 137) and time.monotonic() - started >= timeout_sec:
        output += f"\n[Timeout]: execution exceeded {timeout_sec} seconds"
    return output, proc.returncode


# ---------- the agent loop ----------

class Trajectory:
    """Records every generation step and code execution."""

    def __init__(self, path: Path) -> None:
        self.file = open(path, "w", encoding="utf-8")
        self.llm_calls = 0
        self.code_runs = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.max_context_tokens = 0
        self.last_content = ""

    def close(self) -> None:
        self.file.close()

    def write(self, entry: dict[str, Any]) -> None:
        self.file.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        self.file.flush()

    def record_llm(self, response: dict[str, Any]) -> None:
        usage = response.get("usage") or {}
        self.llm_calls += 1
        self.prompt_tokens += int(usage.get("prompt_tokens") or 0)
        self.completion_tokens += int(usage.get("completion_tokens") or 0)
        self.max_context_tokens = max(self.max_context_tokens, int(usage.get("total_tokens") or 0))

    def usage(self) -> dict[str, int]:
        return {
            "llm_calls": self.llm_calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "max_context_tokens": self.max_context_tokens,
        }


def run_agent(client: VLLMClient, container: str, messages: list[dict[str, str]],
              trajectory: Trajectory, args: argparse.Namespace) -> str:
    """DeepAnalyze's generate -> execute loop; returns how it ended.

    `messages` grows in place: the user prompt, then the model's segments
    (role assistant) and the code output (role execute).
    """
    deadline = time.monotonic() + args.timeout_hours * 3600
    while True:
        if time.monotonic() > deadline:
            return "timeout"
        started = time.monotonic()
        try:
            response = client.chat(messages, args.temperature, args.max_new_tokens)
        except ContextLengthError as e:
            logger.info("context full: %s", str(e)[:300])
            trajectory.write({"time": time.time(), "context_error": str(e)})
            return "context_length"
        llm_seconds = time.monotonic() - started
        trajectory.record_llm(response)
        choice = response["choices"][0]
        content = choice["message"].get("content") or ""
        finish_reason = choice.get("finish_reason")
        usage = response.get("usage") or {}
        # Generation stops at </Code> (a stop token, not part of the output).
        if "<Code>" in content and "</Code>" not in content and finish_reason == "stop":
            content += "</Code>"
        trajectory.last_content = content
        entry: dict[str, Any] = {
            "time": time.time(), "step": trajectory.llm_calls, "llm_seconds": round(llm_seconds, 2),
            "finish_reason": finish_reason, "stop_reason": choice.get("stop_reason"),
            "usage": usage, "content": content,
        }
        logger.info("step %d: %d+%d tokens, %.0fs, finish %s/%s", trajectory.llm_calls,
                    usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0), llm_seconds,
                    finish_reason, choice.get("stop_reason"))
        messages.append({"role": "assistant", "content": content})

        if "</Answer>" in content:
            trajectory.write(entry)
            return "answer"
        if finish_reason == "length":
            # The output stops here at the per-generation cap (a runaway,
            # usually repeating output) or when the context is full.
            trajectory.write(entry)
            if args.max_new_tokens and int(usage.get("completion_tokens") or 0) >= args.max_new_tokens:
                return "max_tokens"
            return "context_length"
        code = extract_code(content)
        if not code:
            trajectory.write(entry)
            return "no_code"
        if trajectory.code_runs >= args.max_turns:
            trajectory.write(entry)
            return "max_turns"

        started = time.monotonic()
        output, returncode = execute_code(container, code, args.exec_timeout)
        output = clip(output, args.max_output_chars)
        trajectory.code_runs += 1
        entry.update(code=code, output=output, returncode=returncode,
                     exec_seconds=round(time.monotonic() - started, 2))
        trajectory.write(entry)
        logger.info("code %d (rc %s, %.0fs): %s -> %s", trajectory.code_runs, returncode,
                    entry["exec_seconds"], code.replace("\n", " ⏎ ")[:300],
                    output.replace("\n", " ⏎ ")[:300])
        messages.append({"role": "execute", "content": output})


def render_transcript(messages: list[dict[str, str]]) -> str:
    """The conversation as the model sees it (cf. DeepAnalyze's `reasoning`)."""
    parts = []
    for message in messages:
        if message["role"] == "execute":
            parts.append(f"\n<Execute>\n{message['content']}\n</Execute>\n")
        elif message["role"] == "user":
            parts.append(f"{message['content']}\n\n---\n\n")
        else:
            parts.append(message["content"])
    return "".join(parts)


def final_answer(content: str) -> str:
    match = re.search(r"<Answer>(.*?)(?:</Answer>|$)", content, re.DOTALL)
    return (match.group(1) if match else content[-2000:]).strip()


# ---------- the main loop ----------

def run_task(db: str, args: argparse.Namespace, experiment_id: str, inputs_root: Path,
             client: VLLMClient) -> None:
    instance_id = f"{experiment_id}/{db}"
    out_dir = Path(args.output_dir) / instance_id
    agent_dir = out_dir / AGENT_SUBDIR
    result_path = agent_dir / "result.json"

    if result_path.exists() and not args.overwrite:
        try:
            previous = json.loads(result_path.read_text())
        except (OSError, ValueError):
            previous = {}
        if previous.get("status") in KEEP_STATUSES:
            logger.info("Skipping %s (result exists, status=%s)", instance_id, previous.get("status"))
            return
        logger.info("Rerunning %s (previous status=%s)", instance_id, previous.get("status"))
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    db_log_path = LOG_DIR / f"{experiment_id}-{db}-{datetime.datetime.now():%Y%m%d@%H%M%S}.log"
    db_handler = logging.FileHandler(db_log_path, encoding="utf-8")
    db_handler.setFormatter(_fmt)
    db_handler.setLevel(logging.DEBUG)
    logger.addHandler(db_handler)
    logger.info("=== Running %s (log: %s) ===", instance_id, db_log_path)
    try:
        _run_task_body(db, args, instance_id, experiment_id, out_dir, agent_dir, inputs_root, client)
    finally:
        logger.removeHandler(db_handler)
        db_handler.close()


def _run_task_body(db: str, args: argparse.Namespace, instance_id: str, experiment_id: str,
                   out_dir: Path, agent_dir: Path, inputs_root: Path, client: VLLMClient) -> None:
    destination = args.destination
    task_input_dir = inputs_root / db
    copy_initial_files(task_input_dir, out_dir)
    (out_dir / "elt").mkdir(exist_ok=True)
    set_task_namespace(out_dir / "config.yaml", destination, db, args.database)

    credential = args.credential
    if credential is None:
        generated = task_input_dir / f"{destination}_credential.json"
        credential = str(generated) if generated.is_file() else None
    namespace = prepare_destination(destination, out_dir, credential)
    logger.info("Prepared %s destination namespace %s", destination, namespace)

    task_container = f"{experiment_id}-{db}"
    system_prompt = adapt_prompt(SYSTEM_PROMPT_TEMPLATE, destination).format(
        container=task_container, image=args.task_image.split(":", 1)[0], network=NETWORK_NAME,
        container_workdir=CONTAINER_WORKDIR, exec_timeout=args.exec_timeout,
        half_output=args.max_output_chars // 2)
    destination_name = get_destination(destination).display_name
    instruction = (
        f"{system_prompt}\n"
        f"Build the ELT pipeline for the `{db}` now. "
        f"All configuration values (including the {destination_name} namespace) "
        "must come from /workspace/config.yaml.\n\n"
        f"{adapt_prompt(TASK_INSTRUCTION, destination)}"
    )
    # DeepAnalyze's prompt format (API/utils.py prepare_vllm_messages).
    messages = [{"role": "user", "content":
                 f"# Instruction\n{instruction}\n\n# Data\n{workspace_file_info(out_dir)}"}]

    # The runner's files go to deepanalyze/, which the task container does not
    # see (an empty tmpfs covers it).
    agent_dir.mkdir(parents=True, exist_ok=True)
    trajectory = Trajectory(agent_dir / "trajectory.jsonl")
    ended_by, error = "exception", None
    started = time.time()
    try:
        start_task_container(task_container, out_dir, args.task_image)
        ended_by = run_agent(client, task_container, messages, trajectory, args)
    except LLMError as e:
        logger.error("model server failed: %s", e)
        ended_by, error = "llm_error", str(e)
    except Exception as e:  # infrastructure failure: retried next time
        logger.exception("DeepAnalyze run failed")
        error = f"{type(e).__name__}: {e}"
    finally:
        trajectory.close()
        remove_container(task_container)
        (agent_dir / "transcript.md").write_text(render_transcript(messages), encoding="utf-8")

    status = STATUS_BY_END.get(ended_by, "exception")
    usage = trajectory.usage()
    logger.info("run status: %s (ended by %s); %d code runs, usage %s", status, ended_by,
                trajectory.code_runs, usage)

    common = {
        "instance_id": instance_id,
        "db": db,
        "model": args.model,
        "num_turns": trajectory.code_runs,
        "duration_sec": round(time.time() - started, 1),
        # Self-hosted model.
        "total_cost_usd": None,
        "usage": usage,
    }
    result_json = {
        **common,
        "finished": status == "success",
        "status": status,
        "ended_by": ended_by,
        "error": error,
        "result": final_answer(trajectory.last_content) if trajectory.last_content else None,
        "trajectory": "trajectory.jsonl",
    }
    (agent_dir / "result.json").write_text(json.dumps(result_json, indent=2, ensure_ascii=False, default=str))
    (agent_dir / "stats.json").write_text(json.dumps(common, indent=2, default=str))
    logger.info("Wrote %s", agent_dir / "result.json")


def main() -> None:
    args = parse_args()
    api_key = os.environ.get(args.api_key_env) if args.api_key_env else None
    client = VLLMClient(args.base_url, args.model, api_key)
    served = client.model_info()
    base_id = args.model.split("/")[-1]
    experiment_id = f"deepanalyze-{base_id}-{args.suffix}-{args.destination}" if args.suffix \
        else f"deepanalyze-{base_id}-{args.destination}"
    # One database (Redshift) / catalog (Databricks) per run unless --database
    # is given, so runs of different agents never drop each other's schemas.
    if args.database is None:
        args.database = default_database(args.destination, experiment_id)
    logger.info("Destination namespace: database %s, one schema per task", args.database)
    inputs_root = resolve_inputs_path(args.destination, args.test_path)
    elt_bench_root = resolve_benchmark_path(args.destination, args.elt_bench)
    if not inputs_root.is_dir():
        raise SystemExit(f"inputs dir not found: {inputs_root}")

    databases = sorted(p.name for p in elt_bench_root.iterdir() if p.is_dir())
    if args.only:
        wanted = set(args.only.split(","))
        databases = [d for d in databases if d in wanted]
    if args.limit and args.limit > 0:
        databases = databases[: args.limit]
    if args.shard:
        k, n = args.shard
        databases = databases[k::n]

    logger.info("Experiment %s — %d tasks (model %s at %s, max_model_len %s)", experiment_id,
                len(databases), args.model, args.base_url, served.get("max_model_len"))
    for db in databases:
        try:
            run_task(db, args, experiment_id, inputs_root, client)
        except Exception:
            logger.exception("Task %s failed", db)


def _parse_shard(value: str) -> tuple[int, int]:
    try:
        k, n = (int(x) for x in value.split("/"))
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected K/N, got {value!r}")
    if not 0 <= k < n:
        raise argparse.ArgumentTypeError(f"need 0 <= K < N, got {value!r}")
    return k, n


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run DeepAnalyze on ELT-Bench.")
    p.add_argument("--destination", choices=destination_choices(), default="snowflake")
    p.add_argument("--credential", help="Optional host-side destination credential JSON override.")
    p.add_argument("--database", help="Database/catalog holding one schema per task (default: "
                                      "'elt' for snowflake; one database (redshift) or catalog "
                                      "(databricks) per run, named after the experiment).")
    p.add_argument("--model", default="DeepAnalyze-8B", help="Served model name.")
    p.add_argument("--base-url", default="http://127.0.0.1:18000/v1",
                   help="OpenAI-compatible base URL of the vLLM server.")
    p.add_argument("--api-key-env", default="",
                   help="Environment variable holding the server's API key (vLLM --api-key), if any.")
    p.add_argument("--max_turns", type=int, default=100, help="Limit on executed <Code> blocks.")
    p.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE,
                   help="DeepAnalyze's API default is 0.4.")
    p.add_argument("--max-new-tokens", type=int, default=MAX_NEW_TOKENS,
                   help="Limit on tokens per generation (DeepAnalyze's default 32768); a "
                        "generation that reaches it ends the task (error_max_tokens). 0: none.")
    p.add_argument("--exec-timeout", type=int, default=EXEC_TIMEOUT_SEC,
                   help="Seconds after which a <Code> block is killed.")
    p.add_argument("--max-output-chars", type=int, default=MAX_OUTPUT_CHARS,
                   help="Characters of each code output returned to the model (head and tail).")
    p.add_argument("--timeout-hours", type=float, default=6.0, help="Wall-clock limit per task.")
    p.add_argument("--suffix", "-s", default="eltbench", help="Experiment id suffix.")
    p.add_argument("--test_path", "-t", help="Per-task inputs directory (default: destination-specific).")
    p.add_argument("--elt_bench", help="Task directory (default: elt-bench/<destination>).")
    p.add_argument("--output_dir", default=str(AGENT_DIR / "output"))
    p.add_argument("--only", default="", help="Comma-separated DBs to run (default: all).")
    p.add_argument("--limit", type=int, default=100, help="Run only the first N DBs; 0 for no limit.")
    p.add_argument("--overwrite", action="store_true", help="Rerun tasks even if result.json exists.")
    p.add_argument("--task-image", default=TASK_IMAGE)
    p.add_argument("--shard", type=_parse_shard, default=None, metavar="K/N",
                   help="Run only every N-th task starting at K (0-based).")
    return p.parse_args()


if __name__ == "__main__":
    main()

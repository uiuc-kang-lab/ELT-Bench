"""JoyAgent-JDGenie runner for ELT-Bench.

JoyAgent (github.com/jd-opensource/joyagent-jdgenie) is a multi-agent product:
a planner splits the task into sub-tasks, an executor solves each with tool
calls (plan-and-execute, "deep think" in its UI), or a single ReAct agent
does the whole task. Its built-in tools (search, code interpreter, report)
cannot run shell commands, so the task tools are added through JoyAgent's own
MCP extension point. For every database this runner:

  1. Copies the destination-specific task inputs into the per-run output
     directory, points the task at its own schema and resets that namespace
     on the host (the agent never sees the credential file).
  2. Starts a fresh `elt-swe-joyagent` task container on
     `elt-docker_elt_network`, running as the host user with `/workspace`
     read-only except `/workspace/elt`. It serves the MCP tools bash /
     read_file / write_file / edit_file (elt-swe-joyagent/mcp_workspace_server.py).
  3. Starts a fresh `joyagent-genie` container (backend, genie-tool,
     genie-client; see genie/) whose override config points JoyAgent at that
     MCP server, the step limits and the model. Its LLM calls go to a proxy in
     this process, which adds the API key (JoyAgent never sees it) and records
     token usage.
  4. Sends the task to JoyAgent's `POST /AutoAgent`, follows the SSE stream
     until the final result, and writes `joyagent/result.json`.

Usage:
    export TOGETHER_API_KEY=...
    python run.py --destination snowflake --database joyagent_glm53 \
        --model zai-org/GLM-5.3 --base-url https://api.together.xyz/v1 --api-key-env TOGETHER_API_KEY
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
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import yaml

AGENT_DIR = Path(__file__).resolve().parent
AGENTS_DIR = AGENT_DIR.parent
if str(AGENTS_DIR) not in sys.path:
    sys.path.insert(0, str(AGENTS_DIR))

from responses_bridge import ResponsesBridge  # noqa: E402
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

logger = logging.getLogger("joyagent")
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

TASK_IMAGE = "elt-swe-joyagent"
GENIE_IMAGE = "joyagent-genie"
GENIE_DATAAGENT_IMAGE = "joyagent-genie-dataagent"
NETWORK_NAME = "elt-docker_elt_network"
CONTAINER_WORKDIR = "/workspace"
CONTAINER_HOME = "/tmp/home"
MCP_PORT = 8000
# Per-attempt runner files inside the task output directory.
AGENT_SUBDIR = "joyagent"
GENIE_LOG_DIR = "/tmp/genie-logs"
READY_TIMEOUT_SEC = 300
# Limit for one MCP tool call: JoyAgent's HTTP call to genie-client and
# genie-client's read from the MCP server (the bash tool itself caps a
# command at 1800 s).
MCP_CALL_TIMEOUT_SEC = 3600
# No SSE event and no LLM call for this long means JoyAgent is stuck (an
# exception in its worker thread leaves the stream open with heartbeats only);
# it must outlast the longest tool call.
IDLE_TIMEOUT_SEC = MCP_CALL_TIMEOUT_SEC + 600
MCP_TOOLS = ("bash", "read_file", "write_file", "edit_file")
AGENT_TYPES = {"plan_solve": 3, "react": 5}
# DataAgent variant: upstream's HTTP limits assume a fast model, but NL2SQL
# (rewrite, think, SQL) and an analysis (up to 10 steps, each possibly with
# NL2SQL) take minutes with a reasoning model.
DATA_AGENT_READ_TIMEOUT_SEC = 900
DATA_ANALYSIS_TIMEOUT_SEC = 1800

SYSTEM_PROMPT_TEMPLATE = """You are a data engineer skilled in databases, SQL, and building ELT pipelines.

The task workspace is `{container_workdir}` inside Docker container `{container}`
({image} image on the {network} network). The bash, read_file, write_file and
edit_file tools operate inside this container: relative paths are relative to
{container_workdir}, and only files under {container_workdir} are visible. You may
only modify files under {container_workdir}/elt. The deliverables are the
Terraform and DBT projects under {container_workdir}/elt and the resulting tables
in Snowflake; no report or other output file is needed.

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

# Attempts the agent itself ended are kept; anything else (LLM/API errors,
# crashes, a stream that ended without a result) is retried on the next
# invocation without --overwrite.
KEEP_STATUSES = frozenset({"success", "error_max_turns"})
# Final messages of JoyAgent's handlers (PlanSolveHandlerImpl / ReactHandlerImpl).
MAX_STEPS_TEXT = "达到最大迭代次数"
ERROR_TEXT = "任务执行异常"
# Upstream answers worth retrying (rate limits, overload, gateway and Cloudflare errors).
RETRY_STATUS = frozenset({408, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524, 529})


# ---------- LLM proxy ----------

def completion_to_sse(completion: dict[str, Any]) -> bytes:
    """A chat completion as the chunk stream a `"stream": true` request expects:
    one chunk with the whole message, one with the finish reason (and usage)."""
    base = {"id": completion.get("id"), "object": "chat.completion.chunk",
            "created": completion.get("created"), "model": completion.get("model")}
    chunks = []
    for choice in completion.get("choices") or []:
        message = choice.get("message") or {}
        delta: dict[str, Any] = {"role": "assistant", "content": message.get("content")}
        if message.get("tool_calls"):
            delta["tool_calls"] = [{"index": i, **call} for i, call in enumerate(message["tool_calls"])]
        index = choice.get("index", 0)
        chunks.append({**base, "choices": [{"index": index, "delta": delta, "finish_reason": None}]})
        chunks.append({**base, "choices": [{"index": index, "delta": {},
                                            "finish_reason": choice.get("finish_reason")}]})
    if chunks and completion.get("usage"):
        chunks[-1]["usage"] = completion["usage"]
    return b"".join(b"data: " + json.dumps(c).encode() + b"\n\n" for c in chunks) + b"data: [DONE]\n\n"


class LLMProxy:
    """OpenAI-compatible proxy between JoyAgent and the model provider.

    JoyAgent is configured with this proxy's URL and a dummy key; the proxy
    adds the real key, applies request tweaks the provider needs (dropped or
    renamed parameters, extra parameters), retries transient errors, and
    records token usage and every response.

    With `responses_api`, requests go to the provider's /responses endpoint
    (see responses_bridge.py): OpenAI's GPT-5.4 rejects function tools
    together with reasoning_effort on /v1/chat/completions, JoyAgent's only
    interface.

    Streaming requests (the DataAgent's genie-tool streams NL2SQL's "think"
    step and its report) are sent upstream without streaming and the answer
    is replayed as an SSE chunk stream, so usage is recorded the same way.
    """

    def __init__(
        self,
        bind_host: str,
        upstream: str,
        api_key: str,
        model: str,
        drop_params: list[str],
        rename_params: dict[str, str],
        extra_params: dict[str, Any],
        timeout_sec: int = 600,
        max_retries: int = 6,
        responses_api: bool = False,
    ) -> None:
        self.upstream = upstream.rstrip("/")
        self.bridge = ResponsesBridge() if responses_api else None
        self.api_key = api_key
        self.model = model
        self.drop_params = drop_params
        self.rename_params = rename_params
        self.extra_params = extra_params
        self.timeout_sec = timeout_sec
        self.max_retries = max_retries
        self.lock = threading.Lock()
        self.log_file = None
        # Only the current task's JoyAgent container may use the proxy (the
        # task container is on the same network).
        self.allowed_ips: set[str] = set()
        self.last_activity = time.monotonic()
        self.reset()
        proxy = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt: str, *args: Any) -> None:  # quiet
                logger.debug("proxy: " + fmt, *args)

            def do_POST(self) -> None:  # noqa: N802
                body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                content_type = "application/json"
                if self.client_address[0] not in proxy.allowed_ips:
                    status, payload = 403, b'{"error": "forbidden"}'
                else:
                    status, payload, content_type = proxy.forward(self.path, body)
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        self.server = ThreadingHTTPServer((bind_host, 0), Handler)
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def reset(self, log_path: Path | None = None) -> None:
        with self.lock:
            self.allowed_ips = set()
            self.calls = 0
            self.failed_calls = 0
            self.prompt_tokens = 0
            self.completion_tokens = 0
            self.cached_tokens = 0
            self.reasoning_tokens = 0
            self.cost_usd = 0.0
            self.cost_known = True
            if self.bridge:
                self.bridge.reset()
            if self.log_file:
                self.log_file.close()
            self.log_file = open(log_path, "a", encoding="utf-8") if log_path else None
            self.last_activity = time.monotonic()

    def close(self) -> None:
        self.server.shutdown()
        self.reset(None)

    def _request_body(self, body: bytes) -> tuple[bytes, bool]:
        """The upstream request (never streamed) and whether the client asked for a stream."""
        params = json.loads(body)
        params["model"] = self.model
        for name in self.drop_params:
            params.pop(name, None)
        for old, new in self.rename_params.items():
            if old in params:
                params[new] = params.pop(old)
        params.update(self.extra_params)
        stream = bool(params.pop("stream", False))
        params.pop("stream_options", None)
        return json.dumps(params).encode(), stream

    def forward(self, path: str, body: bytes) -> tuple[int, bytes, str]:
        """Returns status, payload and its content type."""
        self.last_activity = time.monotonic()
        if not path.rstrip("/").endswith("/chat/completions"):
            return 404, json.dumps({"error": f"unsupported path {path}"}).encode(), "application/json"
        data, stream = self._request_body(body)
        started = time.time()
        if self.bridge:
            params = json.loads(data)
            request_body = self.bridge.to_responses(params, self.model)
            status, payload = self._post("/responses", json.dumps(request_body).encode())
            if status == 200:
                try:
                    payload = json.dumps(self.bridge.to_chat(json.loads(payload), params.get("stop"))).encode()
                except (ValueError, TypeError, AttributeError) as e:
                    status, payload = 502, json.dumps({"error": f"proxy: bad response: {e}"}).encode()
        else:
            status, payload = self._post("/chat/completions", data)
        self._record(status, payload, time.time() - started)
        self.last_activity = time.monotonic()
        if stream and status == 200:
            try:
                return status, completion_to_sse(json.loads(payload)), "text/event-stream"
            except (ValueError, TypeError, AttributeError) as e:
                return 502, json.dumps({"error": f"proxy: bad response: {e}"}).encode(), "application/json"
        return status, payload, "application/json"

    def _post(self, endpoint: str, data: bytes) -> tuple[int, bytes]:
        """POST to the provider, retrying rate limits and transient errors."""
        request = urllib.request.Request(
            f"{self.upstream}{endpoint}", data=data, method="POST",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
        )
        status, payload = 502, b""
        for attempt in range(self.max_retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_sec) as resp:
                    return resp.status, resp.read()
            except urllib.error.HTTPError as e:
                status, payload = e.code, e.read()
                if status not in RETRY_STATUS:
                    break
            except (urllib.error.URLError, OSError, http.client.HTTPException) as e:
                status, payload = 502, json.dumps({"error": f"proxy: {e}"}).encode()
            if attempt < self.max_retries:
                wait = min(60, 2 ** attempt * 2)
                logger.warning("LLM call failed with %s; retry %d in %ds", status, attempt + 1, wait)
                time.sleep(wait)
        logger.warning("LLM call failed with %s: %s", status, payload[:300])
        return status, payload

    def _record(self, status: int, payload: bytes, seconds: float, cost: float | None = None) -> None:
        entry: dict[str, Any] = {"time": time.time(), "status": status, "seconds": round(seconds, 2),
                                 "cost_usd": cost}
        usage: dict[str, Any] = {}
        try:
            response = json.loads(payload)
            usage = response.get("usage") or {}
            entry["response"] = response
        except (ValueError, AttributeError):
            entry["response_text"] = payload.decode("utf-8", errors="replace")[:5000]
        with self.lock:
            self.calls += 1
            if status != 200:
                self.failed_calls += 1
            self.prompt_tokens += int(usage.get("prompt_tokens") or 0)
            self.completion_tokens += int(usage.get("completion_tokens") or 0)
            self.cached_tokens += int((usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0)
            self.reasoning_tokens += int(
                (usage.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0)
            if cost is not None:
                self.cost_usd += float(cost)
            elif status == 200:
                self.cost_known = False
            if self.log_file:
                self.log_file.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
                self.log_file.flush()

    def usage(self) -> dict[str, int]:
        with self.lock:
            return {
                "llm_calls": self.calls,
                "failed_llm_calls": self.failed_calls,
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "cached_prompt_tokens": self.cached_tokens,
                "reasoning_tokens": self.reasoning_tokens,
                "cost_usd": round(self.cost_usd, 6) if self.cost_known and self.calls else None,
            }


# ---------- helpers ----------

def _run(cmd: list[str], check: bool = True, **kw: Any) -> subprocess.CompletedProcess:
    logger.debug("$ %s", " ".join(cmd))
    return subprocess.run(cmd, check=check, text=True, capture_output=True, **kw)


def free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def network_gateway(network: str) -> str:
    """Host address on `network`, reachable from its containers."""
    out = _run(["docker", "network", "inspect", network,
                "-f", "{{range .IPAM.Config}}{{.Gateway}} {{end}}"]).stdout.split()
    if not out:
        raise SystemExit(f"no gateway found for docker network {network}")
    return out[0]


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
    """Fresh task container serving the MCP workspace tools on port 8000.

    `/workspace` is read-only except `/workspace/elt`, which enforces the
    task rule ("you may only modify files under /workspace/elt") for every
    tool. Commands run as the host user, so created files stay host-owned.
    """
    remove_container(name)
    mnt = str(mnt_dir.resolve())
    uid, gid = os.getuid(), os.getgid()
    _run([
        "docker", "run", "-d", "--name", name, "--network", NETWORK_NAME,
        "--user", f"{uid}:{gid}", "-e", f"HOME={CONTAINER_HOME}", "-e", "USER=agent",
        "-v", f"{mnt}:{CONTAINER_WORKDIR}:ro", "-v", f"{mnt}/elt:{CONTAINER_WORKDIR}/elt",
        # The runner's files for this attempt (JoyAgent config, logs) are not
        # part of the task.
        "--mount", f"type=tmpfs,destination={CONTAINER_WORKDIR}/{AGENT_SUBDIR}",
        "-w", CONTAINER_WORKDIR, image,
        "sh", "-c",
        f"mkdir -p {CONTAINER_HOME} && exec /opt/joyagent/venv/bin/python "
        f"/opt/joyagent/mcp_workspace_server.py --host 0.0.0.0 --port {MCP_PORT}",
    ])
    _run([
        "docker", "exec", "-u", "0", name, "sh", "-c",
        f"echo 'agent:x:{uid}:{gid}::{CONTAINER_HOME}:/bin/bash' >> /etc/passwd"
        f" && (getent group {gid} >/dev/null || echo 'agent:x:{gid}:' >> /etc/group)",
    ])
    probe = (f"import socket; socket.create_connection(('127.0.0.1', {MCP_PORT}), 2)")
    deadline = time.monotonic() + READY_TIMEOUT_SEC
    while time.monotonic() < deadline:
        if _run(["docker", "exec", name, "/opt/joyagent/venv/bin/python", "-c", probe],
                check=False).returncode == 0:
            return
        time.sleep(1)
    raise RuntimeError(f"MCP server in {name} not ready")


def data_agent_db_config(destination: str, config_path: Path) -> dict[str, Any]:
    """The DataAgent's warehouse connection: the task's namespace, with the
    credentials of the agent's own config.yaml (not the runner's)."""
    with config_path.open(encoding="utf-8") as f:
        c = yaml.safe_load(f)[destination]["config"]
    user = c.get("username") or c.get("user") or ""
    if destination == "snowflake":
        # Unquoted identifiers, as Airbyte and dbt create them, are upper case.
        schema = str(c["schema"]).upper()
        query = {"db": str(c["database"]).upper(), "schema": schema}
        query.update({k: c[k] for k in ("warehouse", "role") if c.get(k)})
        url = f"jdbc:snowflake://{c['account']}.snowflakecomputing.com/?{urllib.parse.urlencode(query)}"
        return {"type": "Snowflake", "url": url, "schema": schema, "username": user, "password": c["password"]}
    if destination == "redshift":
        schema = str(c["schema"]).lower()
        url = f"jdbc:redshift://{c['host']}:{c['port']}/{str(c['database']).lower()}"
        return {"type": "Redshift", "url": url, "schema": schema, "username": user, "password": c["password"]}
    if destination == "databricks":
        # OAuth machine-to-machine with the service principal of config.yaml.
        schema = str(c["schema"]).lower()
        host = str(c["hostname"]).removeprefix("https://")
        url = (f"jdbc:databricks://{host}:443;httpPath={c['http_path']};AuthMech=11;Auth_Flow=1;"
               f"OAuth2ClientId={c['client_id']};OAuth2Secret={c['secret']};"
               f"ConnCatalog={str(c['database']).lower()};ConnSchema={schema}")
        return {"type": "Databricks", "url": url, "schema": schema, "username": "", "password": ""}
    raise ValueError(f"no DataAgent connection for destination {destination!r}")


def mask_db_config(db_config: dict[str, Any]) -> dict[str, Any]:
    """The connection without secrets, for the copy of the config kept with the results."""
    masked = dict(db_config, password="***" if db_config.get("password") else "")
    masked["url"] = re.sub(r"(OAuth2Secret=)[^;]*", r"\1***", db_config["url"])
    return masked


def write_override(path: Path, override: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(override, allow_unicode=True, sort_keys=False), encoding="utf-8")
    path.chmod(0o600)


def genie_override(args: argparse.Namespace, proxy_url: str, mcp_url: str,
                   db_config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Per-run JoyAgent settings (Spring `additional-location` override).

    With `db_config` (DataAgent variant), the data agent connects to the task
    schema and starts with no data models (upstream ships two demo models);
    the agent registers models itself with the register_models tool.
    """
    settings = {
        "model": args.model,
        "maxTokens": args.max_tokens,
        "temperature": args.temperature,
        "baseUrl": proxy_url,
        "apiKey": "set-by-proxy",
        "interfaceUrl": "/v1/chat/completions",
        "functionCallType": "function_call",
        "maxInputTokens": args.max_input_tokens,
    }
    override = {
        "llm": {"settings": json.dumps({args.model: settings})},
        "autobots": {"autoagent": {
            # The planner's limit also bounds the plan/execute rounds and the
            # executor's tool-call steps over the whole task.
            "planner": {"model_name": args.model, "max_steps": args.max_turns},
            "executor": {"model_name": args.model, "max_steps": args.max_turns,
                         "max_observe": str(args.max_observe)},
            "react": {"model_name": args.model, "max_steps": args.max_turns},
            # No search / code interpreter / report tools: file_tool and the
            # planning tool stay (built in), the task tools come from MCP.
            # (The DataAgent's own tool set ignores this list.)
            "tool_list": json.dumps({"default": "none"}),
            "mcp_server_url": mcp_url,
        }},
    }
    if db_config is not None:
        override["autobots"]["data-agent"] = {"db-config": db_config, "model-list": []}
    return override


def container_ip(name: str) -> str:
    return _run(["docker", "inspect", "-f",
                 f'{{{{(index .NetworkSettings.Networks "{NETWORK_NAME}").IPAddress}}}}', name]).stdout.strip()


def start_genie_container(name: str, image: str, config_dir: Path, port: int,
                          extra_env: dict[str, str] | None = None) -> None:
    remove_container(name)
    uid, gid = os.getuid(), os.getgid()
    env_args = [arg for k, v in (extra_env or {}).items() for arg in ("-e", f"{k}={v}")]
    _run([
        "docker", "run", "-d", "--name", name, "--network", NETWORK_NAME,
        "--user", f"{uid}:{gid}", "-e", "HOME=/tmp/home",
        "-e", f"GENIE_MCP_CALL_TIMEOUT_SEC={MCP_CALL_TIMEOUT_SEC}",
        "-e", f"GENIE_MCP_SSE_READ_TIMEOUT={MCP_CALL_TIMEOUT_SEC}",
        "-e", "GENIE_AUTO_AGENT_SSE_TIMEOUT_MIN=720",
        "-e", f"GENIE_LOG_DIR={GENIE_LOG_DIR}",
        *env_args,
        "-v", f"{config_dir.resolve()}:/config:ro",
        "-p", f"127.0.0.1:{port}:8080", image,
    ])
    deadline = time.monotonic() + READY_TIMEOUT_SEC
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/web/health", timeout=2) as r:
                if r.status == 200:
                    return
        except (urllib.error.URLError, OSError):
            pass
        state = _run(["docker", "inspect", "-f", "{{.State.Running}}", name], check=False).stdout.strip()
        if state != "true":
            raise RuntimeError(f"{name} exited: {_run(['docker', 'logs', '--tail', '30', name], check=False).stderr}")
        time.sleep(2)
    raise RuntimeError(f"JoyAgent backend in {name} not ready")


def check_mcp_tools(genie: str, mcp_url: str) -> list[str]:
    """Tool names JoyAgent's MCP client sees (JoyAgent drops tools silently)."""
    body = json.dumps({"server_url": mcp_url})
    out = _run(["docker", "exec", genie, "curl", "-s", "-X", "POST", "http://127.0.0.1:8188/v1/tool/list",
                "-H", "Content-Type: application/json", "-d", body], check=False).stdout
    try:
        return [t["name"] for t in json.loads(out).get("data") or []]
    except (ValueError, TypeError, KeyError):
        return []


def collect_genie_logs(genie: str, dest: Path) -> str:
    """Save the backend log and the genie-tool/genie-client logs; returns the backend log."""
    dest.mkdir(parents=True, exist_ok=True)
    logs = _run(["docker", "logs", genie], check=False)
    backend_log = logs.stdout + logs.stderr
    (dest / "backend.log").write_text(backend_log, encoding="utf-8")
    _run(["docker", "cp", f"{genie}:{GENIE_LOG_DIR}/.", str(dest)], check=False)
    return backend_log


def hit_step_limit(backend_log: str, request_id: str) -> bool:
    """Whether the executor or ReAct agent used its last allowed step.

    JoyAgent ends a plan normally when the executor runs out of steps on the
    last sub-task (the planner marks the step done and summarizes), so the
    final message alone does not show it; BaseAgent logs every step.
    """
    pattern = re.compile(rf"{re.escape(request_id)} (?:executor|react) Executing step (\d+)/(\d+)")
    return any(n == m for n, m in pattern.findall(backend_log))


# ---------- the AutoAgent call ----------

class EventRecorder:
    """Follows JoyAgent's SSE stream and derives the attempt status."""

    def __init__(self, events_path: Path) -> None:
        self.events: list[dict[str, Any]] = []
        self.events_file = open(events_path, "w", encoding="utf-8")
        self.tool_calls = 0
        self.result_text: str | None = None
        self.result_map: dict[str, Any] | None = None
        self.last_event = time.monotonic()

    def close(self) -> None:
        self.events_file.close()

    def record(self, event: dict[str, Any]) -> None:
        self.last_event = time.monotonic()
        self.events.append(event)
        self.events_file.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
        self.events_file.flush()
        kind = event.get("messageType")
        if kind == "tool_result":
            self.tool_calls += 1
            tr = event.get("toolResult") or {}
            logger.info("tool %s %s -> %s", tr.get("toolName"),
                        json.dumps(tr.get("toolParam"), ensure_ascii=False)[:300],
                        str(tr.get("toolResult")).replace("\n", " ⏎ ")[:300])
        elif kind in ("plan_thought", "tool_thought", "task"):
            text = event.get("planThought") or event.get("toolThought") or event.get("task") or ""
            if text and event.get("isFinal") is not False:
                logger.info("%s: %s", kind, str(text).replace("\n", " ")[:400])
        elif kind == "plan":
            logger.info("plan: %s", json.dumps(event.get("plan"), ensure_ascii=False)[:800])
        elif kind == "task_summary":
            logger.info("task summary: %s", str(event.get("taskSummary")).replace("\n", " ")[:400])
        elif kind == "result":
            self.result_text = event.get("result")
            self.result_map = event.get("resultMap")
            logger.info("result: %s", str(self.result_text).replace("\n", " ")[:800])

    def status(self, ended_by: str) -> str:
        if self.result_text is None and not self.result_map:
            return f"error_{ended_by}"
        text = self.result_text or ""
        if MAX_STEPS_TEXT in text:
            return "error_max_turns"
        if ERROR_TEXT in text:
            return "error"
        return "success"


def agent_thread_failed(genie: str, request_id: str) -> bool:
    """JoyAgent's controller logs this when the agent thread throws; the SSE
    stream is then never completed and only carries heartbeats."""
    logs = _run(["docker", "logs", "--since", "2m", genie], check=False)
    return f"{request_id} auto agent error" in logs.stdout + logs.stderr


def run_autoagent(port: int, request: dict[str, Any], recorder: EventRecorder,
                  proxy: LLMProxy, wall_timeout_sec: int, genie: str) -> str:
    """POST /AutoAgent and read the SSE stream; returns how the stream ended."""
    # JoyAgent sends a heartbeat every 10 s, so a silent socket means the
    # backend is gone (a timed-out socket cannot be read again anyway).
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=120)
    conn.request("POST", "/AutoAgent", body=json.dumps(request, ensure_ascii=False).encode(),
                 headers={"Content-Type": "application/json", "Accept": "text/event-stream"})
    resp = conn.getresponse()
    if resp.status != 200:
        raise RuntimeError(f"/AutoAgent returned {resp.status}: {resp.read()[:500]!r}")
    started = last_check = time.monotonic()
    data_lines: list[str] = []
    try:
        while True:
            now = time.monotonic()
            if now - started > wall_timeout_sec:
                return "timeout"
            if now - last_check > 30:
                last_check = now
                if agent_thread_failed(genie, request["requestId"]):
                    return "agent_error"
            if now - max(recorder.last_event, proxy.last_activity) > IDLE_TIMEOUT_SEC:
                return "idle"
            try:
                raw = resp.readline()
            except socket.timeout:
                return "stalled"
            if not raw:
                return "stream_end"
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            if line.startswith("data:"):
                data_lines.append(line[5:])
                continue
            if line or not data_lines:
                continue
            data, data_lines = "\n".join(data_lines), []
            if data.strip() == "heartbeat":
                continue
            try:
                event = json.loads(data)
            except ValueError:
                logger.debug("non-JSON SSE data: %s", data[:300])
                continue
            recorder.record(event)
            if event.get("messageType") == "result" or event.get("finish"):
                return "result"
    finally:
        conn.close()


# ---------- the main loop ----------

def run_task(db: str, args: argparse.Namespace, experiment_id: str, inputs_root: Path,
             proxy: LLMProxy, gateway: str) -> None:
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
        _run_task_body(db, args, instance_id, experiment_id, out_dir, agent_dir, inputs_root, proxy, gateway)
    finally:
        logger.removeHandler(db_handler)
        db_handler.close()


def _run_task_body(db: str, args: argparse.Namespace, instance_id: str, experiment_id: str,
                   out_dir: Path, agent_dir: Path, inputs_root: Path, proxy: LLMProxy,
                   gateway: str) -> None:
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

    # JoyAgent's config and logs go to joyagent/, which the task container
    # does not see (an empty tmpfs covers it).
    agent_dir.mkdir(parents=True, exist_ok=True)
    config_dir = agent_dir / "config"
    config_dir.mkdir(exist_ok=True)

    task_container = f"{experiment_id}-{db}"
    genie_container = f"{task_container}-genie"
    mcp_url = f"http://{task_container}:{MCP_PORT}/sse"
    proxy_url = f"http://{gateway}:{proxy.port}"
    data_agent = args.variant == "dataagent"
    db_config = data_agent_db_config(destination, out_dir / "config.yaml") if data_agent else None
    override_path = config_dir / "override.yml"
    write_override(override_path, genie_override(args, proxy_url, mcp_url, db_config))
    genie_env = {
        # genie-tool's own LLM calls (NL2SQL, table RAG, analysis) also go to the proxy.
        "GENIE_LLM_BASE_URL": f"{proxy_url}/v1",
        "GENIE_LLM_MODEL": args.model,
        "GENIE_DATA_AGENT_READ_TIMEOUT_SEC": str(DATA_AGENT_READ_TIMEOUT_SEC),
        "GENIE_ANA_DATA_TIMEOUT_SEC": str(DATA_AGENT_READ_TIMEOUT_SEC),
        "GENIE_DATA_ANALYSIS_TIMEOUT_SEC": str(DATA_ANALYSIS_TIMEOUT_SEC),
    } if data_agent else None

    proxy.reset(agent_dir / "llm_calls.jsonl")
    recorder = EventRecorder(agent_dir / "events.jsonl")
    request_id = f"{db}-{uuid.uuid4().hex[:12]}"
    ended_by, error, backend_log = "exception", None, ""
    started = time.time()
    try:
        start_task_container(task_container, out_dir, args.task_image)
        port = free_local_port()
        start_genie_container(genie_container, args.genie_image, config_dir, port, genie_env)
        proxy.allowed_ips = {container_ip(genie_container)}
        tools = check_mcp_tools(genie_container, mcp_url)
        logger.info("MCP tools visible to JoyAgent: %s", tools)
        missing = [t for t in MCP_TOOLS if t not in tools]
        if missing:
            raise RuntimeError(f"MCP tools missing: {missing}")

        system_prompt = adapt_prompt(SYSTEM_PROMPT_TEMPLATE, destination).format(
            container=task_container, image=args.task_image.split(":", 1)[0],
            network=NETWORK_NAME, container_workdir=CONTAINER_WORKDIR)
        destination_name = get_destination(destination).display_name
        query = (
            f"{system_prompt}\n"
            f"Build the ELT pipeline for the `{db}` now. "
            f"All configuration values (including the {destination_name} namespace) "
            "must come from /workspace/config.yaml.\n\n"
            f"{adapt_prompt(TASK_INSTRUCTION, destination)}"
        )
        request = {
            "requestId": request_id,
            "erp": "eltbench",
            "query": query,
            "agentType": AGENT_TYPES[args.mode],
            "basePrompt": "",
            "sopPrompt": "",
            "isStream": False,
        }
        if data_agent:
            # The web UI's 智能问数 (data agent) product with deep thinking.
            request["outputStyle"] = "dataAgent"
        ended_by = run_autoagent(port, request, recorder, proxy, args.timeout_hours * 3600, genie_container)
    except Exception as e:  # infrastructure failure: retried next time
        logger.exception("JoyAgent run failed")
        error = f"{type(e).__name__}: {e}"
    finally:
        recorder.close()
        backend_log = collect_genie_logs(genie_container, agent_dir / "genie-logs")
        remove_container(genie_container)
        remove_container(task_container)
        if db_config is not None:
            write_override(override_path, genie_override(args, proxy_url, mcp_url, mask_db_config(db_config)))

    status = recorder.status(ended_by) if error is None else "exception"
    if error is None and hit_step_limit(backend_log, request_id):
        status = "error_max_turns"
    usage = proxy.usage()
    cost = usage.get("cost_usd")
    if cost is None and args.price_in is not None and args.price_out is not None:
        cached = usage["cached_prompt_tokens"] if args.price_cached is not None else 0
        cost = ((usage["prompt_tokens"] - cached) * args.price_in
                + cached * (args.price_cached or 0.0)
                + usage["completion_tokens"] * args.price_out) / 1e6
    logger.info("run status: %s (ended by %s); %d tool calls, usage %s", status, ended_by,
                recorder.tool_calls, usage)

    common = {
        "instance_id": instance_id,
        "db": db,
        "model": args.model,
        "mode": args.mode,
        "variant": args.variant,
        "num_turns": recorder.tool_calls,
        "duration_sec": round(time.time() - started, 1),
        "total_cost_usd": cost,
        "usage": usage,
    }
    result_json = {
        **common,
        "finished": status == "success",
        "status": status,
        "ended_by": ended_by,
        "error": error,
        "result": recorder.result_text,
        "result_map": recorder.result_map,
        "trajectory": "events.jsonl",
    }
    (agent_dir / "result.json").write_text(json.dumps(result_json, indent=2, ensure_ascii=False, default=str))
    (agent_dir / "stats.json").write_text(json.dumps(common, indent=2, default=str))
    logger.info("Wrote %s", agent_dir / "result.json")


def main() -> None:
    args = parse_args()
    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        raise SystemExit(f"No API key: export {args.api_key_env}.")
    base_id = args.model.split("/")[-1]
    if args.variant == "dataagent":
        base_id = f"dataagent-{base_id}"
    if args.genie_image is None:
        args.genie_image = GENIE_DATAAGENT_IMAGE if args.variant == "dataagent" else GENIE_IMAGE
    experiment_id = f"joyagent-{base_id}-{args.suffix}-{args.destination}" if args.suffix \
        else f"joyagent-{base_id}-{args.destination}"
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

    gateway = network_gateway(NETWORK_NAME)
    proxy = LLMProxy(
        bind_host=gateway, upstream=args.base_url, api_key=api_key, model=args.model,
        drop_params=[p for p in args.drop_params.split(",") if p],
        rename_params=dict(p.split(":", 1) for p in args.rename_params.split(",") if p),
        extra_params=json.loads(args.extra_params) if args.extra_params else {},
        responses_api=args.responses_api,
    )
    logger.info("Experiment %s — %d tasks (mode %s, LLM proxy %s:%d -> %s)",
                experiment_id, len(databases), args.mode, gateway, proxy.port, args.base_url)
    try:
        for db in databases:
            try:
                run_task(db, args, experiment_id, inputs_root, proxy, gateway)
            except Exception:
                logger.exception("Task %s failed", db)
    finally:
        proxy.close()


def _parse_shard(value: str) -> tuple[int, int]:
    try:
        k, n = (int(x) for x in value.split("/"))
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected K/N, got {value!r}")
    if not 0 <= k < n:
        raise argparse.ArgumentTypeError(f"need 0 <= K < N, got {value!r}")
    return k, n


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run JoyAgent-JDGenie on ELT-Bench.")
    p.add_argument("--destination", choices=destination_choices(), default="snowflake")
    p.add_argument("--credential", help="Optional host-side destination credential JSON override.")
    p.add_argument("--database", help="Database/catalog holding one schema per task (default: "
                                      "'elt' for snowflake; one database (redshift) or catalog "
                                      "(databricks) per run, named after the experiment).")
    p.add_argument("--model", required=True, help="Model id sent to the provider, e.g. zai-org/GLM-5.3.")
    p.add_argument("--base-url", default="https://api.openai.com/v1",
                   help="OpenAI-compatible base URL of the provider.")
    p.add_argument("--api-key-env", default="OPENAI_API_KEY", help="Environment variable holding the API key.")
    p.add_argument("--mode", choices=sorted(AGENT_TYPES), default="plan_solve",
                   help="plan_solve: JoyAgent's planner + executor (its 'deep think' mode); "
                        "react: its single ReAct agent.")
    p.add_argument("--variant", choices=("default", "dataagent"), default="default",
                   help="default: main branch (genie/); dataagent: data_agent branch with its data "
                        "agent connected to the task schema (genie-dataagent/, see README).")
    p.add_argument("--max_turns", type=int, default=100,
                   help="JoyAgent step limit (executor tool-call steps over the whole task, "
                        "planner rounds, ReAct steps).")
    p.add_argument("--max-tokens", type=int, default=16384, help="max_tokens per LLM call.")
    p.add_argument("--max-input-tokens", type=int, default=128000,
                   help="JoyAgent truncates older messages beyond this many tokens.")
    p.add_argument("--max-observe", type=int, default=20000,
                   help="Characters of each tool result JoyAgent keeps.")
    p.add_argument("--temperature", type=float, default=0.0, help="JoyAgent's default is 0.")
    p.add_argument("--drop-params", default="", help="Comma-separated request parameters to remove, "
                                                     "e.g. temperature for models that reject it.")
    p.add_argument("--rename-params", default="", help="old:new pairs, e.g. max_tokens:max_completion_tokens.")
    p.add_argument("--extra-params", default="", help='JSON merged into every request, e.g. {"reasoning_effort": "high"}.')
    p.add_argument("--responses-api", action="store_true",
                   help="Send JoyAgent's chat requests to the provider's /responses endpoint "
                        "(needed for GPT-5.4: tools + reasoning_effort).")
    p.add_argument("--price-in", type=float, help="USD per 1M prompt tokens (for total_cost_usd).")
    p.add_argument("--price-out", type=float, help="USD per 1M completion tokens.")
    p.add_argument("--price-cached", type=float, help="USD per 1M cached prompt tokens (default: --price-in).")
    p.add_argument("--timeout-hours", type=float, default=6.0, help="Wall-clock limit per task.")
    p.add_argument("--suffix", "-s", default="eltbench", help="Experiment id suffix.")
    p.add_argument("--test_path", "-t", help="Per-task inputs directory (default: destination-specific).")
    p.add_argument("--elt_bench", help="Task directory (default: elt-bench/<destination>).")
    p.add_argument("--output_dir", default=str(AGENT_DIR / "output"))
    p.add_argument("--only", default="", help="Comma-separated DBs to run (default: all).")
    p.add_argument("--limit", type=int, default=100, help="Run only the first N DBs; 0 for no limit.")
    p.add_argument("--overwrite", action="store_true", help="Rerun tasks even if result.json exists.")
    p.add_argument("--task-image", default=TASK_IMAGE)
    p.add_argument("--genie-image", default=None,
                   help=f"Default: {GENIE_IMAGE}, or {GENIE_DATAAGENT_IMAGE} with --variant dataagent.")
    p.add_argument("--shard", type=_parse_shard, default=None, metavar="K/N",
                   help="Run only every N-th task starting at K (0-based).")
    return p.parse_args()


if __name__ == "__main__":
    main()

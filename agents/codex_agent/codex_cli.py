"""Codex CLI backend: run `codex exec` inside the task container with a
ChatGPT-plan (subscription) login instead of an API key.

The login lives in the host's ``~/.codex/auth.json``. Its tokens rotate on
refresh, and OpenAI's guidance is one auth.json per serialized job stream, so:

  * a process-wide lock allows only one CLI-backend runner per login;
  * each task gets a copy of auth.json in the container's CODEX_HOME, and the
    (possibly refreshed) copy is written back to the host after the task.
"""

from __future__ import annotations

import asyncio
import fcntl
import json
import logging
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("codex_agent")

CLI_IMAGE = "elt-swe-codex:0.160.0"
CLI_HOME = "/home/agent"  # Codex refuses to place its helpers under /tmp
CLI_CODEX_HOME = f"{CLI_HOME}/.codex"
HOST_AUTH = Path.home() / ".codex" / "auth.json"

# Features that add tools the other runners do not have (sub-agents, image
# generation, browser/computer use, plugins, MCP apps, ...). Web search is
# turned off with `-c web_search="disabled"`.
DISABLED_FEATURES = (
    "multi_agent", "image_generation", "goals", "plugins", "remote_plugin",
    "plugin_sharing", "skill_search", "skill_mcp_dependency_install", "hooks",
    "apps", "realtime_conversation", "tool_call_mcp_elicitation",
    "browser_use", "browser_use_external", "browser_use_full_cdp_access",
    "computer_use",
)
# Item types the agent is expected to produce; anything else is reported.
EXPECTED_ITEMS = frozenset({
    "agent_message", "reasoning", "command_execution", "file_change",
    "todo_list", "error",
})
TOOL_ITEMS = frozenset({"command_execution", "file_change", "mcp_tool_call", "web_search"})

USAGE_LIMIT = re.compile(r"usage.?limit|rate.?limit|too many requests|\b429\b", re.IGNORECASE)
AUTH_ERROR = re.compile(r"\b401\b|unauthori[sz]ed|refresh.?token|log ?in again|not logged in|token.{0,20}expired", re.IGNORECASE)


def _toml_string(text: str) -> str:
    # A JSON string literal is also a valid TOML basic string.
    return json.dumps(text)


class LoginLock:
    """Hold an exclusive lock on the host login for the whole process."""

    def __init__(self, auth: Path = HOST_AUTH) -> None:
        self.auth = auth
        self._fh = None

    def acquire(self) -> None:
        if not self.auth.is_file():
            raise SystemExit(
                f"No Codex login at {self.auth}. Run `codex login --device-auth` first."
            )
        self._fh = open(self.auth.with_suffix(".lock"), "w")
        try:
            fcntl.flock(self._fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit(
                "Another runner is using this Codex login. Its refresh tokens rotate, "
                "so the CLI backend runs as a single process (no parallel --shard runs)."
            ) from None


def seed_auth(container: str, uid: int, gid: int) -> None:
    import subprocess
    subprocess.run(
        ["docker", "exec", "-i", "-u", f"{uid}:{gid}", container, "sh", "-c",
         f"mkdir -p {CLI_CODEX_HOME} && umask 077 && cat > {CLI_CODEX_HOME}/auth.json"],
        input=HOST_AUTH.read_bytes(), check=True, capture_output=True,
    )


def sync_auth_back(container: str) -> None:
    """Persist a token refresh done inside the container to the host copy."""
    import subprocess
    out = subprocess.run(
        ["docker", "exec", container, "cat", f"{CLI_CODEX_HOME}/auth.json"],
        capture_output=True,
    )
    if out.returncode != 0:
        logger.warning("could not read auth.json back from %s", container)
        return
    try:
        new = json.loads(out.stdout)
        old = json.loads(HOST_AUTH.read_text())
    except (json.JSONDecodeError, OSError):
        logger.warning("auth.json from %s is not valid JSON; host copy kept", container)
        return
    if not new.get("tokens") or new.get("last_refresh") == old.get("last_refresh"):
        return
    fd, tmp = tempfile.mkstemp(dir=HOST_AUTH.parent, prefix=".auth-")
    with os.fdopen(fd, "wb") as f:
        f.write(out.stdout)
    os.chmod(tmp, 0o600)
    os.replace(tmp, HOST_AUTH)
    logger.info("Codex login refreshed in the container; host auth.json updated")


class CliRecorder:
    """Collects `codex exec --json` events into the runner's result fields."""

    def __init__(self) -> None:
        self.turns: list[dict[str, Any]] = []
        self.num_turns = 0  # tool calls (commands, file changes, ...)
        self.usage: dict[str, Any] | None = None
        self.total_cost_usd: float | None = None
        self.final_text = ""
        self.error_text = ""
        self.status: str | None = None
        self.is_error = False
        self.completed = False
        self.rate_limited = False
        self.rate_limit_resets_at: int | None = None
        self.auth_failed = False
        self.unexpected_items: list[str] = []

    def record(self, event: dict[str, Any]) -> None:
        etype = event.get("type")
        if etype == "item.completed":
            item = event.get("item") or {}
            itype = item.get("type")
            self.turns.append(item)
            if itype in TOOL_ITEMS:
                self.num_turns += 1
            if itype not in EXPECTED_ITEMS:
                self.unexpected_items.append(str(itype))
            if itype == "agent_message":
                self.final_text = item.get("text") or self.final_text
                logger.info("assistant: %s", (item.get("text") or "").strip()[:500])
            elif itype == "command_execution":
                logger.info("command: %s -> exit %s", str(item.get("command"))[:300], item.get("exit_code"))
                logger.debug("output:\n%s", item.get("aggregated_output"))
            elif itype == "file_change":
                logger.info("file_change: %s", json.dumps(item.get("changes"))[:300])
            elif itype == "error":
                logger.warning("codex notice: %s", str(item.get("message"))[:300])
            else:
                logger.info("item %s: %s", itype, json.dumps(item, default=str)[:300])
        elif etype == "turn.completed":
            self.completed = True
            usage = event.get("usage") or {}
            agg = self.usage or {}
            for k, v in usage.items():
                if isinstance(v, (int, float)):
                    agg[k] = agg.get(k, 0) + v
            self.usage = agg
        elif etype in ("turn.failed", "error"):
            self.turns.append(event)
            self._note_failure(event)

    def _note_failure(self, event: dict[str, Any]) -> None:
        blob = json.dumps(event, default=str)
        err = event.get("error") or {}
        self.error_text = (err.get("message") if isinstance(err, dict) else None) or event.get("message") or blob
        logger.error("codex %s: %s", event.get("type"), self.error_text[:500])
        if USAGE_LIMIT.search(blob):
            self.rate_limited = True
            self.rate_limit_resets_at = _find_reset(event) or self.rate_limit_resets_at
        elif AUTH_ERROR.search(blob):
            self.auth_failed = True

    def finalize(self, returncode: int | None, timed_out: bool, stderr: str) -> None:
        if not self.error_text and stderr.strip() and (returncode or 0) != 0:
            self.error_text = stderr.strip()[-2000:]
            if USAGE_LIMIT.search(stderr):
                self.rate_limited = True
            elif AUTH_ERROR.search(stderr):
                self.auth_failed = True
        if self.rate_limited:
            self.status = "rate_limited"
        elif timed_out:
            self.status = "timeout"
        elif self.auth_failed:
            self.status = "auth_error"
        elif self.completed and not self.error_text and (returncode or 0) == 0:
            self.status = "success"
        else:
            self.status = "error"
        self.is_error = self.status != "success"

    def sdk_style_usage(self) -> dict[str, Any] | None:
        """Usage in the SDK backend's shape, for the shared cost computation."""
        if not self.usage:
            return None
        return {
            "input_tokens": self.usage.get("input_tokens", 0),
            "input_tokens_details": {"cached_tokens": self.usage.get("cached_input_tokens", 0)},
            "output_tokens": self.usage.get("output_tokens", 0),
            "output_tokens_details": {"reasoning_tokens": self.usage.get("reasoning_output_tokens", 0)},
        }


def _find_reset(event: dict[str, Any]) -> int | None:
    """Best-effort reset time (Unix seconds) from a usage-limit error."""
    stack: list[Any] = [event]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ("resets_at", "reset_at") and isinstance(v, (int, float)):
                    return int(v)
                if k in ("resets_in_seconds", "reset_after_seconds") and isinstance(v, (int, float)):
                    return int(time.time() + v)
                stack.append(v)
        elif isinstance(node, list):
            stack.extend(node)
    return None


async def run_codex_exec(
    container: str,
    model: str,
    developer_instructions: str,
    prompt: str,
    timeout_sec: int,
    reasoning_effort: str | None = None,
) -> CliRecorder:
    """Run one task with `codex exec --json` inside `container`."""
    cmd = [
        "docker", "exec", "-i", "-w", "/workspace", "-e", f"CODEX_HOME={CLI_CODEX_HOME}",
        container, "codex", "exec", "--json",
        "--skip-git-repo-check", "--ephemeral", "--ignore-user-config", "--ignore-rules",
        # The task container is the sandbox; Codex's own sandbox would need
        # privileges the container does not have.
        "--dangerously-bypass-approvals-and-sandbox",
        "-C", "/workspace", "-m", model.split("/", 1)[-1],
        "-c", 'web_search="disabled"',
        "-c", f"developer_instructions={_toml_string(developer_instructions)}",
    ]
    if reasoning_effort:
        cmd += ["-c", f"model_reasoning_effort={_toml_string(reasoning_effort)}"]
    for feature in DISABLED_FEATURES:
        cmd += ["--disable", feature]
    cmd.append("-")  # prompt from stdin

    recorder = CliRecorder()
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        limit=64 * 1024 * 1024,
    )
    proc.stdin.write(prompt.encode())
    await proc.stdin.drain()
    proc.stdin.close()

    async def pump() -> None:
        async for raw in proc.stdout:
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("{"):
                continue
            try:
                recorder.record(json.loads(line))
            except Exception:
                logger.exception("could not record event: %s", line[:300])
        await proc.wait()

    stderr_task = asyncio.create_task(proc.stderr.read())
    timed_out = False
    try:
        await asyncio.wait_for(pump(), timeout=timeout_sec)
    except asyncio.TimeoutError:
        timed_out = True
        logger.warning("codex exec exceeded %ss; stopping it", timeout_sec)
        proc.kill()
        await proc.wait()
    stderr = (await stderr_task).decode("utf-8", errors="replace")
    if stderr.strip():
        logger.debug("codex stderr:\n%s", stderr[-4000:])
    recorder.finalize(proc.returncode, timed_out, stderr)
    return recorder

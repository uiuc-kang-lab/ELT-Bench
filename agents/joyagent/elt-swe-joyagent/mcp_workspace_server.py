"""MCP server giving JoyAgent shell and file tools inside an ELT task container.

JoyAgent-JDGenie adds tools from MCP servers (`autobots.autoagent.mcp_server_url`).
This server runs inside the task container (the shared `elt-swe` image), so
every command and file operation sees only that container: `/workspace` is
the task directory, mounted read-only except `/workspace/elt`.

Tools: bash, read_file, write_file, edit_file.

    python mcp_workspace_server.py --host 0.0.0.0 --port 8000   # SSE at /sse
"""

from __future__ import annotations

import argparse
import asyncio
import os
import signal
from pathlib import Path

from mcp.server.fastmcp import FastMCP

WORKDIR = Path(os.environ.get("ELT_WORKDIR", "/workspace"))
# Tool results go back into the model's context; keep the head and the tail.
MAX_OUTPUT_CHARS = int(os.environ.get("ELT_MCP_MAX_OUTPUT_CHARS", "10000"))
DEFAULT_TIMEOUT_SEC = 600
MAX_TIMEOUT_SEC = int(os.environ.get("ELT_MCP_MAX_TIMEOUT_SEC", "1800"))
MAX_READ_LINES = 2000
MAX_LINE_CHARS = 2000

mcp = FastMCP("elt-workspace")


def _resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else WORKDIR / p


def _clip(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    if len(text) <= limit:
        return text
    half = limit // 2
    return f"{text[:half]}\n... [{len(text) - limit} characters omitted] ...\n{text[-half:]}"


@mcp.tool()
async def bash(command: str, timeout: int = DEFAULT_TIMEOUT_SEC) -> str:
    """Run a bash command in /workspace inside the task container.

    Returns the exit code and the combined stdout/stderr (long output keeps
    its beginning and end). The command is killed after `timeout` seconds
    (default 600, at most 1800); each call starts a new shell, so `cd` and
    environment variables do not persist between calls. Do not run
    interactive commands.
    """
    timeout = max(1, min(int(timeout), MAX_TIMEOUT_SEC))
    proc = await asyncio.create_subprocess_exec(
        "bash", "-lc", command,
        cwd=WORKDIR,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        start_new_session=True,  # own process group, so a timeout kills children too
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        out, _ = await proc.communicate()
        text = out.decode("utf-8", errors="replace")
        return f"Command timed out after {timeout} s and was killed.\n{_clip(text)}"
    text = out.decode("utf-8", errors="replace")
    return f"Exit code: {proc.returncode}\n{_clip(text)}"


@mcp.tool()
def read_file(path: str, offset: int = 1, limit: int = MAX_READ_LINES) -> str:
    """Read a text file (relative paths are under /workspace).

    Returns lines `offset`..`offset+limit-1` (1-based) prefixed with line
    numbers; at most 2000 lines per call, long lines are cut at 2000 chars.
    """
    p = _resolve(path)
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as e:
        return f"Error: {e}"
    start = max(1, int(offset))
    limit = max(1, min(int(limit), MAX_READ_LINES))
    chunk = lines[start - 1:start - 1 + limit]
    body = "\n".join(f"{i:6d}\t{line[:MAX_LINE_CHARS]}" for i, line in enumerate(chunk, start))
    end = start + len(chunk) - 1
    note = f"[lines {start}-{end} of {len(lines)}]" if chunk else f"[file has {len(lines)} lines]"
    return f"{body}\n{note}" if body else note


@mcp.tool()
def write_file(path: str, content: str) -> str:
    """Create or overwrite a file with `content` (relative paths are under
    /workspace; only files under /workspace/elt may be written). Parent
    directories are created."""
    p = _resolve(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    except OSError as e:
        return f"Error: {e}"
    return f"Wrote {len(content)} characters to {p}"


@mcp.tool()
def edit_file(path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
    """Replace `old_string` with `new_string` in a file (relative paths are
    under /workspace). `old_string` must occur exactly once unless
    `replace_all` is true."""
    p = _resolve(path)
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as e:
        return f"Error: {e}"
    count = text.count(old_string)
    if not old_string or count == 0:
        return "Error: old_string not found in the file."
    if count > 1 and not replace_all:
        return f"Error: old_string occurs {count} times; add context to make it unique or set replace_all."
    try:
        p.write_text(text.replace(old_string, new_string), encoding="utf-8")
    except OSError as e:
        return f"Error: {e}"
    return f"Replaced {count if replace_all else 1} occurrence(s) in {p}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.run(transport="sse")


if __name__ == "__main__":
    main()

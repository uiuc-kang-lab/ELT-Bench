"""Unified entry point for ELT-Bench agents."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


AGENTS_DIR = Path(__file__).resolve().parent
RUNNERS = {
    "codex": AGENTS_DIR / "codex_agent/run.py",
    "claude": AGENTS_DIR / "claude_agent/run.py",
    "openhands": AGENTS_DIR / "openhands/run.py",
    "swe": AGENTS_DIR / "SWE-agent/run_elt.py",
}
DESTINATIONS = ("snowflake", "databricks", "redshift")


def parse_args(argv: list[str] | None = None) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(
        description="Run Codex, Claude, OpenHands, or SWE-agent on ELT-Bench."
    )
    parser.add_argument("agent", choices=RUNNERS)
    parser.add_argument("--destination", choices=DESTINATIONS, default="snowflake")
    args, runner_args = parser.parse_known_args(argv)
    return args, runner_args


def main(argv: list[str] | None = None) -> int:
    args, runner_args = parse_args(argv)
    command = [
        sys.executable,
        str(RUNNERS[args.agent]),
        "--destination",
        args.destination,
        *runner_args,
    ]
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())

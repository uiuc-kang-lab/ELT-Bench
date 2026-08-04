"""Run SWE-agent against any ELT-Bench destination."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml


SWE_ROOT = Path(__file__).resolve().parent
AGENTS_DIR = SWE_ROOT.parent
if str(AGENTS_DIR) not in sys.path:
    sys.path.insert(0, str(AGENTS_DIR))

from common import (  # noqa: E402
    adapt_prompt,
    destination_choices,
    prepare_destination,
    resolve_benchmark_path,
    resolve_inputs_path,
)


def _adapt_strings(value: Any, destination: str) -> Any:
    if isinstance(value, str):
        return adapt_prompt(value, destination)
    if isinstance(value, list):
        return [_adapt_strings(item, destination) for item in value]
    if isinstance(value, dict):
        return {key: _adapt_strings(item, destination) for key, item in value.items()}
    return value


def write_destination_config(destination: str, output_path: Path) -> None:
    with (SWE_ROOT / "config/elt_fc.yaml").open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    config = _adapt_strings(config, destination)
    with output_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(config, handle, sort_keys=False)


def copy_task_input(source: Path, destination: Path) -> None:
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns("*_credential.json"),
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", choices=destination_choices(), default="snowflake")
    parser.add_argument("--model", default="claude-3-5-sonnet-20241022")
    parser.add_argument("--suffix", default="eltbench")
    parser.add_argument("--cost-limit", type=float, default=6.0)
    parser.add_argument("--test_path", "-t")
    parser.add_argument("--elt_bench")
    parser.add_argument("--output_dir", default=str(AGENTS_DIR / "output"))
    parser.add_argument("--credential", help="Host-side credential JSON override.")
    parser.add_argument("--only", default="", help="Comma-separated task names.")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--skip-prepare",
        action="store_true",
        help="Do not reset the destination namespace before a task.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without preparing a warehouse or launching SWE-agent.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    inputs_root = resolve_inputs_path(args.destination, args.test_path)
    benchmark_root = resolve_benchmark_path(args.destination, args.elt_bench)
    if not inputs_root.is_dir():
        raise SystemExit(f"inputs dir not found: {inputs_root}")
    if not benchmark_root.is_dir():
        raise SystemExit(f"elt-bench dir not found: {benchmark_root}")

    tasks = sorted(path.name for path in benchmark_root.iterdir() if path.is_dir())
    if args.only:
        selected = {name.strip() for name in args.only.split(",") if name.strip()}
        tasks = [name for name in tasks if name in selected]
    if args.limit > 0:
        tasks = tasks[: args.limit]

    experiment = f"swe-{args.model.split('/')[-1]}-{args.suffix}-{args.destination}"
    output_root = Path(args.output_dir).expanduser().resolve() / experiment
    failures = 0

    with tempfile.TemporaryDirectory(prefix="elt-bench-swe-config-") as config_tmp:
        config_path = Path(config_tmp) / f"elt_fc_{args.destination}.yaml"
        write_destination_config(args.destination, config_path)

        for task in tasks:
            task_input = inputs_root / task
            task_output = output_root / task
            if task_output.exists() and not args.overwrite:
                print(f"SKIP {task}: output exists")
                continue

            with tempfile.TemporaryDirectory(prefix=f"elt-bench-{task}-") as workspace_tmp:
                workspace = Path(workspace_tmp) / "workspace"
                copy_task_input(task_input, workspace)
                command = [
                    "sweagent",
                    "run",
                    f"--env.repo.path={workspace}",
                    "--config",
                    str(config_path),
                    f"--problem_statement.id={task}",
                    "--agent.model.per_instance_cost_limit",
                    str(args.cost_limit),
                    "--agent.model.name",
                    args.model,
                ]
                print(f"RUN {task}: {' '.join(command)}")
                if args.dry_run:
                    continue

                if not args.skip_prepare:
                    try:
                        namespace = prepare_destination(
                            args.destination, task_input, args.credential
                        )
                        print(f"Prepared {namespace}")
                    except Exception as exc:
                        failures += 1
                        print(f"FAIL {task}: destination preparation failed: {exc}")
                        continue

                result = subprocess.run(command, cwd=SWE_ROOT, check=False)
                if task_output.exists():
                    shutil.rmtree(task_output)
                task_output.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(workspace, task_output)
                if result.returncode:
                    failures += 1
                    print(f"FAIL {task}: sweagent exited with {result.returncode}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

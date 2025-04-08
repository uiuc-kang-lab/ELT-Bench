import json
import logging
from pathlib import Path

from typing import Any, Dict, Literal, Optional

from inspect_ai import Task, task
from inspect_ai.model import ChatMessageUser
from inspect_ai.solver import TaskState, system_message, solver, Solver
from inspect_ai.tool import bash, python
from inspect_ai.util import sandbox, store
from dataset import create_dataset
from agent import get_agent
from inspect_ai.solver import bridge

from evaluation.eva import eva_stage1, eva_stage2, eva_elt

CHALLENGES_DIR = Path(__file__).parent / "inputs"


@task
def eltbench(
  challenges: str | list[str] | None = None,
  agent: str = 'default',
  agent_kwargs: Optional[Dict[str, Any]] = None,
):
  task_id = 'gpt'

  def get_challenge_dir_paths() -> list[Path]:
        # If no challenges are specified, use the default challenge directory.
        if challenges is None:
            return [CHALLENGES_DIR]
        if isinstance(challenges, str):
            return [_make_absolute(challenges)]
        return [_make_absolute(x) for x in challenges]

  dataset = create_dataset(
      get_challenge_dir_paths(),
  )

  agent_solver = get_agent(agent=agent, **agent_kwargs if agent_kwargs else {})
  
  plan = [agent_solver]
  return Task(
        dataset=dataset,
        solver=plan,
        scorer=[eva_elt(task_id)]
  )

def _make_absolute(challenge_dir: str) -> Path:
    path = Path(challenge_dir)
    if path.is_absolute():
        return path.resolve()
    return (CHALLENGES_DIR / path).resolve()


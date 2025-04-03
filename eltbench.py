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

CHALLENGES_DIR = Path(__file__).parent / "inputs"
@task
def eltbench(
  challenges: str | list[str] | None = None,
  agent: str = None,
  agent_kwargs: Optional[Dict[str, Any]] = None,
):
  print(22, agent)
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
  print(34, dataset)
  agent_solver = get_agent(agent=agent, **agent_kwargs if agent_kwargs else {})
  print(34, dataset)
  plan = [agent_solver]
  return Task(
        dataset=dataset,
        solver=plan
    )

def _make_absolute(challenge_dir: str) -> Path:
    path = Path(challenge_dir)
    if path.is_absolute():
        return path.resolve()
    return (CHALLENGES_DIR / path).resolve()

    
eltbench(agent='default')
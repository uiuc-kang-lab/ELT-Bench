from pathlib import Path
from typing import Generator, Literal
import os
import yaml
from inspect_ai.dataset import Dataset, MemoryDataset, Sample

from model import ChallengeInfo

CHALLENGE_INFO_FILENAME = "config.yaml"

def create_dataset(
    challenge_dirs: list[Path], sandbox_type: Literal["docker", "k8s"] = "docker"
) -> Dataset:
    """
    Create a dataset from a list of challenge directories.
    """
    return MemoryDataset(samples=list(_create_samples(challenge_dirs, sandbox_type)))

def _create_samples(
    challenge_dirs: list[Path], sandbox_type: Literal["docker", "k8s"]
) -> Generator[Sample, None, None]:
    directories = [name for name in os.listdir(challenge_dirs[0]) 
               if os.path.isdir(os.path.join(challenge_dirs[0], name))]
    for challenge_dir in directories:
        files_path = {'path': challenge_dir}
                
        yield Sample(
            id=f"{challenge_dir}",
            input='test model',
            files=files_path
        )

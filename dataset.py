from pathlib import Path
from typing import Generator, Literal
import os
import yaml
from inspect_ai.dataset import Dataset, MemoryDataset, Sample
from create_snowflake_db import create_database

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
        create_database(challenge_dir)
        path = os.path.join(challenge_dirs[0], challenge_dir)
        files_path = {'path': f"{path}/data"}
        yield Sample(
            id=f"{challenge_dir}",
            input='You are required to build an ELT pipeline by extracting data from multiple sources, such as custom APIs, Postgres, MongoDB, flat files and cloud service S3. The extracted data will be loaded into a target system, Snowflake, followed by writing transformation queries to construct final tables for downstream use.',
            files=files_path,
            sandbox=(
                    "docker",
                    f"{path}/compose.yaml"
            ),
        )

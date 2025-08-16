#!/usr/bin/env python3
"""
Script to run the agent on a SWE-bench problem in a Docker container.

This script loads a SWE-bench problem, starts a Docker container for it,
and runs the agent inside the container by calling cli.py.
"""

from functools import partial
import os
import logging
import threading
import sys
import json
import argparse
from pathlib import Path
from multiprocessing import Pool, Manager
import time
import numpy as np

from rich.console import Console
from rich.panel import Panel

from utils.docker_utils import MAX_DOCKER_CONCURRENCY, setup_workspace, stop_container, start_container
from utils.common import generate_patch
from cli import main as cli_main
import uuid
from utils.swebench_eval_utils import get_dataset_name, run_evaluation
import docker
from docker.models.containers import Container
from docker.errors import ImageNotFound
import pathlib
from create_snowflake_db import create_database


START_UP_DELAY = 2

def construct_container(problem_id):
        
    client = docker.from_env()
    container_name = 'testelt'
    #### delete existing container
    try:
        container = client.containers.get(container_name)
        container.stop()
        container.remove()
        print(f"Container {container_name} stopped and removed.")
    except docker.errors.NotFound:
        pass
    except docker.errors.APIError as e:
        pass
    mnt_dir = f'/mydata/elt/ELT-Bench/agents/augment-swebench-agent/inputs/{problem_id}'
    src_dir = pathlib.Path(mnt_dir).absolute().__str__()
    
    volumes = {src_dir: {'bind': '/workspace', 'mode': 'rw'}}
    allowed_params = ['command', 'ports', 'restart_policy', 'entrypoint', 'hostname', 'domainname', 'name', 'user', 'mac_address', 'platform', 'network_mode', 'network_disabled', 'healthcheck', "environment", "network"]
    
    kwargs_test = {"name": 'augment-eltbench-agent-'+problem_id,
                "work_dir": "/workspace",
                "network": "elt-docker_elt_network"}
    
    kwargs = {k: kwargs_test[k] for k in kwargs_test if k in allowed_params}
    
    extra_params = {'detach': True, 'tty': True, 'stdout': True, 'stderr': True, 'stdin_open': True, **kwargs}
    image_name = 'elt_agent-image:latest'
    try:
        client: DockerClient = docker.from_env()
        image = client.images.get(image_name)
        container: Container = client.containers.run(image=image, volumes=volumes, **extra_params)
    except ImageNotFound as e:
        dockerfile_path = os.path.join(DEFAULT_IMAGE_DIR, image_name)
        if os.path.exists(dockerfile_path):
            image = client.images.build(path=dockerfile_path, tag=image_name, rm=True)[0]
        else:
            image = client.images.pull(image_name)[0]
        container: Container = client.containers.run(image=image, volumes=volumes, **extra_params)
    except Exception as e:

        raise e

    time.sleep(START_UP_DELAY)

    return container.id


if __name__ == "__main__":
    databases = [f.name for f in os.scandir('../../elt-bench') if f.is_dir()]
    databases.sort()
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=int, default=0)
    args = parser.parse_args()
    index = args.index
    for problem_id in databases[index:index+1]:
        workspace_path = Path(f"/mydata/elt/ELT-Bench/agents/augment-swebench-agent/inputs/{problem_id}")
        create_database(problem_id)
        console = Console()
        logs_prefix = f"[bold blue]{problem_id}[/bold blue]"

        output_file = Path("/mydata/elt/ELT-Bench/agents/augment-swebench-agent/logs") / f"agent_logs_{problem_id}.txt"
        container_id = construct_container(problem_id)
        cli_args = [
            "cli.py",
            "--workspace",
            str(workspace_path),
            "--problem-statement",
            'Build an ELT pipeline',
            "--docker-container-id",
            container_id,
            "--use-container-workspace",
            "/workspace",
            "--minimize-stdout-logs",
        ]

        # Set logs path if output_file is specified
        if output_file:
            cli_args.extend(["--logs-path", str(output_file)])

        # Replace sys.argv with our custom arguments
        sys.argv = cli_args

        # Run the agent via cli.py
        console.print(f"{logs_prefix} Starting agent run...")
        start_time = time.time()
        cli_main()
        agent_duration = time.time() - start_time
        console.print(f"{logs_prefix} Agent run completed in {agent_duration:.2f}s.")


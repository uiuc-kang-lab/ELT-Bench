import openhands.agenthub
import asyncio
from evaluation.utils.shared import (
    EvalMetadata,
    EvalOutput,
    make_metadata,
    prepare_dataset,
    reset_logger_for_multiprocessing,
    run_evaluation,
    compatibility_for_eval_history_pairs,
    get_default_sandbox_config_for_eval
)
from openhands.controller.state.state import State
from openhands.core.config import (
    OpenHandsConfig,
    SandboxConfig,
    get_llm_config_arg,
    parse_arguments,
    load_openhands_config,
)
# from openhands.core.logger import openhands_logger as logger
from openhands.core.main import create_runtime, run_controller
from openhands.events.action import CmdRunAction, MessageAction
from openhands.events.observation import CmdOutputObservation, ErrorObservation
from openhands.runtime.base import Runtime
from openhands.utils.async_utils import call_async_from_sync
from create_snowflake_db import create_database
import pandas as pd
import os
from docker import DockerClient
import docker
import subprocess
from pathlib import Path

import zipfile
import logging
import datetime
import sys

logger = logging.getLogger("openhands")
datetime_str: str = datetime.datetime.now().strftime("%Y%m%d@%H%M%S")
file_handler = logging.FileHandler(os.path.join("logs", "normal-{:}.log".format(datetime_str)), encoding="utf-8")
file_handler.setLevel(logging.INFO)


formatter = logging.Formatter(
    fmt="\x1b[1;33m[%(asctime)s \x1b[31m%(levelname)s \x1b[32m%(module)s/%(lineno)d-%(processName)s\x1b[1;33m] \x1b[0m%(message)s")
file_handler.setFormatter(formatter)



logger.addHandler(file_handler)


def codeact_user_response(state: State) -> str:
    msg = (
        'Please continue working on the task on whatever approach you think is suitable.\n'
        'If you think you have completed the ELT pipeline, please finish the interaction using the "finish" tool.\n'
        'IMPORTANT: YOU SHOULD NEVER ASK FOR HUMAN HELP OR USE THE INTERNET TO SOLVE THIS TASK.\n'
    )
    if state.history:
        # check if the agent has tried to talk to the user 3 times, if so, let the agent know it can give up
        user_msgs = [
            event
            for event in state.history
            if isinstance(event, MessageAction) and event.source == 'user'
        ]
        if len(user_msgs) > 2:
            # let the agent know that it can give up when it has tried 3 times
            return (
                msg
                + 'If you want to give up, use the "finish" tool to finish the interaction.\n'
            )
    return msg


AGENT_CLS_TO_FAKE_USER_RESPONSE_FN = {
    'CodeActAgent': codeact_user_response,
}

def get_config(metadata: EvalMetadata, instance: pd.Series) -> OpenHandsConfig:

    sandbox_config = get_default_sandbox_config_for_eval()
    sandbox_config.base_container_image = 'elt_agent-image'
    # sandbox_config.keep_runtime_alive = True
    sandbox_config.volumes = f"/mydata/openhands/OpenHands/inputs/{instance.instance_id}:/workspace"
    sandbox_config.docker_runtime_kwargs = {"network": "elt-docker_elt_network"}



    # config = OpenHandsConfig(
    #     default_agent=metadata.agent_class,
    #     run_as_openhands=False,
    #     runtime='docker',
    #     max_iterations=metadata.max_iterations,
    #     sandbox=sandbox_config,
    #     # do not mount workspace
    #     workspace_base=None,
    #     workspace_mount_path=None,
    # )

    config = load_openhands_config()
    config.default_agent = metadata.agent_class
    config.max_iterations = metadata.max_iterations
    config.sandbox = sandbox_config
    config.runtime = 'docker'
    
    agent_config = config.get_agent_config(metadata.agent_class)
    agent_config.enable_prompt_extensions = False
    return config



def initialize_runtime(runtime: Runtime, instance: pd.Series):
    # Source directory containing all files
    source_dir = os.path.join('/mydata/elt/ELT-Bench/inputs', f'{instance.instance_id}/')
    
    # Ensure the source directory exists
    if not os.path.exists(source_dir):
        raise FileNotFoundError(f"Source directory {source_dir} does not exist")
    
    # Copy the entire directory to workspace
    runtime.copy_to(source_dir, '/workspace', recursive=True)
    create_database(instance.instance_id)
    print(f"Successfully copied {source_dir} to /workspace")


def process_instance(instance: pd.Series, metadata: EvalMetadata, reset_logger: bool = True) -> EvalOutput:
    config = get_config(metadata, instance)
    runtime = create_runtime(config)
    call_async_from_sync(runtime.connect)
    initialize_runtime(runtime, instance)

    with open('/mydata/openhands/OpenHands/evaluation/benchmarks/elt_bench/prompt.txt', 'r') as file:
        instruction = file.read()

    state: State | None = asyncio.run(
        run_controller(
            config=config,
            initial_user_action=MessageAction(content=instruction),
            fake_user_response_fn=AGENT_CLS_TO_FAKE_USER_RESPONSE_FN[
                metadata.agent_class
            ],
            runtime=runtime,
        )
    )

    histories = compatibility_for_eval_history_pairs(state.history)

    count = 0
    for history in histories:
        logger.info(f'Step: {count}')

        logger.info(f'Action: {history[0]}')
        logger.info(f'Observation: {history[1]}')
        logger.info(f'Action: {history[0].keys()}')
        logger.info(f'Observation: {history[1].keys()}')
        try:
            if count > 2:
                logger.info(f"Action: {history[0]['message']}")
                logger.info(f"Action type: {history[0]['action']}")
                logger.info(f"Thought: {history[0]['args']['thought']}")
                logger.info(f"\n\n")
                logger.info(f"Observation: {history[1]['message']}")
                logger.info(f"Observation type: {history[1]['observation']}")
                logger.info(f"Observation content: {history[1]['content']}")
                logger.info(f"Accumulated cost: {history[0]['llm_metrics']['accumulated_cost']}")
        except:
            e = 1
        logger.info('-'*100)
        count += 1
    logger.info(f"\n\n")

    output = EvalOutput(
        instance_id=instance.instance_id,
        instruction=instruction,
        metadata=metadata,
        history=histories,
        error=state.last_error if state and state.last_error else None,
        test_result={},
    )
    # res_path = runtime.copy_from('/workspace')

    # logger.info(f"Successfully copied {res_path} to /workspace")
    # # unzip the res_path
    # os.makedirs(f'/mydata/openhands/OpenHands/evaluation/benchmarks/elt_bench/output/{instance.instance_id}', exist_ok=True)
    # with zipfile.ZipFile(res_path, 'r') as zip_ref:
    #     zip_ref.extractall(f'/mydata/openhands/OpenHands/evaluation/benchmarks/elt_bench/output/{instance.instance_id}')



    return output


if __name__ == "__main__":
    args = parse_arguments()

    llm_config = None
    if args.llm_config:
        llm_config = get_llm_config_arg(args.llm_config)
        # modify_params must be False for evaluation purpose, for reproducibility and accurancy of results
        # llm_config.modify_params = False
    if llm_config is None:
        raise ValueError(f'Could not find LLM config: --llm_config {args.llm_config}')
    print(f'LLM config: {llm_config}')
    metadata = make_metadata(
        llm_config,
        'ELT-Bench',
        args.agent_cls,
        args.max_iterations,
        args.eval_note,
        args.eval_output_dir,
    )
    output_file = os.path.join(metadata.eval_output_dir, 'output.jsonl')
    databases = [f.name for f in os.scandir('/mydata/elt/ELT-Bench/inputs') if f.is_dir()]
    databases.sort()
    # databases = ['address', 'amplitude', 'app_store', 'asana', 'authors', 'beer_factory', 'bike_share_1', 'book_publishing_company', 'books', 'california_schools', 'car_retails', 'cars', 'chicago_crime', 'citeseer', 'codebase_comments', 'codebase_community', 'coinmarketcap', 'computer_student', 'cookbook', 'cs_semester', 'debit_card_specializing', 'disney', 'european_football_1', 'european_football_2', 'facebook_ads', 'financial', 'food_inspection', 'formula_1', 'github', 'hockey', 'image_and_language', 'instagram_business', 'language_corpus', 'law_episode', 'legislator', 'lever', 'mailchimp', 'marketo', 'microsoft_ads', 'mondial_geo', 'movie_3', 'movie_platform', 'movielens', 'movies_4', 'olympics', 'pardot', 'pinterest', 'professional_basketball', 'public_review_platform', 'qualtrics', 'recurly', 'regional_sales', 'restaurant', 'retail_complains', 'retail_world', 'retails', 'sales', 'sales_in_weather', 'shakespeare','simpson_episodes', 'soccer_2016', 'software_company', 'student_club', 'student_loan', 'superhero', 'synthea', 'talkingdata', 'thrombosis_prediction', 'tiktok_ads', 'toxicology', 'trains', 'twilio', 'twitter_organic', 'university', 'video_games', 'workday', 'works_cycles', 'world', 'world_development_indicators', 'xero', 'zuora']
    dataset = pd.DataFrame({'instance_id': databases[40:]})
    instances = prepare_dataset(dataset, output_file, args.eval_n_limit)
    run_evaluation(
        instances, metadata, output_file, args.eval_num_workers, process_instance
    )
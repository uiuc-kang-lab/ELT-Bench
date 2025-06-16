import os
import re
import json
import glob
import yaml
import uuid
import datetime
import subprocess
import concurrent.futures
from typing import List
from tqdm import tqdm
import tempfile
import argparse
import shutil

def load_config(config_path: str) -> dict:
    """Load configuration from a YAML file."""
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    required_keys = ['input_path', 'output_path', 'model_name', 'instance_id']
    for key in required_keys:
        if key not in config:
            raise ValueError(f"Missing required configuration key: {key}")
    return config

def find_content_for_action(node: dict, target_action: str) -> List[str]:
    """Recursively find content for a given action in the JSON structure."""
    results = []
    
    if isinstance(node, dict):
        action = node.get('action')
        if action and target_action in action:
            children = node.get('children', [])
            if children and isinstance(children[0], dict):
                content = children[0].get('content')
                if content:
                    results.append(content)
        
        for child in node.get('children', []):
            results.extend(find_content_for_action(child, target_action))
    
    return results

def extract_content_list(input_path: str, target_action: str) -> List[str]:
    """Extract a list of content strings matching the target action from the input JSON file."""
    with open(input_path, 'r') as f:
        data = json.load(f)
    root = data.get('root', {})
    content_list = find_content_for_action(root, target_action)
    content_list = [content.split('(Open file')[0] for content in content_list]
    return content_list

def run_evaluation(
    content: str,
    idx: int,
    model_name: str,
    instance_id: str
) -> dict:
    """Run the evaluation process for a single content item."""
    run_id = f"eval_{idx}_{uuid.uuid4().hex[:8]}"

    # Create a temporary directory for this run
    temp_dir = tempfile.mkdtemp()

    # Create a temporary file in the temp_dir
    temp_filename = f"temp_{run_id}.jsonl"
    temp_file_path = os.path.join(temp_dir, temp_filename)
    with open(temp_file_path, 'w') as temp_file:
        json.dump({
            "model_name_or_path": model_name,
            "instance_id": instance_id,
            "model_patch": content
        }, temp_file)
        temp_file.write('\n')

    command = [
        "python", "-m", "swebench.harness.run_evaluation",
        "--dataset_name", "princeton-nlp/SWE-bench_Lite",
        "--predictions_path", temp_file_path,
        "--max_workers", "1",
        "--run_id", run_id
    ]

    try:
        output = subprocess.check_output(
            command,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            timeout=1200,  # 20-minute timeout
            cwd=temp_dir  # Set the working directory to temp_dir
        )
        status = "success"
    except subprocess.CalledProcessError as e:
        output = e.output
        status = "error"
    except subprocess.TimeoutExpired:
        output = "Evaluation timed out after 20 minutes"
        status = "timeout"
    except Exception as e:
        output = f"Unexpected error: {str(e)}"
        status = "unexpected_error"
    finally:
        # Clean up: delete the temporary directory and its contents
        shutil.rmtree(temp_dir)
        files = glob.glob(f'{model_name}*.json')
        for f in files:
            os.remove(f) 

    result = {"run_id": run_id, "output": output, "status": status, "content": content}

    # Do not save individual result files
    return result

def parallel_evaluation(
    content_list: List[str],
    max_workers: int,
    model_name: str,
    instance_id: str
) -> List[dict]:
    """Run evaluations in parallel using a thread pool."""
    results = [None] * len(content_list)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {
            executor.submit(run_evaluation, content, idx, model_name, instance_id): idx
            for idx, content in enumerate(content_list)
        }
        
        # Initialize the progress bar
        with tqdm(total=len(content_list), desc="Evaluations", unit="task") as pbar:
            for future in concurrent.futures.as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    results[idx] = {
                        "run_id": f"eval_{idx}",
                        "output": f"Exception occurred: {str(e)}",
                        "status": "thread_error",
                        "content": content_list[idx]
                    }
                finally:
                    pbar.update(1)  # Update the progress bar
    
    return results

def process_results(results):
    resolved = 0
    unresolved = 0

    for result in results:
        output = result['output']
        resolved_match = re.search(r'Instances resolved: (\d+)', output)
        unresolved_match = re.search(r'Instances unresolved: (\d+)', output)
        
        if resolved_match:
            resolved += int(resolved_match.group(1))
        if unresolved_match:
            unresolved += int(unresolved_match.group(1))
    
    print(f"Resolved Cases: {resolved}")
    print(f"Unresolved Cases: {unresolved}")

def main():
    parser = argparse.ArgumentParser(description="Run evaluation on content based on the provided config file.")
    parser.add_argument(
        '--config_path', 
        type=str, 
        default='config.yaml',  # Default to 'config.yaml' if not provided
        help="Path to the YAML configuration file (default: 'config.yaml')."
    )
    args = parser.parse_args()
    config = load_config(args.config_path)
    input_path = config['input_path']
    output_path = config['output_path']
    num_workers = config.get('num_workers', 4)
    model_name = config['model_name']
    instance_id = config['instance_id']
    target_action = config.get('target_action', 'submit')  # Default to 'submit' if not specified

    content_list = extract_content_list(input_path, target_action)
    eval_data = []
    if os.path.exists(f'{output_path}/overall_evaluation_results.json'):
        with open(f'{output_path}/overall_evaluation_results.json', 'r') as f:
            eval_data = json.load(f)
        unevaluated_patch = []
        for i in eval_data:
            output = i['output']
            status = i['status']
            unresoved_match = re.search(r'Instances unresolved: (\d+)', output)
            if status == 'error':
                unevaluated_patch.append(i['content'])
            elif unresoved_match and int(unresoved_match.group(1)) == 0:
                unevaluated_patch.append(i['content'])
        content_list = unevaluated_patch

    save_directory = output_path
    os.makedirs(save_directory, exist_ok=True)
    evaluation_results = parallel_evaluation(
        content_list,
        num_workers,
        model_name,
        instance_id
    )
    for i in eval_data:
        for j in evaluation_results:
            if i['content'] == j['content']:
                i['status'] = j['status']
                i['output'] = j['output']
                break
    if eval_data:
        evaluation_results = eval_data
    # Print or process the results
    for result in evaluation_results:
        print(f"Run ID: {result['run_id']}")
        print(f"Content: {result['content'][:100]}...")
        print(f"Status: {result['status']}")
        print(f"Output: {result['output'][:100]}...")  # Print first 100 characters of output
        print("---")
    
    # Save the overall results to a file
    overall_results_path = os.path.join(save_directory, "overall_evaluation_results.json")
    with open(overall_results_path, "w") as f:
        json.dump(evaluation_results, f, indent=2)
    
    print("Total Cases:", len(evaluation_results))
    process_results(evaluation_results)

    print(f"Overall results have been saved to '{overall_results_path}'.")

if __name__ == "__main__":
    main()

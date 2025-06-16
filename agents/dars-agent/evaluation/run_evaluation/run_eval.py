#!/usr/bin/env python3

import subprocess
from pathlib import Path
import json
import logging
import yaml
from typing import List, Dict
import argparse

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class EvaluationConfig:
    def __init__(self, base_dir: str, run_id: str, python_script: str, 
                 config_template: str, instances: List[str] = None):
        self.base_dir = Path(base_dir)
        self.run_id = run_id
        self.python_script = python_script
        self.config_template = config_template
        self.instances = instances

    @property
    def trajectory_dir(self) -> Path:
        return self.base_dir / "results" / f"dars_run/run_{self.run_id}/trajectory"
    
    @property
    def output_dir(self) -> Path:
        return self.base_dir / "results" / f"dars_run/run_{self.run_id}/evaluation_results"

    @classmethod
    def from_yaml(cls, config_path: str, run_id: str = None, instances: List[str] = None):
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        # Override run_id and instances if provided
        if run_id:
            config['run_id'] = run_id
            
        return cls(
            base_dir=config['base_dir'],
            run_id=config['run_id'],
            python_script=config['python_script'],
            config_template=config['config_template'],
            instances=instances
        )

class PatchEvaluator:
    def __init__(self, config: EvaluationConfig):
        self.config = config
        self.setup_directories()
        
    def setup_directories(self):
        """Ensure all necessary directories exist."""
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
    
    def update_config_yaml(self, instance_id: str) -> Path:
        """Update configuration YAML file for the current instance."""
        input_path = self.config.trajectory_dir / instance_id / f"{instance_id}.prev.root"
        output_path = self.config.output_dir / instance_id
        
        with open(self.config.config_template) as f:
            config_data = yaml.safe_load(f)
        
        config_data.update({
            'input_path': str(input_path),
            'instance_id': instance_id,
            'output_path': str(output_path)
        })
        
        temp_config = self.config.output_dir / f"config_{instance_id}.yaml"
        with open(temp_config, 'w') as f:
            yaml.dump(config_data, f)
            
        return temp_config
    
    def evaluate_instance(self, instance_id: str) -> bool:
        """Evaluate a single instance."""
        config_path = self.update_config_yaml(instance_id)
        try:
            result = subprocess.run(
                ['python', str(self.config.python_script), '--config_path', str(config_path)],
                capture_output=True,
                text=True,
                check=True
            )
            logging.info(f"Successfully evaluated instance {instance_id}")
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"Error evaluating instance {instance_id}: {e.stderr}")
            return False
        finally:
            config_path.unlink(missing_ok=True)  # Clean up temporary config
    
    def is_patch_accepted(self, patch: Dict) -> bool:
        """Determine if a patch is accepted based on resolution status."""
        output = patch.get('output', '').lower()
        
        # Extract resolution counts
        resolved = 0 if "instances resolved: 0" in output else (
            1 if "instances resolved: 1" in output else 2
        )
        unresolved = 0 if "instances unresolved: 0" in output else (
            1 if "instances unresolved: 1" in output else 2
        )
        
        # Apply acceptance criteria
        if (resolved == 0 and unresolved == 0) or resolved == 2 or unresolved == 2:
            return False
        return resolved > 0
    
    def process_evaluation_results(self) -> int:
        """Process all evaluation results and return total resolved count."""
        total_resolved = 0
        result_files = self.config.output_dir.glob("*/overall_evaluation_results.json")
        
        for result_file in result_files:
            try:
                with open(result_file) as f:
                    patches = json.load(f)
                if any(self.is_patch_accepted(patch) for patch in patches):
                    total_resolved += 1
            except Exception as e:
                logging.error(f"Error processing {result_file}: {e}")
                
        return total_resolved

def get_instances_to_evaluate(config: EvaluationConfig) -> List[str]:
    """Determine which instances to evaluate based on config."""
    if config.instances and len(config.instances) > 0:
        logging.info(f"Evaluating specified instances: {config.instances}")
        return config.instances
    
    # Fallback to original approach: scanning all instances in trajectory directory
    logging.info("No instances specified, falling back to scanning all instances...")
    original_instances = [
        p.parent.name 
        for p in config.trajectory_dir.glob("*/*.prev.root")
    ]
    if not original_instances:
        logging.warning(f"No instances found in trajectory directory: {config.trajectory_dir}")
    else:
        logging.info(f"Found {len(original_instances)} instances to evaluate")
    return original_instances

def main():
    parser = argparse.ArgumentParser(description='Evaluate patches for specified instances')
    parser.add_argument('--config', default='evaluation_config.yaml', help='Path to eval config file')
    parser.add_argument('--run_id', help='Override run_id from config')
    parser.add_argument('--instances', nargs='+', help='List of specific instances to evaluate')
    args = parser.parse_args()
    
    # Load configuration with optional overrides
    config = EvaluationConfig.from_yaml(args.config, args.run_id, args.instances)
    evaluator = PatchEvaluator(config)
    
    # Get instances to evaluate
    try:
        instances = get_instances_to_evaluate(config)
    except Exception as e:
        logging.error(f"Error determining instances to evaluate: {e}")
        return
    
    # Evaluate instances
    for instance_id in instances:
        evaluator.evaluate_instance(instance_id)
    
    # Process results
    total_resolved = evaluator.process_evaluation_results()
    logging.info(f"Total resolved instances: {total_resolved}")

if __name__ == "__main__":
    main()
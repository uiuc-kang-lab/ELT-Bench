import hydra
import os
from omegaconf import DictConfig
import subprocess

@hydra.main(version_base=None, config_path="./", config_name="run_dars_config")
def main(cfg: DictConfig) -> None:
    config_map = {
        "swe-agent": "config/default.yaml",
        "dars": "config/default_dars.yaml",
    }

    assert cfg.agent in config_map, f"Agent {cfg.agent} not supported. Supported agents: {list(config_map.keys())}"

    for instance in cfg.instances:
        print(f"\nProcessing instance: {instance}")
        command = [
            "python", "run.py",
            "--model_name", cfg.model.name,
            "--per_instance_cost_limit", str(cfg.model.cost_limit),
            "--instance_filter", instance,
            "--split", cfg.split,
            "--config", config_map[cfg.agent],
        ]
        
        if hasattr(cfg, 'skip_existing'):
            command.extend(["--skip_existing", str(cfg.skip_existing)])
        
        print(f"Running command: {' '.join(command)}")
        
        result = subprocess.run(command, text=True)
        if result.returncode != 0:
            print(f"Command failed for instance {instance} with return code {result.returncode}")

if __name__ == "__main__":
    main()
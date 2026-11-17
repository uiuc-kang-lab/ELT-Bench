"""Transformation-only variant of the ELT-Bench task.

The warehouse namespace starts as a clone of the loaded ground-truth source
tables (``prepare_destination(..., source_database=...)``), and the agent is
asked for the dbt stage only.  The workspace keeps what that stage needs:
``data_model.yaml``, ``schemas/``, and a ``config.yaml`` reduced to the
destination section; the Airbyte documentation, ``elt/main.tf`` and the job
checker are left out.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml


# The Stage 2 hints of the full task, unchanged except where they pointed back
# to Stage 1.
TRANSFORM_TASK_INSTRUCTION = """We're currently building the data transformation stage of the ELT pipeline using DBT. Data extraction and loading is already complete: every source table described in /workspace/schemas has been loaded into the Snowflake database and schema given in /workspace/config.yaml. Here's the detailed instruction:

INSTRUCTIONS:
#  Data Transformation Hints#
1. Initialize the DBT Project: Set up a new DBT project by configuring it with /workspace/config.yaml, and remove the example directory under the models directory.
2. Understand the Data Model: Review data_model.yaml in /workspace to understand the required data models and their column descriptions. Then, write SQL queries to generate these defined data models, referring to the files in the /workspace/schemas directory to understand the schemas of source tables.
• Important: Write a separate query for each data model, and if using any DBT project variables, ensure they have already been declared.
3. Validate Table Locations: Ensure all SQL queries reference the correct database and schema names for source tables. If you encounter a "table not found" error, refer to /workspace/config.yaml to obtain the correct configuration. Do not modify, drop, or reload the source tables.
4. Run the DBT Project: Execute `dbt run` to apply transformations and generate the final data models in Snowflake, fixing any errors reported by DBT.
5. Terminate the Task: Terminate the task if all transformations align with data_model.yaml and the final tables in Snowflake are accurate and verified. Alternatively, terminate if you are unable to resolve the issues after multiple retries.

When done (or giving up), print a single final line:
    RESULT: SUCCESS   — final tables populated
    RESULT: FAIL: <short reason>
"""

WORKSPACE_FILES = ("data_model.yaml", "schemas")


def copy_transform_inputs(src: Path, dst: Path, destination: str) -> None:
    """Populate the workspace for a transformation-only run of one task."""
    dst.mkdir(parents=True, exist_ok=True)
    for name in WORKSPACE_FILES:
        item = src / name
        if item.is_dir():
            shutil.copytree(item, dst / name, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dst / name)
    with (src / "config.yaml").open(encoding="utf-8") as f:
        config = yaml.safe_load(f)
    with (dst / "config.yaml").open("w", encoding="utf-8") as f:
        yaml.safe_dump({destination: config[destination]}, f, sort_keys=False)
    (dst / "elt").mkdir(exist_ok=True)

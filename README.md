# ELT-Bench
The first comprehensive, end-to-end benchmark designed to evaluate AI agents in automating ELT pipelines.
![ELT](https://anonymous.4open.science/r/ELT-Bench-B51C/materials/elt.svg)

[![License](https://img.shields.io/badge/License-CC%20BY%20SA%204.0-orange.svg)](https://creativecommons.org/licenses/by-sa/4.0/deed.en)
## Environment Setup

### Install Docker and Conda 
- Ensure your machine has the [Docker environment](https://docs.docker.com/get-docker/) and the [Conda environment](https://docs.conda.io/projects/conda/en/stable/user-guide/install/index.html) installed.

### Install Airbyte 
- You can deploy Airbyte Open Source by following the [official documentation](https://docs.airbyte.com/using-airbyte/getting-started/oss-quickstart).  
*Note:* You may need to add `sudo` before `abctl` commands.

### Setup Airbyte 

- Navigate to [http://localhost:8000/](http://localhost:8000/) in your web browser. Set your username. To retrieve your password, execute:
  ```bash
  (sudo) abctl local credentials
  ```

- In the Airbyte UI, go to Builder > Import a YAML. Upload the manifest matching
  your destination:

  | Destination | Manifest |
  | --- | --- |
  | Snowflake | `./setup/elt_snowflake.yaml` |
  | Databricks | `./setup/elt_databricks.yaml` |
  | Redshift | `./setup/elt_redshift.yaml` |

Click on the Publish button, type ignore warnings, and publish it to your workspace.

- In the Airbyte UI, go to **Sources > Custom > ELT Bench**. Retrieve the Workspace ID and Definition ID from the URL:
  ```
  http://localhost:8012/workspaces/<workspace_id>/source/new-source/<api_definition_id>
  ```
  Update the file `./setup/airbyte/airbyte_credentials.json` by filling in the following information: username, password, workspace ID, and API definition ID.


### Install psql
- To insert data into PostgreSQL without installing the complete PostgreSQL database server, you can use the `psql` command-line tool. 
Please refer to the [installation instructions](https://www.timescale.com/blog/how-to-install-psql-on-mac-ubuntu-debian-windows) to install `psql` on your machine.
After successful installation, you can confirm the installation by running:

  ```bash
  psql --version
  ```

### Set up data destination

ELT-Bench ships destination-specific configurations for three data warehouses. All three
use the single shared set of schema descriptions in `./elt-bench/schemas`; the warehouse
directories differ only in the destination block of each `config.yaml`:

| Version | Benchmark folder | Config generator |
| --- | --- | --- |
| Snowflake | `./elt-bench/snowflake` | `python write_config.py --destination snowflake` |
| Databricks | `./elt-bench/databricks` | `python write_config.py --destination databricks` |
| Redshift | `./elt-bench/redshift` | `python write_config.py --destination redshift` |

Set up whichever destination you plan to evaluate against.

#### Snowflake
- Refer to the example in `./setup/destination/setup.sql`. Copy all the contents into a Snowflake worksheet and execute "Run all" to create the necessary credentials.

- Fill in the required values in `./setup/destination/snowflake_credential.json` to ensure Airbyte can successfully connect to Snowflake.

#### Databricks
- Create a SQL warehouse in your Databricks workspace and note its **Server Hostname** and **HTTP Path**.

- Create a service principal with an OAuth secret and grant it access to that SQL warehouse, then note its **Client ID** and **Secret**. See `./documentation/databricks_authentication.md` for the authentication options supported by the Databricks SQL connector.

- Fill in the required values in `./setup/destination/databricks_credential.json` to ensure Airbyte can successfully connect to Databricks.

#### Redshift
- Create or select a Redshift provisioned cluster or Serverless workgroup and an S3 bucket that Airbyte can use for staging.

- Fill in the required values in `./setup/destination/redshift_credential.json`. The AWS access key must have read and write access to the staging bucket. Connector configuration details are available in `./documentation/destination_redshift.md`.

### Generate agent inputs
- Generate the per-database input bundles (config, schemas, data model, documentation) for your chosen destination:

  ```bash
  cd ./setup
  python write_config.py --destination snowflake    # -> ../inputs
  python write_config.py --destination databricks   # -> ../inputs_databricks
  python write_config.py --destination redshift     # -> ../inputs_redshift
  ```

  `write_config.py` copies schemas from the shared
  `./elt-bench/schemas/<database>` directory into every generated input bundle.

  The legacy `write_config_databricks.py` and `write_config_redshift.py` commands remain available as compatibility wrappers.

### Run ELT setup
- Execute the script to create Docker containers for various sources, download both source data and ground truth results for evaluation, and insert the data.
  ```bash
  cd ./setup
  bash elt_setup.sh
  ```

## Running agents
- To evaluate the Spider-Agent and SWE-agent on ELT-Bench, follow the instructions in the `agents` folder. This folder contains detailed steps for running each agent.

- Agents read the generated input bundles from `../../inputs` by default. For another destination, point them at the matching bundles, e.g. `python run.py -t ../../inputs_databricks/` or `python run.py -t ../../inputs_redshift/`.

## Evaluation

- To evaluate the performance of an agent, use the following commands:

  ```bash
  cd evaluation
  pip install -r requirements.txt

  python eva.py --folder run_name --db-type snowflake \
    --gt-folder /path/to/gt_snowflake

  python eva.py --folder run_name --db-type databricks \
    --database catalog_name --gt-folder /path/to/gt_databricks

  python eva.py --folder run_name --db-type redshift \
    --gt-folder /path/to/gt_redshift
  ```

  Credentials default to `./setup/destination/<db-type>_credential.json`; override this with `--credential` when needed. Use `--stage 1` or `--stage 2` to run a single stage and `--only db1,db2` to evaluate selected task schemas.

  Results are written to `./evaluation/agent_results/<run_name>`. Stage 2 requires a warehouse-specific ground-truth CSV directory containing `<schema>/<table>.csv`.

  The 100 database-specific evaluation SQL directories are organized under `./evaluation/sql`. Queries use the warehouse-neutral `schema.table` form (for example, `shipping.drivers`). Before execution, the connector maps it to Snowflake's `database.AIRBYTE_SCHEMA.table`, Databricks' `catalog.schema.table`, or Redshift's `schema.table` layout.

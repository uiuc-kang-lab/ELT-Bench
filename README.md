# ELT-Bench

## Setup

### Install Docker
Ensure that your machine has installed [`docker` environment](https://docs.docker.com/get-docker/) before proceeding.

### Install Airbyte 
Airbyte is a leading data integration platform for ELT pipelines from APIs, databases & files to databases, warehouses & lakes. You can deploy Airbyte Open Source by following the [official documentation](https://docs.airbyte.com/using-airbyte/getting-started/oss-quickstart). You may need to add sudo before abctl.

### Create Docker Containers for Different Data Sources
You can create the docker container for Postgres, MongoDB, LocalStack (AWS S3 simulator), and API by running following commands:
```
cd ./elt-docker
docker compose up -d
```

Then connect the Airbyte container to the same network.
```
docker network connect elt-docker_elt_network airbyte-abctl-control-plane
```

### Set up data sources
After creating the containers, you can now insert data by running following commands. Replace '<path>' with the actual data path, for exmaple, if the data is located in '/mydata/elt/data/', replace '<path>' with '/mydata/elt'

```
cd ./setup
bash data_setup.sh <path>
```

### Set up data destination - Snowflake
First, create the necessary credentials to access the Snowflake database by referring to the example in ./setup/destination/setup.sql.
Next, fill in the required values in ./setup/destination/snowflake_credential to ensure Airbyte can successfully connect to Snowflake.

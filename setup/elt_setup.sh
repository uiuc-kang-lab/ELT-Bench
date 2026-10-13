#!/usr/bin/env bash
# Create and activate the Python environment before running this script
# (`conda activate` does not work inside a non-interactive script):
#   conda create -y -n elt python=3.11
#   conda activate elt
#   pip install -r requirements.txt

set -e

CURRENT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd -- "$CURRENT_DIR"

# Source data (REST API files and database dumps) and ground truth.
gdown 'https://drive.google.com/uc?id=1qVAzU3kgn_G72QQ4b5zt3e1hwkQcSgDq'
gdown 'https://drive.google.com/uc?id=1-Gv5g_Yg_YrR-NxH4s2tSEK3VhJQc2Q0'
gdown 'https://drive.google.com/uc?id=11vQqNEWXoPG6sjKytAn7TtFLDMiQa17I'

unzip data_api.zip -d ../elt-docker/rest_api
unzip data_db.zip -d ./
unzip gt.zip -d ../evaluation

# Source containers, reachable from Airbyte.
cd ../elt-docker
docker compose up -d
docker network connect elt-docker_elt_network airbyte-abctl-control-plane
cd -- "$CURRENT_DIR"

bash data_setup.sh "$CURRENT_DIR"
python mongo.py --path "$CURRENT_DIR"
# Import/publish the connector, create its Source, and fill Airbyte credentials.
python setup_airbyte.py
python write_config.py

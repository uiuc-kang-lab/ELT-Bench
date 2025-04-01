
conda create -y -n elt
conda activate elt
conda install -y python=3.11
pip install -r requirements.txt

gdown 'https://drive.google.com/uc?id=1qVAzU3kgn_G72QQ4b5zt3e1hwkQcSgDq'
gdown 'https://drive.google.com/uc?id=1-Gv5g_Yg_YrR-NxH4s2tSEK3VhJQc2Q0'
gdown 'https://drive.google.com/uc?id=11vQqNEWXoPG6sjKytAn7TtFLDMiQa17I'

unzip data_api.zip -d ../elt-docker/rest_api
unzip data_db.zip -d ./
unzip gt.zip -d ../evaluation
unzip 
cd ../elt-docker
docker compose up -d
docker network connect elt-docker_elt_network airbyte-abctl-control-plane
cd ../setup

CURRENT_DIR=$(pwd)
bash data_setup.sh CURRENT_DIR
python mongo.py --path CURRENT_DIR
python write_config.py
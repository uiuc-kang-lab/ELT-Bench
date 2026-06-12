#!/bin/bash
set -e  # Exit on error

# Inherit conda environment from parent shell
if [ -n "$CONDA_PREFIX" ]; then
    # Initialize conda for this shell
    eval "$(conda shell.bash hook)"
    conda activate "$CONDA_PREFIX"
fi

echo "=============================================="
echo "  ELT-Bench-Verified Setup"
echo "=============================================="
echo ""

# Phase 1: Download data archives
echo "[1/6] Downloading data archives from Google Drive..."
echo "      This may take a few minutes depending on your connection."
echo ""

if [ -f "data_api.zip" ]; then
    echo "      data_api.zip already exists, skipping download"
else
    gdown 'https://drive.google.com/uc?id=1YSIYFYfr6nXz076dfx8F_rwNv0xFIJRp' -O data_api.zip || { echo "ERROR: Failed to download data_api.zip"; exit 1; }
fi

if [ -f "data_db.zip" ]; then
    echo "      data_db.zip already exists, skipping download"
else
    gdown 'https://drive.google.com/uc?id=1OKfoGh6aynBNcR9KltPJagp2cfNwZOfS' -O data_db.zip || { echo "ERROR: Failed to download data_db.zip"; exit 1; }
fi

if [ -f "ground_truth.zip" ]; then
    echo "      ground_truth.zip already exists, skipping download"
else
    gdown 'https://drive.google.com/uc?id=1AzSYAOjDr3Tz_GZVVIs49zWV6q8HST22' -O ground_truth.zip || { echo "ERROR: Failed to download ground_truth.zip"; exit 1; }
fi

echo "      Downloads complete."
echo ""

# Phase 2: Create directory structure
echo "[2/6] Creating directory structure..."
mkdir -p ../data/source
mkdir -p ../data/inputs
mkdir -p ../data/results
echo "      Directories created."
echo ""

# Phase 3: Extract archives
echo "[3/6] Extracting archives..."
unzip -o -q data_api.zip -d ../data/source && echo "      Extracted data_api.zip"
unzip -o -q data_db.zip -d ../data/source && echo "      Extracted data_db.zip"
unzip -o -q ground_truth.zip -d ../data && echo "      Extracted ground_truth.zip"
echo "      Extraction complete."
echo ""

# Phase 4: Start Docker containers
echo "[4/6] Starting Docker containers..."
cd ./docker

# Check if docker-compose is available
if command -v docker-compose &> /dev/null; then
    docker-compose up -d
elif command -v docker &> /dev/null && docker compose version &> /dev/null; then
    docker compose up -d
else
    echo "ERROR: docker-compose or 'docker compose' not found"
    exit 1
fi

echo "      Waiting for containers to be healthy..."
sleep 10  # Give containers time to initialize

# Verify containers are running
if ! docker ps | grep -q "elt-postgres"; then
    echo "WARNING: elt-postgres container may not be running"
fi
if ! docker ps | grep -q "elt-mongodb"; then
    echo "WARNING: elt-mongodb container may not be running"
fi
if ! docker ps | grep -q "elt-api"; then
    echo "WARNING: elt-api container may not be running"
fi
if ! docker ps | grep -q "elt-localstack"; then
    echo "WARNING: elt-localstack container may not be running"
fi

echo "      Docker containers started."
echo ""

# Phase 5: Connect Airbyte to network and populate databases
echo "[5/6] Connecting Airbyte and populating source databases..."
docker network connect docker_elt_network airbyte-abctl-control-plane 2>/dev/null || echo "      Note: Airbyte network connection skipped (may already be connected or Airbyte not running)"

cd ..

echo "      Loading data into source databases..."
python loaders/load_all.py

echo "      Database population complete."
echo ""

# Phase 6: Generate agent workspaces
echo "[6/6] Generating agent workspaces..."
python write_config.py
echo "      Agent workspaces created in data/inputs/"
echo ""

# Cleanup
echo "Cleaning up downloaded archives..."
rm -f data_api.zip data_db.zip ground_truth.zip
echo ""

echo "=============================================="
echo "  Setup Complete!"
echo "=============================================="
echo ""
echo "Next steps:"
echo "  1. Verify Docker containers: docker ps"
echo "  2. Agent workspace is ready in: data/inputs/"
echo "  3. Run agent from the agents/ directory"
echo ""
echo "To verify database connectivity:"
echo "  PostgreSQL:"
echo "    >> docker exec -it elt-postgres psql -U postgres"
echo "    >> \l              (list all databases, press q to quit)"
echo "    >> \c <db_name>    (connect to a db, e.g. \c address)"
echo "    >> \dt <db_name>   (list tables inside the db, e.g. \dt address)"
echo "  MongoDB:    docker exec -it elt-mongodb mongosh --eval 'show dbs'"
echo "  REST API:   curl http://localhost:5005/health"
echo ""
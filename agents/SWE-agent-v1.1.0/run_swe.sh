TABLES_DIR="../../tasks"
table_names=($(ls "$TABLES_DIR" | head -n 100))
echo $table_names

for table_name in "${table_names[@]}"; do
    # Remove file extensions if needed
    table_name=$(basename "$table_name" | cut -d. -f1)
    echo "Processing table: $table_name"
    before=$(docker ps -a --format "{{.Names}}")

    # Copy input files for the current table
    rm -rf ./workspace
    mkdir ./workspace
    cp -r ../../data/inputs/"$table_name"/* ./workspace/
    rm ./workspace/snowflake_credential.json
    
    # Initialize git so SWE-agent v1.1.0 is happy
    cd ./workspace
    git init
    git add .
    git commit -m "Initialize workspace for SWE-agent"
    cd -

    # Run initialization script
    python create_snowflake_db.py --db "$table_name"

    # Run SWE-Agent for gpt-4o or Claude-3.5-Sonnet
    # sweagent run  --env.repo.path=./workspace --config config/elt_fc.yaml --problem_statement.id="$table_name"
    # Run SWE-Agent for open-source models, change model names in ./config/elt_ta.yaml
    sweagent run  --env.repo.path=./workspace --config config/elt_fc_claude45.yaml --problem_statement.id="$table_name"

    # Create output directory and move processed files
    rm -rf ./outputs/"$table_name"
    mkdir -p ./outputs/"$table_name"
    # Find the container created by swe-agent (name starts with elt-bench-env)
    new_container=$(docker ps -a --format "{{.Names}}" | grep "^elt-bench-env" | head -1)
    echo "Found container: $new_container"
    if [ -n "$new_container" ]; then
        docker cp "$new_container":/workspace/. ./outputs/"$table_name" 
        echo "Removing container: $new_container"
        docker rm "$new_container"
    else
        echo "Warning: No elt-bench-env container found to copy from"
    fi
done


TABLES_DIR="../../elt-bench"
table_names=($(ls "$TABLES_DIR" | head -n 100))

for table_name in "${table_names[@]}"; do
    # Remove file extensions if needed
    table_name=$(basename "$table_name" | cut -d. -f1)
    echo "Processing table: $table_name"
    before=$(docker ps -a --format "{{.Names}}")
    # Copy input files for the current table
    rm -rf ./workspace
    mkdir ./workspace
    cp -r ../../inputs/"$table_name"/* ./workspace/
    rm ./workspace/snowflake_credential.json
    # Run initialization script
    python create_snowflake_db.py --db "$table_name"

    # Run SWE-Agent for gpt-4o or Claude-3.5-Sonnet
    sweagent run  --env.repo.path=./workspace --config config/elt_fc.yaml --problem_statement.id="$table_name"  --agent.model.per_instance_cost_limit 6.0 --agent.model.name=claude-3-5-sonnet-20241022
    # Run SWE-Agent for open-source models, change model names in ./config/elt_ta.yaml
    # sweagent run  --env.repo.path=./workspace --config config/elt_ta.yaml --problem_statement.id="$table_name"  --agent.model.per_instance_cost_limit 6.0
   
    # Create output directory and move processed files
    rm -rf ./outputs/"$table_name"
    mkdir -p ./outputs/"$table_name"
    mv ./workspace/* ./outputs/"$table_name"
    after=$(docker ps -a --format "{{.Names}}")
    new_container=$(comm -13 <(echo "$before" | sort) <(echo "$after" | sort))
    echo "Newly added container: $new_container"
    docker cp "$new_container":/workspace ./outputs/"$table_name"
done


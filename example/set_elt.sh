
#!/bin/bash

# List of databases

python write_gt.py

DATABASES=('retails')
# Loop through each database
for DB_NAME in "${DATABASES[@]}"; do
    # Run the Python configuration script
    # rm -r ./$DB_NAME
    python create_snowflake_db.py --db "$DB_NAME"

    cd "$DB_NAME" || { echo "Directory not found: $DB_NAME"; exit 1; }

    # Initialize and apply Terraform
    terraform init
    terraform apply -auto-approve

    # Go back to the parent directory
    cd ..

    # Trigger the sync script
    python trigger_sync.py --db "$DB_NAME"

    echo "Completed processing for database: $DB_NAME"
    echo "-----------------------------------------"
done
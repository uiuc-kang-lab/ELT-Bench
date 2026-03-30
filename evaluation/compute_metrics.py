import re
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--folder", type=str, required=True, help='Specify the folder name where you stored the results.')
args = parser.parse_args()

EL_FILE = f"../data/results/{args.folder}/stage1.log"
T_FILE = f"../data/results/{args.folder}/stage2.log"
TOTAL_TASKS = 100
TOTAL_TABLES = 203

with open(EL_FILE, "r") as file:
    lines = [line.strip() for line in file if line.strip()]

# SRDEL
success_count = 0
unmatched_not_empty_count = 0
error_count = 0

for line in lines:
    if line.startswith("Success"):
        success_count += 1

# SRDT
with open(T_FILE, 'r') as f:
    content = f.read()

# Split on "Database:" or "Table:" to process each block
lines = content.split('\n')

valid_count = 0
total_tables = 0
total_matched_columns = 0
total_unmatched_columns = 0
current_database = ''
current_table = ''
matched = None
unmatched = None
missed = None

# Track per-database table validity for "perfect databases" metric
# {db_name: [is_valid_bool, ...]}
db_table_validity = {}

for line in lines:
    line = line.strip()
    
    if line.startswith('Database:'):
        current_database = line.replace('Database:', '').strip()
    elif line.startswith('Table:'):
        # Process previous table if exists
        if current_table:
            total_tables += 1  # Increment total table count for any table

            is_valid = False
            # Only count as valid if it has the standard format and meets criteria
            if matched is not None and unmatched is not None and missed is not None:
                if len(matched) > 0 and len(unmatched) == 0 and len(missed) == 0:
                    valid_count += 1
                    is_valid = True

            # Track validity per database
            if current_database not in db_table_validity:
                db_table_validity[current_database] = []
            db_table_validity[current_database].append(is_valid)

            # Count matched columns
            if matched is not None:
                total_matched_columns += len(matched)

            # Count unmatched not empty cases
            if unmatched is not None and len(unmatched) > 0:
                unmatched_not_empty_count += 1
                total_unmatched_columns += len(unmatched)
        
        current_table = line.replace('Table:', '').strip()
        matched = None
        unmatched = None
        missed = None
    elif line.startswith('Error:'):
        error_count += 1
    elif line.startswith('Matched columns:'):
        match = re.search(r'Matched columns:\s*\[(.*?)\]', line)
        if match:
            matched = [x.strip().strip("'") for x in match.group(1).split(",") if x.strip()]
    elif line.startswith('Unmatched columns:'):
        match = re.search(r'Unmatched columns:\s*\[(.*?)\]', line)
        if match:
            unmatched = [x.strip().strip("'") for x in match.group(1).split(",") if x.strip()]
    elif line.startswith('Missed:'):
        match = re.search(r'Missed:\s*\[(.*?)\]', line)
        if match:
            missed = [x.strip().strip("'") for x in match.group(1).split(",") if x.strip()]

# Last table
if current_table:
    total_tables += 1  # Increment total table count for last table

    is_valid = False
    # Only count as valid if it has the standard format and meets criteria
    if matched is not None and unmatched is not None and missed is not None:
        if len(matched) > 0 and len(unmatched) == 0 and len(missed) == 0:
            valid_count += 1
            is_valid = True

    # Track validity per database
    if current_database not in db_table_validity:
        db_table_validity[current_database] = []
    db_table_validity[current_database].append(is_valid)

    # Count matched columns for last table
    if matched is not None:
        total_matched_columns += len(matched)

    # Count unmatched not empty cases for last table
    if unmatched is not None and len(unmatched) > 0:
        unmatched_not_empty_count += 1
        total_unmatched_columns += len(unmatched)

# Compute "perfect databases": all tables in the DB are valid
perfect_dbs = sorted([db for db, validities in db_table_validity.items() if all(validities)])
perfect_db_count = len(perfect_dbs)

print(f"\nCorrect data models: {valid_count}")
# E.g. 194 data models because the other 9 were from failed EL tasks.
# However after talking to authors they said we always consider SRDT over 203 and not the count of data models considering only successful ELs
# So the computation of total_tables is unnecessary for SRDT calculation
print(f"Total data models (considering only correctly loaded tasks): {total_tables}")

srdel = (success_count/TOTAL_TASKS) * 100
srdt = (valid_count/TOTAL_TABLES) * 100

print(f"\nSRDEL: {srdel:.2f} % (considering {TOTAL_TASKS} total pipelines)")
print(f"\nSRDT: {srdt:.2f} % (considering {TOTAL_TABLES} total tables)")
print(f"\nTotal matched columns: {total_matched_columns}")
print(f"Tables with unmatched columns: {unmatched_not_empty_count}")
print(f"Total unmatched columns: {total_unmatched_columns}")
print(f"Tables with errors: {error_count}")
print(f"\nDatabases where ALL tables are perfect: {perfect_db_count}")
for db in perfect_dbs:
    print(f"  - {db} ({len(db_table_validity[db])} table(s))")

with open(f'../data/results/{args.folder}/metrics.log', 'a') as f:
    f.write("__" * 40 + "\n")
    f.write(f'SRDEL: {srdel:.2f} % (over {TOTAL_TASKS} tasks)\n')
    f.write(f'SRDT: {srdt:.2f} % (over {TOTAL_TABLES} models)\n')
    f.write(f'Total matched columns: {total_matched_columns}\n')
    f.write(f'Total unmatched columns: {total_unmatched_columns}\n')
    f.write(f'Databases where ALL tables are perfect: {perfect_db_count}\n')
    for db in perfect_dbs:
        f.write(f'  - {db} ({len(db_table_validity[db])} table(s))\n')
    f.write("__" * 40)
    f.write("\n\n")
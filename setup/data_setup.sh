DB_DIR="./sources"
db_names=($(ls "$DB_DIR" | head -n 100))
# db_names=($(ls "$DB_DIR" | tail -n +50 | head -n 50))
cd ./sources
for table_name in "${db_names[@]}"; do
  cd ./$table_name
  bash data.sh $1
  cd ..
  echo "Databases Created: $table_name"
done

python mongo.py --path $1
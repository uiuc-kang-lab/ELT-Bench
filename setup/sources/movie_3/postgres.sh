# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="movie_3"    # Name of the new database
TABLE_NAME="film_actor"
DB_PORT=5433            # Port to connect to PostgreSQL
HOST="localhost"        # Hostname of PostgreSQL server

# Create the database
echo "Creating database '$DB_NAME'..."
PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -c "DROP DATABASE IF EXISTS $DB_NAME;"
PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -c "CREATE DATABASE $DB_NAME;"

# Check if the database was created successfully
if [ $? -eq 0 ]; then
  echo "Database '$DB_NAME' created successfully!"
else
  echo "Failed to create database '$DB_NAME'."
fi

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE $TABLE_NAME
(
  actor_id INTEGER NOT NULL,
  film_id INTEGER NOT NULL,
  last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
  PRIMARY KEY (actor_id, film_id)
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"


PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE film_category
(
  film_id INTEGER NOT NULL,
  category_id INTEGER NOT NULL,
  last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
  PRIMARY KEY (film_id, category_id)
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY film_category FROM '$1/data/$DB_NAME/film_category.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE inventory
(
  inventory_id SERIAL PRIMARY KEY,
  film_id INTEGER NOT NULL,
  store_id INTEGER NOT NULL,
  last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY inventory FROM '$1/data/$DB_NAME/inventory.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE payment
(
  payment_id SERIAL PRIMARY KEY,
  customer_id INTEGER NOT NULL,
  staff_id INTEGER NOT NULL,
  rental_id INTEGER,
  amount REAL NOT NULL,
  payment_date TIMESTAMP NOT NULL,
  last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY payment FROM '$1/data/$DB_NAME/payment.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE rental
(
  rental_id SERIAL PRIMARY KEY,
  rental_date TIMESTAMP NOT NULL,
  inventory_id INTEGER NOT NULL,
  customer_id INTEGER NOT NULL,
  return_date TIMESTAMP,
  staff_id INTEGER NOT NULL,
  last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
  UNIQUE (rental_date, inventory_id, customer_id)
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY rental FROM '$1/data/$DB_NAME/rental.csv' DELIMITER ',' CSV HEADER;"

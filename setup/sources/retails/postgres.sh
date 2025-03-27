# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="retails"    # Name of the new database
TABLE_NAME="lineitem"
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
    l_shipdate      DATE           NULL,
    l_orderkey      INTEGER         NOT NULL,
    l_discount      REAL            NOT NULL,
    l_extendedprice REAL            NOT NULL,
    l_suppkey       INTEGER         NOT NULL,
    l_quantity      INTEGER         NOT NULL,
    l_returnflag    TEXT            NULL,
    l_partkey       INTEGER         NOT NULL,
    l_linestatus    TEXT            NULL,
    l_tax           REAL            NOT NULL,
    l_commitdate    DATE            NULL,
    l_receiptdate   DATE            NULL,
    l_shipmode      TEXT            NULL,
    l_linenumber    INTEGER         NOT NULL,
    l_shipinstruct  TEXT            NULL,
    l_comment       TEXT            NULL,
    PRIMARY KEY (l_orderkey, l_linenumber)
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE orders
(
    o_orderdate     DATE            NULL,
    o_orderkey      INTEGER         NOT NULL PRIMARY KEY,
    o_custkey       INTEGER         NOT NULL,
    o_orderpriority TEXT            NULL,
    o_shippriority  INTEGER         NULL,
    o_clerk         TEXT            NULL,
    o_orderstatus   TEXT            NULL,
    o_totalprice    REAL            NULL,
    o_comment       TEXT            NULL
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY orders FROM '$1/data/$DB_NAME/orders.csv' DELIMITER ',' CSV HEADER;"


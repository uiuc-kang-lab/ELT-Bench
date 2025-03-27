export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION="us-west-2"
export AWS_ENDPOINT_URL=http://localhost:4566

DB_NAME="works-cycles"

aws --endpoint-url=http://localhost:4566 s3 mb s3://$DB_NAME-bucket
aws --endpoint-url=http://localhost:4566 s3 cp $1/data/works_cycles/ContactType.jsonl s3://$DB_NAME-bucket
aws --endpoint-url=http://localhost:4566 s3 cp $1/data/works_cycles/Culture.csv s3://$DB_NAME-bucket
aws --endpoint-url=http://localhost:4566 s3 cp $1/data/works_cycles/Location.jsonl s3://$DB_NAME-bucket
aws --endpoint-url=http://localhost:4566 s3 cp $1/data/works_cycles/PhoneNumberType.jsonl s3://$DB_NAME-bucket
aws --endpoint-url=http://localhost:4566 s3 cp $1/data/works_cycles/SalesTerritory.jsonl s3://$DB_NAME-bucket
aws --endpoint-url=http://localhost:4566 s3 cp $1/data/works_cycles/SalesTerritoryHistory.jsonl s3://$DB_NAME-bucket
aws --endpoint-url=http://localhost:4566 s3 cp $1/data/works_cycles/Shift.csv s3://$DB_NAME-bucket
aws --endpoint-url=http://localhost:4566 s3 cp $1/data/works_cycles/ShipMethod.jsonl s3://$DB_NAME-bucket
aws --endpoint-url=http://localhost:4566 s3 cp $1/data/works_cycles/ShoppingCartItem.csv s3://$DB_NAME-bucket
aws --endpoint-url=http://localhost:4566 s3 cp $1/data/works_cycles/TransactionHistoryArchive.csv s3://$DB_NAME-bucket
aws --endpoint-url=http://localhost:4566 s3 cp $1/data/works_cycles/UnitMeasure.csv s3://$DB_NAME-bucket

bash ./postgres.sh $1
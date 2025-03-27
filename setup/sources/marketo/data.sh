export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION="us-west-2"
export AWS_ENDPOINT_URL=http://localhost:4566

DB_NAME="marketo"

aws --endpoint-url=http://localhost:4566 s3 mb s3://$DB_NAME-bucket
aws --endpoint-url=http://localhost:4566 s3 cp $1/data/marketo/lead.csv s3://$DB_NAME-bucket
aws --endpoint-url=http://localhost:4566 s3 cp $1/data/marketo/lead_describe.jsonl s3://$DB_NAME-bucket


bash ./postgres.sh $1
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION="us-west-2"
export AWS_ENDPOINT_URL=http://localhost:4566

DB_NAME="zuora"

aws --endpoint-url=http://localhost:4566 s3 mb s3://$DB_NAME-bucket
aws --endpoint-url=http://localhost:4566 s3 cp $1/data/zuora/contact.csv s3://$DB_NAME-bucket
aws --endpoint-url=http://localhost:4566 s3 cp $1/data/zuora/product_rate_plan_charge.jsonl s3://$DB_NAME-bucket
aws --endpoint-url=http://localhost:4566 s3 cp $1/data/zuora/rate_plan.csv s3://$DB_NAME-bucket
aws --endpoint-url=http://localhost:4566 s3 cp $1/data/zuora/taxation_item.csv s3://$DB_NAME-bucket
bash ./postgres.sh $1
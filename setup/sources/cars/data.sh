export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION="us-west-2"
export AWS_ENDPOINT_URL=http://localhost:4566


aws --endpoint-url=http://localhost:4566 s3 mb s3://cars-bucket
aws --endpoint-url=http://localhost:4566 s3 cp $1/data/cars/country.jsonl s3://cars-bucket

bash ./postgres.sh $1

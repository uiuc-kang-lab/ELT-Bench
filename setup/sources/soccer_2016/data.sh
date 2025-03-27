export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION="us-west-2"
export AWS_ENDPOINT_URL=http://localhost:4566

DB_NAME="soccer-2016"
aws --endpoint-url=http://localhost:4566 s3 mb s3://$DB_NAME-bucket
aws --endpoint-url=http://localhost:4566 s3 cp $1/data/soccer_2016/City.jsonl s3://$DB_NAME-bucket
aws --endpoint-url=http://localhost:4566 s3 cp $1/data/soccer_2016/Country.parquet s3://$DB_NAME-bucket
aws --endpoint-url=http://localhost:4566 s3 cp $1/data/soccer_2016/Outcome.jsonl s3://$DB_NAME-bucket
aws --endpoint-url=http://localhost:4566 s3 cp $1/data/soccer_2016/Team.jsonl s3://$DB_NAME-bucket
aws --endpoint-url=http://localhost:4566 s3 cp $1/data/soccer_2016/Toss_Decision.parquet s3://$DB_NAME-bucket
aws --endpoint-url=http://localhost:4566 s3 cp $1/data/soccer_2016/Out_Type.csv s3://$DB_NAME-bucket
aws --endpoint-url=http://localhost:4566 s3 cp $1/data/soccer_2016/Umpire.csv s3://$DB_NAME-bucket
aws --endpoint-url=http://localhost:4566 s3 ls s3://$DB_NAME-bucket
bash ./postgres.sh $1
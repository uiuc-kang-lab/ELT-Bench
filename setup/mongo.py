import pandas as pd
from pymongo import MongoClient
import math
import json
import argparse

parser = argparse.ArgumentParser(description="Data path")
parser.add_argument("--path", type=str, default=".", help="Data path")
args = parser.parse_args()

host='localhost'
port=27017

mongo_uri = f"mongodb://{host}:{port}/?directConnection=true&serverSelectionTimeoutMS=2000"
client = MongoClient(mongo_uri)

mongo_dbs = json.load(open('mongo.jsonl'))
for db, tables in mongo_dbs.items():
  client.drop_database(db)
  mg_db = client[db]
  for table in tables:
    df = pd.read_csv(f'{args.path}/data/{db}/{table}.csv')

    df = df.where(pd.notnull(df), None)
    collection = mg_db[table]
    data = df.to_dict(orient='records')
    cleaned_data = []
    for row in data:
      cleaned_data.append({k: v for k, v in row.items() if v is not None and not (isinstance(v, float) and math.isnan(float(v)))})
    collection.insert_many(cleaned_data)
  print(f'{db} inserted successfully')



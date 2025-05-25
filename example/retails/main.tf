terraform {
  required_providers {
    airbyte = {
      source  = "airbytehq/airbyte"
      version = "0.6.5"
    }
  }
}

provider "airbyte" {
  server_url = "http://airbyte-abctl-control-plane:80/api/public/v1/"
  username   = "<username>"
  password   = "<password>"
}

resource "airbyte_source_postgres" "postgres" {
  name          = "Postgres Source"
  workspace_id  = "<workspace_id>"
  definition_id = "decd338e-5647-4c0b-adf4-da0e75f5a750"

  configuration = {
    host     = "elt-postgres"
    port     = 5432
    database = "retails"
    username = "postgres"
    password = "testelt"
    schemas  = ["public"]
  }
}

resource "airbyte_source_mongodb_v2" "mongodb" {
  name          = "MongoDB Source"
  workspace_id  = "<workspace_id>"
  definition_id = "b2e713cd-cc36-4c0a-b5bd-b47cb8a0561e"

  configuration = {
    database_config = {
      self_managed_replica_set = {
        connection_string = "mongodb://elt-mongodb:27017/?directConnection=true"
        database          = "retails"
      }
    }
  }
}

resource "airbyte_source_custom" "custom_api" {
  name          = "Custom API Source"
  workspace_id  = "<workspace_id>"
  definition_id = "<custom_api_definition_id>"

  configuration = jsonencode({})
}

resource "airbyte_source_s3" "aws_s3" {
  name          = "AWS S3 Source"
  workspace_id  = "<workspace_id>"
  definition_id = "69589781-7828-43c5-9f63-8925b1c1ccc2"

  configuration = {
    aws_access_key_id     = "test"
    aws_secret_access_key = "test"
    endpoint              = "http://elt-localstack:4566"
    region_name           = "us-west-2"
    bucket                = "retails-bucket"
    streams = [
      {
        name = "region"
        format = {
          csv_format = {}
        }
        globs = ["region.csv"]
      },
      {
        name = "supplier"
        format = {
          parquet_format = {}
        }
        globs = ["supplier.parquet"]
      }
    ]
  }
}

resource "airbyte_source_file" "jsonl_file_nation" {
  name          = "JSONL File nation"
  workspace_id  = "<workspace_id>"
  definition_id = "778daa7c-feaf-4db6-96f3-70fd645acc77"

  configuration = {
    dataset_name = "nation"
    format       = "jsonl"
    provider = {
      https_public_web = {}
    }
    url = "https://drive.google.com/uc?export=download&id=1bpJheSVxnPfDbWzWtGSgK8y6eQL81PPl"
  }
}

resource "airbyte_destination_snowflake" "snowflake" {
  name          = "Snowflake Destination"
  workspace_id  = "<workspace_id>"
  definition_id = "424892c4-daac-4491-b35d-c6688ba547ba"

  configuration = {
    database  = "retails"
    host      = "<snowflake_host>"
    role      = "AIRBYTE_ROLE"
    schema    = "AIRBYTE_SCHEMA"
    username  = "AIRBYTE_USER"
    warehouse = "AIRBYTE_WAREHOUSE"
    credentials = {
      username_and_password = {
        password = "Snowflake@123"
      }
    }
  }
}

resource "airbyte_connection" "postgres_to_snowflake" {
  name                 = "Postgres to Snowflake"
  source_id            = airbyte_source_postgres.postgres.source_id
  destination_id       = airbyte_destination_snowflake.snowflake.destination_id
  namespace_definition = "destination"
  configurations = {
    streams = [
      {
        name      = "lineitem"
        sync_mode = "full_refresh_append"
      },
      {
        name      = "orders"
        sync_mode = "full_refresh_append"
      }
    ]
  }
}

resource "airbyte_connection" "mongodb_to_snowflake" {
  name                 = "MongoDB to Snowflake"
  source_id            = airbyte_source_mongodb_v2.mongodb.source_id
  destination_id       = airbyte_destination_snowflake.snowflake.destination_id
  namespace_definition = "destination"
  configurations = {
    streams = [
      {
        name      = "customer"
        sync_mode = "full_refresh_append"
      },
      {
        name      = "partsupp"
        sync_mode = "full_refresh_append"
      }
    ]
  }
}

resource "airbyte_connection" "api_to_snowflake" {
  name                 = "API to Snowflake"
  source_id            = airbyte_source_custom.custom_api.source_id
  destination_id       = airbyte_destination_snowflake.snowflake.destination_id
  namespace_definition = "destination"
  configurations = {
    streams = [
      {
        name      = "part"
        sync_mode = "full_refresh_append"
      }
    ]
  }
}

resource "airbyte_connection" "s3_to_snowflake" {
  name                 = "S3 to Snowflake"
  source_id            = airbyte_source_s3.aws_s3.source_id
  destination_id       = airbyte_destination_snowflake.snowflake.destination_id
  namespace_definition = "destination"
  configurations = {
    streams = [
      {
        name      = "region"
        sync_mode = "full_refresh_append"
      },
      {
        name      = "supplier"
        sync_mode = "full_refresh_append"
      }
    ]
  }
}

resource "airbyte_connection" "jsonl_nation_to_snowflake" {
  name                 = "JSONL nation to Snowflake"
  source_id            = airbyte_source_file.jsonl_file_nation.source_id
  destination_id       = airbyte_destination_snowflake.snowflake.destination_id
  namespace_definition = "destination"
  configurations = {
    streams = [
      {
        name      = "nation"
        sync_mode = "full_refresh_append"
      }
    ]
  }
}


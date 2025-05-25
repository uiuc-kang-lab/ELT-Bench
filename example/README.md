# ELT-Bench

## Environment Setup
Please ensure that you have configured the Airbyte credentials in ../setup/airbyte and the Snowflake credentials in ../setup/destination.

``` bash
bash install.sh
```

### RUN Airbyte
``` bash
bash set_elt.sh
```

### Config DBT
``` bash
dbt init retails_dbt
```

configure ~/.dbt/profile.yml 
```
retails_dbt:
  outputs:
    dev:
      type: snowflake
      account: 
      user: AIRBYTE_USER
      password: Snowflake@123
      role: AIRBYTE_ROLE
      database: retails
      warehouse: AIRBYTE_WAREHOUSE
      schema: AIRBYTE_SCHEMA
      threads: 4
  target: dev
```

### RUN DBT
Move the ground truth transformation queries into `models` folder, then run `dbt run`
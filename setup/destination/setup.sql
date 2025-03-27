set airbyte_role = 'AIRBYTE_ROLE';
set airbyte_username = 'AIRBYTE_USER' ;
set airbyte_warehouse = 'AIRBYTE_WAREHOUSE' ;
set airbyte_schema = 'AIRBYTE_SCHEMA' ;

set airbyte_password ='Snowflake@123';

begin;

use role securityadmin;
create role if not exists identifier($airbyte_role);
grant role identifier ($airbyte_role) to role SYSADMIN;

create user if not exists identifier($airbyte_username)
password = $airbyte_password
default_role = $airbyte_role
default_warehouse = $airbyte_warehouse;
grant role identifier($airbyte_role) to user identifier($airbyte_username);

use role sysadmin;

create warehouse if not exists identifier($airbyte_warehouse)
warehouse_size = xsmall
warehouse_type = standard
auto_suspend=60
auto_resume=true
initially_suspended = true;


grant USAGE 
on warehouse identifier($airbyte_warehouse)
to role identifier($airbyte_role);


commit;

begin;
# Authentication

The Databricks SQL Connector for Python supports the following Databricks authentication types:

- Databricks personal access token authentication
- OAuth machine-to-machine (M2M) authentication
- OAuth user-to-machine (U2M) authentication

## Databricks personal access token authentication

To use the Databricks SQL Connector for Python with Databricks personal access token authentication, you must first create a Databricks personal access token. To do so, follow the steps in [Create personal access tokens for workspace users](https://docs.databricks.com/en/dev-tools/auth/pat.html).

To authenticate the Databricks SQL Connector for Python, use the following code snippet. This snippet assumes that you have set the following environment variables:

- `DATABRICKS_SERVER_HOSTNAME` set to the Server Hostname value for your all-purpose compute or SQL warehouse.
- `DATABRICKS_HTTP_PATH` set to the HTTP Path value for your all-purpose compute or SQL warehouse.
- `DATABRICKS_TOKEN` set to the Databricks personal access token.

To set environment variables, see your operating system's documentation.

```python
from databricks import sql
import os

with sql.connect(server_hostname = os.getenv("DATABRICKS_SERVER_HOSTNAME"),
                 http_path       = os.getenv("DATABRICKS_HTTP_PATH"),
                 access_token    = os.getenv("DATABRICKS_TOKEN")) as connection:
  # ...
```

## OAuth machine-to-machine (M2M) authentication

Databricks SQL Connector for Python versions 2.5.0 and above support OAuth machine-to-machine (M2M) authentication. You must also install the Databricks SDK for Python (for example by running `pip install databricks-sdk` or `python -m pip install databricks-sdk`).

To use the Databricks SQL Connector for Python with OAuth M2M authentication, you must do the following:

1. Create a Databricks service principal in your Databricks workspace, and create an OAuth secret for that service principal.

   To create the service principal and its OAuth secret, see [Authorize service principal access to Databricks with OAuth](https://docs.databricks.com/en/dev-tools/auth/oauth-m2m.html). Make a note of the service principal's **UUID** or **Application ID** value, and the **Secret** value for the service principal's OAuth secret.

2. Give that service principal access to your all-purpose compute or warehouse.

   To give the service principal access to your all-purpose compute or warehouse, see [Compute permissions](https://docs.databricks.com/en/compute/manage.html#compute-permissions) or [Manage a SQL warehouse](https://docs.databricks.com/en/compute/sql-warehouse/warehouse-manage.html).

To authenticate the Databricks SQL Connector for Python, use the following code snippet. This snippet assumes that you have set the following environment variables:

- `DATABRICKS_SERVER_HOSTNAME` set to the Server Hostname value for your all-purpose compute or SQL warehouse.
- `DATABRICKS_HTTP_PATH` set to the HTTP Path value for your all-purpose compute or SQL warehouse.
- `DATABRICKS_CLIENT_ID` set to the service principal's UUID or Application ID value.
- `DATABRICKS_CLIENT_SECRET` set to the Secret value for the service principal's OAuth secret.

To set environment variables, see your operating system's documentation.

```python
from databricks.sdk.core import Config, oauth_service_principal
from databricks import sql
import os

server_hostname = os.getenv("DATABRICKS_SERVER_HOSTNAME")

def credential_provider():
  config = Config(
    host          = f"https://{server_hostname}",
    client_id     = os.getenv("DATABRICKS_CLIENT_ID"),
    client_secret = os.getenv("DATABRICKS_CLIENT_SECRET"))
  return oauth_service_principal(config)

with sql.connect(server_hostname      = server_hostname,
                 http_path            = os.getenv("DATABRICKS_HTTP_PATH"),
                 credentials_provider = credential_provider) as connection:
  # ...
```

## OAuth user-to-machine (U2M) authentication

Databricks SQL Connector for Python versions 2.1.0 and above support OAuth user-to-machine (U2M) authentication.

To authenticate the Databricks SQL Connector for Python with OAuth U2M authentication, use the following code snippet. OAuth U2M authentication uses real-time human sign-in and consent to authenticate the target Databricks user account. This snippet assumes that you have set the following environment variables:

- Set `DATABRICKS_SERVER_HOSTNAME` to the Server Hostname value for your all-purpose compute or SQL warehouse.
- Set `DATABRICKS_HTTP_PATH` to the HTTP Path value for your all-purpose compute or SQL warehouse.

To set environment variables, see your operating system's documentation.

```python
from databricks import sql
import os

with sql.connect(server_hostname = os.getenv("DATABRICKS_SERVER_HOSTNAME"),
                 http_path       = os.getenv("DATABRICKS_HTTP_PATH"),
                 auth_type       = "databricks-oauth") as connection:
  # ...
```

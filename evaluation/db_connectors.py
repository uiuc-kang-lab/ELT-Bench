"""Database access layer for the ELT-Bench evaluators.

Separates all warehouse-specific content (connections, information_schema
queries, identifier-case conventions, table fetches) from the evaluation
logic in eva_stage1.py / eva_stage2_new.py.

Supported backends: snowflake, databricks, redshift.

    from db_connectors import get_connector
    conn = get_connector("databricks", read_json("databricks_credential.json"))
    conn.verify_schema("elt_claude_v5", "apple_store")
    conn.list_tables("elt_claude_v5", "apple_store")
    conn.table_size("elt_claude_v5", "apple_store", "app")
    df = conn.fetch_table("elt_claude_v5", "apple_store", "app")
    conn.close()

Credential JSON formats
-----------------------
snowflake : kwargs for snowflake.connector.connect
            {"account":..., "user":..., "password":..., "role":..., "warehouse":...}
databricks: {"hostname":..., "http_path":..., "client_id":..., "secret":...,
             "database": "<default catalog, optional>"}
redshift  : kwargs for redshift_connector.connect (or psycopg2)
            {"host":..., "port":..., "database":..., "user":..., "password":...}
"""

import re

import pandas as pd


_RELATION_PATTERN = re.compile(
    r"\b(FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)",
    flags=re.IGNORECASE,
)


class BaseConnector:
    """Uniform interface the evaluators code against."""

    def __init__(self, config: dict):
        self.config = dict(config)
        self._conn = None

    # -- to implement per backend -------------------------------------------
    def _connect(self):
        raise NotImplementedError

    def _quote(self, ident: str) -> str:
        raise NotImplementedError

    def _norm(self, ident: str) -> str:
        """Fold an identifier to the backend's canonical case for comparison."""
        raise NotImplementedError

    def _schemata_sql(self, database: str) -> str:
        raise NotImplementedError

    def _tables_sql(self, database: str, schema: str) -> str:
        raise NotImplementedError

    # -- shared plumbing ------------------------------------------------------
    def conn(self):
        if self._conn is None:
            self._conn = self._connect()
        return self._conn

    def close(self):
        if self._conn is not None:
            try:
                self._conn.close()
            finally:
                self._conn = None

    def query(self, sql: str) -> pd.DataFrame:
        cur = self.conn().cursor()
        try:
            cur.execute(sql)
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
        finally:
            cur.close()
        return pd.DataFrame(rows, columns=cols)

    def prepare_evaluation_sql(self, sql: str, database: str) -> str:
        """Map logical ``schema.table`` references to a warehouse layout."""
        return sql

    def query_evaluation_sql(self, sql: str, database: str) -> pd.DataFrame:
        return self.query(self.prepare_evaluation_sql(sql, database))

    @staticmethod
    def _rewrite_relations(sql: str, qualify) -> str:
        def replace(match):
            keyword, schema, table = match.groups()
            return f"{keyword} {qualify(schema, table)}"

        return _RELATION_PATTERN.sub(replace, sql)

    def _fqn(self, database: str, schema: str, table: str) -> str:
        return f"{self._quote(database)}.{self._quote(schema)}.{self._quote(table)}"

    # -- operations used by the evaluators ------------------------------------
    def verify_schema(self, database: str, schema: str) -> bool:
        df = self.query(self._schemata_sql(database))
        names = {self._norm(x) for x in df.iloc[:, 0].astype(str)}
        return self._norm(schema) in names

    def list_tables(self, database: str, schema: str) -> list:
        """Table names in the schema, in the backend's native case."""
        df = self.query(self._tables_sql(database, schema))
        return [str(x) for x in df.iloc[:, 0]]

    def table_size(self, database: str, schema: str, table: str) -> int:
        df = self.query(f"SELECT COUNT(*) FROM {self._fqn(database, schema, table)}")
        return int(df.iloc[0, 0])

    def fetch_table(self, database: str, schema: str, table: str) -> pd.DataFrame:
        return self.query(f"SELECT * FROM {self._fqn(database, schema, table)}")


class SnowflakeConnector(BaseConnector):
    """Snowflake adapter for the current benchmark layout.

    Each logical task schema is stored as its own Snowflake database, with
    source and model tables under AIRBYTE_SCHEMA.
    """

    def _connect(self):
        import snowflake.connector
        return snowflake.connector.connect(**self.config)

    def _quote(self, ident: str) -> str:
        return ident  # rely on Snowflake's case-insensitive unquoted resolution

    def _norm(self, ident: str) -> str:
        return ident.upper()

    def verify_schema(self, database: str, schema: str) -> bool:
        df = self.query(
            f"SELECT schema_name FROM {schema}.information_schema.schemata"
        )
        names = {self._norm(x) for x in df.iloc[:, 0].astype(str)}
        return "AIRBYTE_SCHEMA" in names

    def list_tables(self, database: str, schema: str) -> list:
        df = self.query(
            f"SELECT table_name FROM {schema}.information_schema.tables "
            "WHERE table_schema = 'AIRBYTE_SCHEMA' "
            "AND table_type = 'BASE TABLE'"
        )
        return [str(x) for x in df.iloc[:, 0]]

    def _fqn(self, database: str, schema: str, table: str) -> str:
        return f"{schema}.AIRBYTE_SCHEMA.{table}"

    def prepare_evaluation_sql(self, sql: str, database: str) -> str:
        return self._rewrite_relations(
            sql,
            lambda schema, table: f"{schema}.AIRBYTE_SCHEMA.{table}",
        )

    def _schemata_sql(self, database: str) -> str:
        return f"SELECT schema_name FROM {database}.information_schema.schemata"

    def _tables_sql(self, database: str, schema: str) -> str:
        return (f"SELECT table_name FROM {database}.information_schema.tables "
                f"WHERE table_schema = '{schema.upper()}' AND table_type = 'BASE TABLE'")


class DatabricksConnector(BaseConnector):
    """Databricks SQL warehouse (Unity Catalog): identifiers fold to lowercase.

    Auth: OAuth machine-to-machine via service-principal client_id + secret.
    """

    def _connect(self):
        from databricks import sql as dbsql
        from databricks.sdk.core import Config, oauth_service_principal
        hostname = self.config["hostname"]
        cfg = Config(
            host=f"https://{hostname}",
            client_id=self.config["client_id"],
            client_secret=self.config["secret"],
        )
        return dbsql.connect(
            server_hostname=hostname,
            http_path=self.config["http_path"],
            credentials_provider=lambda: oauth_service_principal(cfg),
        )

    def _quote(self, ident: str) -> str:
        return f"`{ident}`"

    def _norm(self, ident: str) -> str:
        return ident.lower()

    def prepare_evaluation_sql(self, sql: str, database: str) -> str:
        return self._rewrite_relations(
            sql,
            lambda schema, table: (
                f"{self._quote(database)}."
                f"{self._quote(schema)}."
                f"{self._quote(table)}"
            ),
        )

    def _schemata_sql(self, database: str) -> str:
        return f"SELECT schema_name FROM {self._quote(database)}.information_schema.schemata"

    def _tables_sql(self, database: str, schema: str) -> str:
        # Unity Catalog table_type values: MANAGED / EXTERNAL / VIEW / ...
        return (f"SELECT table_name FROM {self._quote(database)}.information_schema.tables "
                f"WHERE table_schema = '{schema.lower()}' "
                f"AND table_type IN ('MANAGED', 'EXTERNAL')")


class RedshiftConnector(BaseConnector):
    """Redshift: identifiers fold to lowercase; connection is per-database,
    so the `database` argument is ignored in queries (must match the
    database in the credential)."""

    def _connect(self):
        config = {
            key: self.config[key]
            for key in ("host", "port", "database", "user", "password")
            if key in self.config
        }
        if "user" not in config:
            config["user"] = self.config["username"]
        try:
            import redshift_connector
            return redshift_connector.connect(**config)
        except ImportError:
            import psycopg2
            return psycopg2.connect(**config)

    def _quote(self, ident: str) -> str:
        return f'"{ident.lower()}"'

    def _norm(self, ident: str) -> str:
        return ident.lower()

    def _fqn(self, database: str, schema: str, table: str) -> str:
        # cross-database qualification is not used; schema.table only
        return f"{self._quote(schema)}.{self._quote(table)}"

    def _schemata_sql(self, database: str) -> str:
        return "SELECT schema_name FROM information_schema.schemata"

    def _tables_sql(self, database: str, schema: str) -> str:
        return (f"SELECT table_name FROM information_schema.tables "
                f"WHERE table_schema = '{schema.lower()}' AND table_type = 'BASE TABLE'")


_CONNECTORS = {
    "snowflake": SnowflakeConnector,
    "databricks": DatabricksConnector,
    "redshift": RedshiftConnector,
}


def get_connector(db_type: str, config: dict) -> BaseConnector:
    try:
        cls = _CONNECTORS[db_type.lower()]
    except KeyError:
        raise ValueError(f"unknown db_type {db_type!r}; expected one of {sorted(_CONNECTORS)}")
    return cls(config)

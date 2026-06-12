-- Schema definitions for retails
-- Auto-extracted from sources/retails/postgres.sh

-- Table: lineitem
CREATE TABLE IF NOT EXISTS lineitem (
    l_shipdate      DATE           NULL,
    l_orderkey      INTEGER         NOT NULL,
    l_discount      REAL            NOT NULL,
    l_extendedprice REAL            NOT NULL,
    l_suppkey       INTEGER         NOT NULL,
    l_quantity      INTEGER         NOT NULL,
    l_returnflag    TEXT            NULL,
    l_partkey       INTEGER         NOT NULL,
    l_linestatus    TEXT            NULL,
    l_tax           REAL            NOT NULL,
    l_commitdate    DATE            NULL,
    l_receiptdate   DATE            NULL,
    l_shipmode      TEXT            NULL,
    l_linenumber    INTEGER         NOT NULL,
    l_shipinstruct  TEXT            NULL,
    l_comment       TEXT            NULL,
    PRIMARY KEY (l_orderkey, l_linenumber)
);

-- Table: orders
CREATE TABLE IF NOT EXISTS orders (
    o_orderdate     DATE            NULL,
    o_orderkey      INTEGER         NOT NULL PRIMARY KEY,
    o_custkey       INTEGER         NOT NULL,
    o_orderpriority TEXT            NULL,
    o_shippriority  INTEGER         NULL,
    o_clerk         TEXT            NULL,
    o_orderstatus   TEXT            NULL,
    o_totalprice    REAL            NULL,
    o_comment       TEXT            NULL
);


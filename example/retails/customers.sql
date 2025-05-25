WITH orders_cte AS (
  SELECT o_custkey,
    COUNT(*) AS num_orders,
    avg(o_totalprice) AS average_total_price_per_order
  FROM retails.airbyte_schema.orders
  GROUP BY o_custkey
),
has_above_average_account_balance_cte AS (
  SELECT c_custkey
  FROM retails.airbyte_schema.customer
  WHERE c_acctbal > (
      SELECT AVG(c_acctbal)
      FROM retails.airbyte_schema.customer
    )
),
order_date_highest_total_price AS (
  SELECT o_custkey,
    o_orderdate,
    RANK() over(
      PARTITION by o_custkey
      ORDER BY o_totalprice DESC,
        o_orderdate
    ) AS price_rank
  FROM retails.airbyte_schema.orders
),
balance_lower_than_4000_and_in_US_cte AS (
  SELECT DISTINCT c_custkey
  FROM retails.airbyte_schema.customer T1
    JOIN retails.airbyte_schema.nation T2 ON T1.c_nationkey = T2.n_nationkey
  WHERE T1.c_acctbal < 4000
    AND T2.n_name ILIKE 'United States'
)
SELECT T1.c_custkey AS c_custkey,
  T1.c_nationkey AS c_nationkey,
  T1.c_name AS c_name,
  CASE
    WHEN T2.num_orders IS NULL THEN 0
    ELSE T2.num_orders
  END AS num_orders,
  T2.average_total_price_per_order,
  CASE
    WHEN T3.c_custkey IS NULL THEN 0
    ELSE 1
  END AS has_above_average_account_balance,
  T4.o_orderdate AS order_date_highest_total_price,
  CASE
    WHEN T5.c_custkey IS NULL THEN 0
    ELSE 1
  END AS balance_lower_than_4000_and_in_US
FROM retails.airbyte_schema.customer T1
  LEFT JOIN orders_cte T2 ON T1.c_custkey = T2.o_custkey
  LEFT JOIN has_above_average_account_balance_cte T3 ON T1.c_custkey = T3.c_custkey
  LEFT JOIN order_date_highest_total_price T4 ON T1.c_custkey = T4.o_custkey
  AND T4.price_rank = 1
  LEFT JOIN balance_lower_than_4000_and_in_US_cte T5 ON T1.c_custkey = T5.c_custkey
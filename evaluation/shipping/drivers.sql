WITH num_shipments_2017_cte AS (
  SELECT T2.driver_id as driver_id,
    COUNT(*) AS num_shipments_2017
  FROM shipping.airbyte_schema.shipment AS T1
    INNER JOIN shipping.airbyte_schema.driver AS T2 ON T1.driver_id = T2.driver_id
  WHERE Year(T1.ship_date) = 2017
  GROUP BY T2.driver_id
),
least_city_pre AS (
  SELECT city_id
  FROM shipping.airbyte_schema.city
  WHERE population = (
      SELECT min(population)
      FROM shipping.airbyte_schema.city
    )
),
num_shipment_to_least_populated_city AS (
  SELECT driver_id,
    COUNT(ship_id) AS num_shipment_to_least_populated_city
  FROM shipping.airbyte_schema.shipment
  WHERE city_id IN (
      SELECT *
      FROM least_city_pre
    )
  GROUP BY driver_id
),
per_shipment_placed_by_Autoware_Inc_cte AS(
  SELECT T1.driver_id as driver_id,
    CAST(
      SUM(
        CASE
          WHEN T2.cust_name ILIKE 'Autoware Inc' THEN 1
          ELSE 0
        END
      ) AS REAL
    ) * 100 / COUNT(*) AS per
  FROM shipping.airbyte_schema.shipment AS T1
    INNER JOIN shipping.airbyte_schema.customer AS T2 ON T2.cust_id = T1.cust_id
  GROUP BY T1.driver_id
),
has_a_shipment_weight_greater_95_per_avg_across_all_shipments_cte AS (
  SELECT DISTINCT driver_id as driver_id
  FROM shipping.airbyte_schema.shipment
  WHERE weight * 100 > (
      SELECT 95 * AVG(weight)
      FROM shipping.airbyte_schema.shipment
    )
),
weight_first_shipment_cte AS (
  SELECT driver_id,
    weight,
    rank() over(
      PARTITION by driver_id
      ORDER BY ship_date, weight desc
    ) AS date_rank
  FROM shipping.airbyte_schema.shipment
)
SELECT T1.driver_id AS driver_id,
  T1.first_name,
  T1.last_name,
  CASE
    WHEN T2.num_shipments_2017 IS NULL THEN 0
    ELSE T2.num_shipments_2017
  END AS num_shipments_2017,
  CASE
    WHEN T3.num_shipment_to_least_populated_city IS NULL THEN 0
    ELSE T3.num_shipment_to_least_populated_city
  END AS num_shipment_to_least_populated_city,
  T4.per AS per_shipment_placed_by_Autoware_Inc,
  CASE
    WHEN T5.driver_id IS NULL THEN 0
    ELSE 1
  END AS has_a_shipment_weight_greater_95_per_avg_across_all_shipments,
  T6.weight as weight_first_shipment
FROM shipping.airbyte_schema.driver T1
  LEFT JOIN num_shipments_2017_cte T2 ON T1.driver_id = T2.driver_id
  LEFT JOIN num_shipment_to_least_populated_city T3 ON T1.driver_id = T3.driver_id
  LEFT JOIN per_shipment_placed_by_Autoware_Inc_cte T4 ON T1.driver_id = T4.driver_id
  LEFT JOIN has_a_shipment_weight_greater_95_per_avg_across_all_shipments_cte T5 ON T1.driver_id = T5.driver_id
  LEFT JOIN weight_first_shipment_cte T6 ON T1.driver_id = T6.driver_id
  AND T6.date_rank = 1
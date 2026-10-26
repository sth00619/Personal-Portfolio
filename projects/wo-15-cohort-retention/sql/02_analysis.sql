-- All purchase-based metrics use delivered orders and customer_unique_id.
DROP SCHEMA IF EXISTS analytics CASCADE;
CREATE SCHEMA analytics;

CREATE OR REPLACE VIEW analytics.delivered_orders AS
SELECT
    o.order_id,
    o.customer_id,
    c.customer_unique_id,
    NULLIF(o.order_purchase_timestamp, '')::timestamp AS purchase_ts,
    NULLIF(o.order_delivered_customer_date, '')::timestamp AS delivered_ts,
    NULLIF(o.order_estimated_delivery_date, '')::timestamp AS estimated_delivery_ts
FROM raw.orders AS o
JOIN raw.customers AS c USING (customer_id)
WHERE o.order_status = 'delivered'
  AND NULLIF(o.order_purchase_timestamp, '') IS NOT NULL
  AND c.customer_unique_id IS NOT NULL;

CREATE OR REPLACE VIEW analytics.order_value AS
SELECT order_id, SUM(NULLIF(payment_value, '')::numeric) AS paid_value
FROM raw.order_payments
GROUP BY order_id;

CREATE OR REPLACE VIEW analytics.customer_orders AS
SELECT
    d.customer_unique_id,
    d.order_id,
    d.purchase_ts,
    d.delivered_ts,
    d.estimated_delivery_ts,
    COALESCE(v.paid_value, 0)::numeric AS paid_value
FROM analytics.delivered_orders AS d
LEFT JOIN analytics.order_value AS v USING (order_id);

CREATE TABLE analytics.customer_id_effect AS
WITH populations AS (
    SELECT 'all_orders' AS population, o.order_id, o.customer_id, c.customer_unique_id
    FROM raw.orders AS o
    JOIN raw.customers AS c USING (customer_id)
    UNION ALL
    SELECT 'delivered_orders', d.order_id, d.customer_id, d.customer_unique_id
    FROM analytics.delivered_orders AS d
), identifiers AS (
    SELECT population, 'customer_id' AS identifier, customer_id AS customer_key,
           COUNT(DISTINCT order_id) AS orders
    FROM populations
    GROUP BY population, customer_id
    UNION ALL
    SELECT population, 'customer_unique_id', customer_unique_id,
           COUNT(DISTINCT order_id)
    FROM populations
    GROUP BY population, customer_unique_id
)
SELECT
    population,
    identifier,
    COUNT(*) AS customers,
    COUNT(*) FILTER (WHERE orders > 1) AS repeat_customers,
    COUNT(*) FILTER (WHERE orders > 1)::numeric / NULLIF(COUNT(*), 0) AS repeat_rate
FROM identifiers
GROUP BY population, identifier;

CREATE TABLE analytics.cohort_retention AS
WITH first_purchase AS (
    SELECT DISTINCT
        customer_unique_id,
        FIRST_VALUE(purchase_ts) OVER (
            PARTITION BY customer_unique_id ORDER BY purchase_ts, order_id
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ) AS first_purchase_ts
    FROM analytics.customer_orders
), customer_month AS (
    SELECT DISTINCT customer_unique_id, DATE_TRUNC('month', purchase_ts)::date AS purchase_month
    FROM analytics.customer_orders
), customer_cohort AS (
    SELECT customer_unique_id, DATE_TRUNC('month', first_purchase_ts)::date AS cohort_month
    FROM first_purchase
), cohort_sizes AS (
    SELECT cohort_month, COUNT(*) AS cohort_customers
    FROM customer_cohort
    GROUP BY cohort_month
), cohort_activity AS (
    SELECT
        cc.cohort_month,
        cm.purchase_month,
        ((EXTRACT(YEAR FROM cm.purchase_month) - EXTRACT(YEAR FROM cc.cohort_month)) * 12
          + EXTRACT(MONTH FROM cm.purchase_month) - EXTRACT(MONTH FROM cc.cohort_month))::int AS cohort_age,
        COUNT(DISTINCT cc.customer_unique_id) AS active_customers
    FROM customer_cohort AS cc
    JOIN customer_month AS cm USING (customer_unique_id)
    WHERE cm.purchase_month >= cc.cohort_month
    GROUP BY cc.cohort_month, cm.purchase_month
), month_bounds AS (
    SELECT MAX(purchase_month) AS last_month FROM customer_month
), retention_grid AS (
    SELECT
        cs.cohort_month,
        cs.cohort_customers,
        month_spine.purchase_month,
        ((EXTRACT(YEAR FROM month_spine.purchase_month) - EXTRACT(YEAR FROM cs.cohort_month)) * 12
          + EXTRACT(MONTH FROM month_spine.purchase_month) - EXTRACT(MONTH FROM cs.cohort_month))::int AS cohort_age
    FROM cohort_sizes AS cs
    CROSS JOIN month_bounds AS mb
    CROSS JOIN LATERAL GENERATE_SERIES(
        cs.cohort_month::timestamp,
        mb.last_month::timestamp,
        INTERVAL '1 month'
    ) AS month_spine(purchase_month)
)
SELECT
    rg.cohort_month,
    rg.purchase_month,
    rg.cohort_age,
    rg.cohort_customers,
    COALESCE(ca.active_customers, 0) AS active_customers,
    COALESCE(ca.active_customers, 0)::numeric / rg.cohort_customers AS retention_rate
FROM retention_grid AS rg
LEFT JOIN cohort_activity AS ca USING (cohort_month, purchase_month, cohort_age)
ORDER BY rg.cohort_month, rg.cohort_age;

CREATE TABLE analytics.monthly_metric_tree AS
WITH monthly AS (
    SELECT
        DATE_TRUNC('month', purchase_ts)::date AS purchase_month,
        COUNT(DISTINCT customer_unique_id) AS customers,
        COUNT(DISTINCT order_id) AS delivered_orders,
        SUM(paid_value) AS revenue
    FROM analytics.customer_orders
    GROUP BY 1
), components AS (
    SELECT
        purchase_month,
        customers,
        delivered_orders,
        revenue,
        delivered_orders::numeric / NULLIF(customers, 0) AS orders_per_customer,
        revenue / NULLIF(delivered_orders, 0) AS average_order_value
    FROM monthly
)
SELECT
    *,
    LAG(purchase_month) OVER (ORDER BY purchase_month) AS previous_month,
    LAG(revenue) OVER (ORDER BY purchase_month) AS previous_revenue,
    revenue / NULLIF(LAG(revenue) OVER (ORDER BY purchase_month), 0) - 1 AS revenue_change_rate,
    LAG(customers) OVER (ORDER BY purchase_month) AS previous_customers,
    LAG(orders_per_customer) OVER (ORDER BY purchase_month) AS previous_orders_per_customer,
    LAG(average_order_value) OVER (ORDER BY purchase_month) AS previous_average_order_value
FROM components
ORDER BY purchase_month;

CREATE TABLE analytics.rfm_customer AS
WITH metrics AS (
    SELECT
        customer_unique_id,
        MAX(purchase_ts)::date AS last_purchase_date,
        COUNT(DISTINCT order_id)::int AS frequency,
        SUM(paid_value)::numeric AS monetary
    FROM analytics.customer_orders
    GROUP BY customer_unique_id
), anchor AS (
    SELECT MAX(purchase_ts)::date + 1 AS observation_date
    FROM analytics.customer_orders
), scored AS (
    SELECT
        m.customer_unique_id,
        (a.observation_date - m.last_purchase_date)::int AS recency_days,
        m.frequency,
        m.monetary,
        NTILE(5) OVER (ORDER BY a.observation_date - m.last_purchase_date DESC) AS r_score,
        CASE WHEN m.frequency = 1 THEN 1 ELSE 5 END AS f_score,
        NTILE(5) OVER (ORDER BY m.monetary ASC) AS m_score
    FROM metrics AS m
    CROSS JOIN anchor AS a
)
SELECT
    *,
    r_score::text || f_score::text || m_score::text AS rfm_segment
FROM scored;

CREATE TABLE analytics.rfm_profile AS
SELECT
    rfm_segment,
    r_score,
    f_score,
    m_score,
    COUNT(*) AS customers,
    AVG(recency_days)::numeric(12,2) AS average_recency_days,
    AVG(frequency)::numeric(12,3) AS average_frequency,
    AVG(monetary)::numeric(14,2) AS average_monetary,
    COUNT(*) FILTER (WHERE frequency > 1)::numeric / COUNT(*) AS repeat_rate
FROM analytics.rfm_customer
GROUP BY rfm_segment, r_score, f_score, m_score
ORDER BY customers DESC;

CREATE TABLE analytics.survival AS
WITH ordered AS (
    SELECT
        customer_unique_id,
        purchase_ts,
        ROW_NUMBER() OVER (PARTITION BY customer_unique_id ORDER BY purchase_ts, order_id) AS purchase_number
    FROM analytics.customer_orders
), first_second AS (
    SELECT
        customer_unique_id,
        MIN(purchase_ts) FILTER (WHERE purchase_number = 1) AS first_purchase,
        MIN(purchase_ts) FILTER (WHERE purchase_number = 2) AS second_purchase
    FROM ordered
    GROUP BY customer_unique_id
), observation AS (
    SELECT MAX(purchase_ts) AS last_observed_purchase
    FROM analytics.customer_orders
)
SELECT
    fs.customer_unique_id,
    GREATEST(
        1,
        COALESCE(fs.second_purchase::date, o.last_observed_purchase::date) - fs.first_purchase::date
    )::int AS duration_days,
    (fs.second_purchase IS NOT NULL) AS repurchased
FROM first_second AS fs
CROSS JOIN observation AS o;

CREATE TABLE analytics.first_order_experience AS
WITH first_orders AS (
    SELECT DISTINCT ON (customer_unique_id)
        customer_unique_id, order_id, purchase_ts, delivered_ts, estimated_delivery_ts
    FROM analytics.customer_orders
    ORDER BY customer_unique_id, purchase_ts, order_id
), customer_repeat AS (
    SELECT customer_unique_id, COUNT(DISTINCT order_id) > 1 AS repurchased
    FROM analytics.customer_orders
    GROUP BY customer_unique_id
), review_by_order AS (
    SELECT order_id, AVG(NULLIF(review_score, '')::numeric) AS review_score
    FROM raw.order_reviews
    GROUP BY order_id
)
SELECT
    f.customer_unique_id,
    r.repurchased,
    v.review_score,
    (f.delivered_ts > f.estimated_delivery_ts) AS delivery_delayed
FROM first_orders AS f
JOIN customer_repeat AS r USING (customer_unique_id)
LEFT JOIN review_by_order AS v USING (order_id)
WHERE f.delivered_ts IS NOT NULL
  AND f.estimated_delivery_ts IS NOT NULL;

CREATE TABLE analytics.category_repeat_profile AS
WITH item_category AS (
    SELECT
        d.customer_unique_id,
        d.order_id,
        d.purchase_ts,
        COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS category,
        SUM(NULLIF(i.price, '')::numeric) AS category_value
    FROM analytics.delivered_orders AS d
    JOIN raw.order_items AS i USING (order_id)
    JOIN raw.products AS p USING (product_id)
    LEFT JOIN raw.category_translation AS t USING (product_category_name)
    GROUP BY d.customer_unique_id, d.order_id, d.purchase_ts,
             COALESCE(t.product_category_name_english, p.product_category_name, 'unknown')
), first_category AS (
    SELECT DISTINCT ON (customer_unique_id)
        customer_unique_id, category
    FROM item_category
    ORDER BY customer_unique_id, purchase_ts, category_value DESC, category
), customer_repeat AS (
    SELECT customer_unique_id, COUNT(DISTINCT order_id) > 1 AS repurchased
    FROM analytics.customer_orders
    GROUP BY customer_unique_id
)
SELECT
    fc.category,
    COUNT(*) AS customers,
    COUNT(*) FILTER (WHERE cr.repurchased) AS repeat_customers,
    COUNT(*) FILTER (WHERE cr.repurchased)::numeric / COUNT(*) AS repeat_rate
FROM first_category AS fc
JOIN customer_repeat AS cr USING (customer_unique_id)
GROUP BY fc.category
HAVING COUNT(*) >= 200
ORDER BY repeat_rate DESC, customers DESC;


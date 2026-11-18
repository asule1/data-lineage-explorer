-- Sample warehouse ETL: raw -> staging -> core -> marts

CREATE TABLE staging.customers AS
SELECT id AS customer_id, lower(email) AS email, country, created_at
FROM raw.crm_customers
WHERE deleted_at IS NULL;

CREATE TABLE staging.orders AS
SELECT o.order_id, o.customer_id, o.order_ts, o.status
FROM raw.shop_orders o;

CREATE TABLE staging.order_items AS
SELECT i.order_id, i.product_id, i.quantity, p.unit_price
FROM raw.shop_order_items i
JOIN raw.product_catalog p ON p.product_id = i.product_id;

INSERT INTO core.fact_sales
WITH line_totals AS (
    SELECT order_id, SUM(quantity * unit_price) AS order_total
    FROM staging.order_items
    GROUP BY order_id
)
SELECT o.order_id, o.customer_id, o.order_ts, lt.order_total
FROM staging.orders o
JOIN line_totals lt ON lt.order_id = o.order_id
WHERE o.status = 'completed';

CREATE TABLE core.dim_customer AS
SELECT c.customer_id, c.email, c.country, MIN(f.order_ts) AS first_order_ts
FROM staging.customers c
LEFT JOIN core.fact_sales f ON f.customer_id = c.customer_id
GROUP BY c.customer_id, c.email, c.country;

CREATE VIEW marts.revenue_by_country AS
SELECT d.country, DATE_TRUNC('month', f.order_ts) AS month, SUM(f.order_total) AS revenue
FROM core.fact_sales f
JOIN core.dim_customer d ON d.customer_id = f.customer_id
GROUP BY 1, 2;

CREATE VIEW marts.customer_ltv AS
SELECT customer_id, SUM(order_total) AS lifetime_value, COUNT(*) AS orders
FROM core.fact_sales
GROUP BY customer_id;

INSERT INTO reporting.exec_dashboard
SELECT r.month, SUM(r.revenue) AS total_revenue, AVG(l.lifetime_value) AS avg_ltv
FROM marts.revenue_by_country r
CROSS JOIN marts.customer_ltv l
GROUP BY r.month;

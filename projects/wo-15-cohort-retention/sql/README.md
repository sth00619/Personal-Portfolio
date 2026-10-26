# SQL query guide

Run in order using `docker compose exec -T db psql -U olist -d olist -f /sql/01_load.sql` and then `docker compose exec -T db psql -U olist -d olist -f /sql/02_analysis.sql`.

`02_analysis.sql` contains the complete analytical SQL: delivered-order attribution, repeat-rate identifier audit, first-purchase cohorts, monthly retention, monthly revenue metric tree with `LAG()`, tied-frequency-aware RFM scores, first-to-second-purchase survival observations, and first-order experience joins.


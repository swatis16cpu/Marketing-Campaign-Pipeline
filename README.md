# Marketing Campaign Data Pipeline

A Python + SQL pipeline that ingests marketing campaign event files (modelled on an SFMC-style email/SMS/push export), applies automated data quality checks, transforms the data into reporting tables, and loads it to a warehouse (SQLite locally, Snowflake optionally).

## Pipeline flow
1. **Extract**: read the raw campaign events CSV (file-transfer style ingestion)
2. **Clean**: standardise text fields, remove duplicate events
3. **Validate**: 6 automated data quality rules (null customer IDs, invalid event types/channels, unknown campaigns, negative costs, future timestamps). Failing rows go to a `rejected_events` table with the reason.
4. **Gate**: the run aborts if the reject rate exceeds a configurable threshold (default 5%)
5. **Transform**: build `fact_campaign_events` and `agg_campaign_performance` (open rate, click-through rate, unsubscribe rate, cost)
6. **Load**: SQLite by default, or Snowflake with `--target snowflake`; each run writes `data/dq_report.json` and a `pipeline_run_log` entry

## Run it
```
pip install -r requirements.txt
python generate_data.py        # creates synthetic raw data with injected errors
python pipeline.py             # runs the pipeline into warehouse.db
```
Then run the queries in `sql/analysis_queries.sql`.

**Snowflake:** create a free trial account, run `sql/snowflake_setup.sql`, set `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`, then `python pipeline.py --target snowflake`.

## Data documentation
| Column | Type | Description |
|---|---|---|
| event_id | int | Unique event identifier |
| customer_id | int | Customer identifier (required) |
| campaign_id / campaign_name | text | Campaign key and label |
| channel | text | email, sms or push |
| event_type | text | sent, delivered, opened, clicked, unsubscribed |
| event_ts | timestamp | When the event occurred (cannot be in the future) |
| cost | float | Cost of the send (cannot be negative) |

## Tech
Python (Pandas, NumPy), SQL, Snowflake connector, data quality validation, ETL, logging

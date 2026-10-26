"""Marketing campaign data pipeline: extract -> validate -> transform -> load.

Run:  python generate_data.py && python pipeline.py
Loads to a local SQLite warehouse by default. Set SNOWFLAKE_* env vars and use
--target snowflake to load into Snowflake instead (see sql/snowflake_setup.sql).
"""
import argparse, json, logging, os, sqlite3
from datetime import datetime
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("pipeline")

RAW = "data/campaign_events_raw.csv"
VALID_EVENTS = {"sent", "delivered", "opened", "clicked", "unsubscribed"}
VALID_CHANNELS = {"email", "sms", "push"}
KNOWN_CAMPAIGNS = {"C001", "C002", "C003", "C004"}


def extract(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["event_ts"])
    log.info("Extracted %d rows from %s", len(df), path)
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Standardise formats before validation."""
    df = df.copy()
    df["event_type"] = df["event_type"].str.strip().str.lower()
    df["channel"] = df["channel"].str.strip().str.lower()
    df = df.drop_duplicates(subset=["event_id"])
    return df


def run_quality_checks(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Return (valid_rows, rejected_rows, report). Each rule flags failing rows."""
    now = pd.Timestamp(datetime.now())
    rules = {
        "customer_id_not_null": df["customer_id"].notna(),
        "event_type_valid": df["event_type"].isin(VALID_EVENTS),
        "channel_valid": df["channel"].isin(VALID_CHANNELS),
        "campaign_known": df["campaign_id"].isin(KNOWN_CAMPAIGNS),
        "cost_non_negative": df["cost"] >= 0,
        "event_ts_not_future": df["event_ts"] <= now,
    }
    report = {"total_rows": len(df), "checks": {}}
    passed = pd.Series(True, index=df.index)
    reasons = pd.Series("", index=df.index)
    for name, ok in rules.items():
        report["checks"][name] = {"failed_rows": int((~ok).sum())}
        reasons = reasons.where(ok, reasons + name + ";")
        passed &= ok
    report["valid_rows"] = int(passed.sum())
    report["rejected_rows"] = int((~passed).sum())
    rejected = df[~passed].assign(reject_reason=reasons[~passed])
    for name, res in report["checks"].items():
        level = logging.WARNING if res["failed_rows"] else logging.INFO
        log.log(level, "DQ check %-22s failed rows: %d", name, res["failed_rows"])
    return df[passed], rejected, report


def transform(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    df = df.assign(customer_id=df["customer_id"].astype(int), event_date=df["event_ts"].dt.date.astype(str))
    funnel = (df.pivot_table(index=["campaign_id", "campaign_name", "channel"],
                             columns="event_type", values="event_id", aggfunc="count", fill_value=0)
                .reset_index())
    for col in VALID_EVENTS:
        if col not in funnel:
            funnel[col] = 0
    funnel["open_rate"] = (funnel["opened"] / funnel["delivered"]).round(4)
    funnel["click_through_rate"] = (funnel["clicked"] / funnel["delivered"]).round(4)
    funnel["unsubscribe_rate"] = (funnel["unsubscribed"] / funnel["delivered"]).round(4)
    cost = df.groupby("campaign_id", as_index=False)["cost"].sum().rename(columns={"cost": "total_cost"})
    return {"fact_campaign_events": df.assign(event_ts=df["event_ts"].astype(str)),
            "agg_campaign_performance": funnel.merge(cost, on="campaign_id")}


def load_sqlite(tables: dict, rejected: pd.DataFrame, report: dict, db="warehouse.db"):
    with sqlite3.connect(db) as con:
        for name, t in tables.items():
            t.to_sql(name, con, if_exists="replace", index=False)
        rejected.assign(event_ts=rejected["event_ts"].astype(str)).to_sql(
            "rejected_events", con, if_exists="replace", index=False)
        con.execute("CREATE TABLE IF NOT EXISTS pipeline_run_log (run_ts TEXT, report TEXT)")
        con.execute("INSERT INTO pipeline_run_log VALUES (?, ?)", (datetime.now().isoformat(), json.dumps(report)))
    log.info("Loaded %d tables to %s", len(tables) + 1, db)


def load_snowflake(tables: dict, rejected: pd.DataFrame):
    import snowflake.connector
    from snowflake.connector.pandas_tools import write_pandas
    con = snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"], user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"], warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "MARKETING_WH"),
        database=os.environ.get("SNOWFLAKE_DATABASE", "MARKETING_DB"), schema=os.environ.get("SNOWFLAKE_SCHEMA", "ANALYTICS"))
    try:
        for name, t in {**tables, "rejected_events": rejected.assign(event_ts=rejected["event_ts"].astype(str))}.items():
            t.columns = [c.upper() for c in t.columns]
            write_pandas(con, t, name.upper(), auto_create_table=True, overwrite=True)
            log.info("Loaded %s to Snowflake", name)
    finally:
        con.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--target", choices=["sqlite", "snowflake"], default="sqlite")
    p.add_argument("--max-reject-pct", type=float, default=5.0, help="fail run if rejects exceed this %%")
    args = p.parse_args()

    raw = extract(RAW)
    valid, rejected, report = run_quality_checks(clean(raw))
    reject_pct = 100 * report["rejected_rows"] / max(report["total_rows"], 1)
    log.info("Valid: %d | Rejected: %d (%.2f%%)", report["valid_rows"], report["rejected_rows"], reject_pct)
    if reject_pct > args.max_reject_pct:
        raise SystemExit(f"Reject rate {reject_pct:.2f}% exceeds threshold {args.max_reject_pct}%; aborting load")
    tables = transform(valid)
    (load_snowflake if args.target == "snowflake" else lambda t, r: load_sqlite(t, r, report))(tables, rejected)
    os.makedirs("data", exist_ok=True)
    with open("data/dq_report.json", "w") as f:
        json.dump(report, f, indent=2)


if __name__ == "__main__":
    main()

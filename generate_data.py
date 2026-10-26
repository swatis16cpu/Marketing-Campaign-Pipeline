"""Generate a synthetic email-campaign events file (mimics an SFMC-style export).
Deliberately includes some dirty records so the data quality checks have work to do."""
import os
import numpy as np, pandas as pd
os.makedirs("data", exist_ok=True)

rng = np.random.default_rng(42)
n = 5000
campaigns = {"C001": "Retirement Planning Webinar", "C002": "Annuity Awareness",
             "C003": "Year-End Savings", "C004": "New Client Welcome"}
channels = ["email", "sms", "push"]
events = ["sent", "delivered", "opened", "clicked", "unsubscribed"]

df = pd.DataFrame({
    "event_id": np.arange(1, n + 1),
    "customer_id": rng.integers(1000, 2500, n),
    "campaign_id": rng.choice(list(campaigns), n),
    "channel": rng.choice(channels, n, p=[0.7, 0.2, 0.1]),
    "event_type": rng.choice(events, n, p=[0.1, 0.35, 0.3, 0.2, 0.05]),
    "event_ts": pd.to_datetime("2026-01-01") + pd.to_timedelta(rng.integers(0, 90 * 86400, n), unit="s"),
    "cost": np.round(rng.uniform(0.01, 0.4, n), 4),
})
df["campaign_name"] = df["campaign_id"].map(campaigns)

# inject dirt: duplicates, nulls, bad values, unknown campaign, future dates
df = pd.concat([df, df.sample(40, random_state=1)], ignore_index=True)
df.loc[rng.choice(len(df), 30, replace=False), "customer_id"] = None
df.loc[rng.choice(len(df), 20, replace=False), "event_type"] = "OPENED "
df.loc[rng.choice(len(df), 15, replace=False), "cost"] = -1
df.loc[rng.choice(len(df), 10, replace=False), "campaign_id"] = "C999"
df.loc[rng.choice(len(df), 10, replace=False), "event_ts"] = pd.Timestamp("2030-01-01")

df.to_csv("data/campaign_events_raw.csv", index=False)
print(f"Wrote data/campaign_events_raw.csv with {len(df)} rows")

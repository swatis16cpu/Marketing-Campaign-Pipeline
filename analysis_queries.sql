-- Top campaigns by click-through rate (works in SQLite and Snowflake)
SELECT campaign_name, SUM(delivered) AS delivered, SUM(clicked) AS clicks,
       ROUND(1.0 * SUM(clicked) / SUM(delivered), 4) AS ctr
FROM agg_campaign_performance
GROUP BY campaign_name
ORDER BY ctr DESC;

-- Cost per click by channel
SELECT channel, ROUND(SUM(total_cost) / NULLIF(SUM(clicked), 0), 2) AS cost_per_click
FROM agg_campaign_performance
GROUP BY channel;

-- Customer engagement segments (5+ clicks = highly engaged)
SELECT CASE WHEN clicks >= 5 THEN 'highly engaged'
            WHEN clicks >= 1 THEN 'engaged' ELSE 'inactive' END AS segment,
       COUNT(*) AS customers
FROM (SELECT customer_id,
             SUM(CASE WHEN event_type = 'clicked' THEN 1 ELSE 0 END) AS clicks
      FROM fact_campaign_events GROUP BY customer_id) t
GROUP BY segment;

-- Data quality audit: why rows were rejected
SELECT reject_reason, COUNT(*) AS rows_rejected
FROM rejected_events GROUP BY reject_reason ORDER BY rows_rejected DESC;

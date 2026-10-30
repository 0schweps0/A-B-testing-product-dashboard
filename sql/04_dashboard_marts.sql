-- Relative days align rolling assignment cohorts; all seven exposure days exist.
CREATE OR REPLACE VIEW daily_metrics AS
WITH exposure AS (
    SELECT a.driver_id, a.variant, d.country, day_number,
           a.assigned_at + day_number * INTERVAL '1 day' AS day_start
    FROM experiment_assignments a INNER JOIN drivers d USING (driver_id)
    CROSS JOIN generate_series(0, 6) AS day_number
), daily AS (
    SELECT e.country, e.variant, e.day_number,
           COUNT(DISTINCT e.driver_id) AS exposed_drivers,
           COUNT(DISTINCT CASE WHEN r.ride_id IS NOT NULL THEN e.driver_id END) AS active_drivers,
           COUNT(r.ride_id) AS completed_rides, COALESCE(SUM(r.revenue), 0) AS revenue
    FROM exposure e LEFT JOIN rides r ON r.driver_id = e.driver_id
        AND r.completed_at >= e.day_start AND r.completed_at < e.day_start + INTERVAL '1 day'
    GROUP BY e.country, e.variant, e.day_number
)
SELECT *, completed_rides - LAG(completed_rides) OVER (
           PARTITION BY country, variant ORDER BY day_number) AS rides_change,
       SUM(completed_rides) OVER (PARTITION BY country, variant ORDER BY day_number
           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cumulative_rides
FROM daily;

CREATE OR REPLACE VIEW calendar_activity AS
SELECT (r.completed_at AT TIME ZONE 'UTC')::date AS activity_date,
       d.country, a.variant, COUNT(*) AS completed_rides
FROM rides r INNER JOIN experiment_assignments a USING (driver_id)
INNER JOIN drivers d USING (driver_id)
WHERE r.completed_at >= a.assigned_at AND r.completed_at < a.assigned_at + INTERVAL '7 days'
GROUP BY 1, 2, 3;

-- Python writes these precomputed tests; BI never recomputes p-values from daily rows.
CREATE TABLE IF NOT EXISTS statistical_results (
    scope text PRIMARY KEY,
    n_control bigint NOT NULL, n_treatment bigint NOT NULL,
    rate_control double precision NOT NULL, rate_treatment double precision NOT NULL,
    absolute_uplift double precision NOT NULL,
    relative_uplift double precision,
    ci_low double precision NOT NULL, ci_high double precision NOT NULL,
    p_value double precision NOT NULL,
    srm_p_value double precision NOT NULL,
    rides_p_value_exploratory double precision,
    net_incremental_contribution double precision NOT NULL,
    net_ci_low double precision NOT NULL, net_ci_high double precision NOT NULL,
    bonus_cost double precision NOT NULL
);

-- Aggregate rides and payments independently to avoid fan-out multiplication.
CREATE OR REPLACE VIEW driver_metrics AS
WITH ride_totals AS (
    SELECT a.driver_id, COUNT(r.ride_id)::bigint AS completed_rides,
           COALESCE(SUM(r.revenue), 0) AS revenue
    FROM experiment_assignments a
    LEFT JOIN rides r ON r.driver_id = a.driver_id
        AND r.completed_at >= a.assigned_at
        AND r.completed_at < a.assigned_at + INTERVAL '7 days'
    GROUP BY a.driver_id
), bonus_totals AS (
    SELECT a.driver_id, COALESCE(SUM(b.amount), 0) AS bonus_cost
    FROM experiment_assignments a
    LEFT JOIN bonus_payments b ON b.driver_id = a.driver_id
        AND b.paid_at >= a.assigned_at
        AND b.paid_at < a.assigned_at + INTERVAL '7 days'
    GROUP BY a.driver_id
)
SELECT a.driver_id, d.country, a.variant, a.assigned_at,
       t.completed_rides, (t.completed_rides > 0)::int AS reactivated,
       t.revenue, b.bonus_cost,
       t.revenue * c.margin_rate AS contribution_before_bonus,
       t.revenue * c.margin_rate - b.bonus_cost AS contribution_after_bonus
FROM experiment_assignments a
INNER JOIN drivers d ON d.driver_id = a.driver_id
INNER JOIN ride_totals t ON t.driver_id = a.driver_id
INNER JOIN bonus_totals b ON b.driver_id = a.driver_id
CROSS JOIN model_config c;

CREATE OR REPLACE VIEW group_metrics AS
SELECT variant, COUNT(*) AS assigned_users,
       COUNT(*) FILTER (WHERE reactivated = 1) AS reactivated_drivers,
       AVG(reactivated)::double precision AS reactivation_rate,
       AVG(completed_rides)::double precision AS avg_rides_per_assigned_driver,
       SUM(completed_rides) AS completed_rides,
       SUM(revenue) AS revenue, SUM(bonus_cost) AS bonus_cost,
       SUM(contribution_before_bonus) AS contribution_before_bonus,
       SUM(contribution_after_bonus) AS contribution_after_bonus
FROM driver_metrics
GROUP BY variant;

CREATE OR REPLACE VIEW experiment_effect AS
SELECT t.reactivation_rate - c.reactivation_rate AS absolute_uplift,
       t.reactivation_rate / NULLIF(c.reactivation_rate, 0) - 1 AS relative_uplift,
       t.assigned_users * (t.contribution_before_bonus / t.assigned_users
           - c.contribution_before_bonus / c.assigned_users) AS incremental_contribution_before_bonus,
       t.bonus_cost,
       t.assigned_users * (t.contribution_after_bonus / t.assigned_users
           - c.contribution_after_bonus / c.assigned_users) AS net_incremental_contribution
FROM (SELECT * FROM group_metrics WHERE variant = 'treatment') t
CROSS JOIN (SELECT * FROM group_metrics WHERE variant = 'control') c;

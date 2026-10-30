CREATE OR REPLACE VIEW country_metrics AS
SELECT country, variant, COUNT(*) AS assigned_users,
       SUM(reactivated) AS reactivated_drivers,
       AVG(reactivated)::double precision AS reactivation_rate,
       AVG(completed_rides)::double precision AS avg_rides_per_assigned_driver,
       SUM(completed_rides) AS completed_rides, SUM(revenue) AS revenue,
       SUM(bonus_cost) AS bonus_cost,
       SUM(contribution_after_bonus) AS contribution_after_bonus
FROM driver_metrics GROUP BY country, variant;

-- Qualifiers are an audit view, not the primary-metric denominator.
CREATE OR REPLACE VIEW bonus_qualifiers AS
SELECT a.driver_id, COUNT(*) AS qualifying_rides
FROM experiment_assignments a
INNER JOIN rides r ON r.driver_id = a.driver_id
WHERE a.variant = 'treatment' AND r.completed_at >= a.assigned_at
    AND r.completed_at < a.assigned_at + INTERVAL '7 days'
GROUP BY a.driver_id HAVING COUNT(*) >= 3;

-- Third completion is the moment the bonus is earned.
CREATE OR REPLACE VIEW ride_milestones AS
WITH ranked AS (
    SELECT a.driver_id, a.variant, r.completed_at,
           ROW_NUMBER() OVER (PARTITION BY a.driver_id ORDER BY r.completed_at, r.ride_id) AS ride_number
    FROM experiment_assignments a
    INNER JOIN rides r ON r.driver_id = a.driver_id
        AND r.completed_at >= a.assigned_at
        AND r.completed_at < a.assigned_at + INTERVAL '7 days'
)
SELECT driver_id, variant, completed_at AS third_ride_at FROM ranked WHERE ride_number = 3;

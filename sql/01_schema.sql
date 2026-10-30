-- A dedicated local development database; all timestamps are UTC.
CREATE TABLE IF NOT EXISTS model_config (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    margin_rate numeric NOT NULL CHECK (margin_rate BETWEEN 0 AND 1)
);
CREATE TABLE IF NOT EXISTS drivers (
    driver_id bigint PRIMARY KEY CHECK (driver_id > 0),
    country text NOT NULL CHECK (country IN ('RU', 'KZ', 'BY')),
    signup_date timestamptz NOT NULL
);
CREATE TABLE IF NOT EXISTS experiment_assignments (
    driver_id bigint PRIMARY KEY REFERENCES drivers(driver_id),
    variant text NOT NULL CHECK (variant IN ('control', 'treatment')),
    assigned_at timestamptz NOT NULL
);
CREATE TABLE IF NOT EXISTS rides (
    ride_id bigint PRIMARY KEY CHECK (ride_id > 0),
    driver_id bigint NOT NULL REFERENCES drivers(driver_id),
    completed_at timestamptz NOT NULL,
    revenue numeric(14, 2) NOT NULL CHECK (revenue >= 0)
);
CREATE TABLE IF NOT EXISTS bonus_payments (
    payment_id bigint PRIMARY KEY CHECK (payment_id > 0),
    driver_id bigint NOT NULL UNIQUE REFERENCES experiment_assignments(driver_id),
    paid_at timestamptz NOT NULL,
    amount numeric(14, 2) NOT NULL CHECK (amount = 300)
);
CREATE INDEX IF NOT EXISTS rides_driver_time ON rides(driver_id, completed_at);
CREATE INDEX IF NOT EXISTS assignments_variant ON experiment_assignments(variant);
CREATE INDEX IF NOT EXISTS drivers_country ON drivers(country);

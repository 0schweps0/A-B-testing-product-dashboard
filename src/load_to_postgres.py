"""Atomic, idempotent CSV-to-PostgreSQL load and SQL mart creation."""
import os
from contextlib import contextmanager
from collections.abc import Iterator
import pandas as pd
import psycopg
from dotenv import load_dotenv
from src.config import MARGIN_RATE, ROOT
from src.validate_data import COLUMNS, read_raw, validate


@contextmanager
def connect() -> Iterator[psycopg.Connection]:
    """Read local .env; never log a DSN or credential."""
    load_dotenv(ROOT / ".env")
    password = os.environ.get("POSTGRES_PASSWORD")
    if not password:
        raise RuntimeError("Set POSTGRES_PASSWORD securely in .env")
    with psycopg.connect(host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
                         port=os.getenv("POSTGRES_PORT", "5433"),
                         dbname=os.getenv("POSTGRES_DB", "reactivation"),
                         user=os.getenv("POSTGRES_USER", "analyst"), password=password,
                         connect_timeout=10) as conn:
        conn.execute("SET TIME ZONE 'UTC'")
        yield conn


def load(data: dict[str, pd.DataFrame] | None = None) -> dict[str, int]:
    """Replace this project's four simulation tables in one transaction.

    Use a dedicated database: this intentionally replaces prior simulated runs.
    COPY uses explicit columns and PostgreSQL constraints are always enabled.
    """
    data = read_raw() if data is None else data
    counts = validate(data)
    with connect() as conn:
        conn.execute((ROOT / "sql/01_schema.sql").read_text())
        conn.execute("INSERT INTO model_config VALUES (true, %s) ON CONFLICT (singleton) DO UPDATE SET margin_rate = EXCLUDED.margin_rate", (MARGIN_RATE,))
        conn.execute("TRUNCATE bonus_payments, rides, experiment_assignments, drivers")
        for name, columns in COLUMNS.items():
            with conn.cursor().copy(f"COPY {name} ({', '.join(columns)}) FROM STDIN WITH (FORMAT CSV)") as copy:
                copy.write(data[name].to_csv(index=False, header=False))
            actual = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
            if actual != counts[name]:
                raise RuntimeError(f"Row count mismatch: {name}")
        for script in ["02_metrics.sql", "03_segment_analysis.sql", "04_dashboard_marts.sql"]:
            conn.execute((ROOT / "sql" / script).read_text())
        # Old tests must never remain attached to a newly loaded simulation.
        conn.execute("TRUNCATE statistical_results")
    return counts


def query_frame(conn: psycopg.Connection, query: str) -> pd.DataFrame:
    with conn.cursor() as cursor:
        cursor.execute(query)
        return pd.DataFrame(cursor.fetchall(), columns=[c.name for c in cursor.description])


if __name__ == "__main__":
    print(load())

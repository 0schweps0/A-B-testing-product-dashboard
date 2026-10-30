"""Real PostgreSQL integration; isolated schema, rolled back after every test."""
import os
from uuid import uuid4
import pandas as pd
import pytest
from psycopg import sql, errors
from src.config import ROOT
from src.load_to_postgres import connect, query_frame
from src.validate_data import COLUMNS

pytestmark = pytest.mark.postgres


@pytest.fixture
def db(tiny):
    if os.getenv("RUN_POSTGRES_TESTS") != "1":
        pytest.skip("Set RUN_POSTGRES_TESTS=1 to execute real PostgreSQL integration")
    with connect() as conn:
        schema = "test_" + uuid4().hex
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        conn.execute(sql.SQL("SET LOCAL search_path TO {}").format(sql.Identifier(schema)))
        for path in sorted((ROOT / "sql").glob("*.sql")):
            conn.execute(path.read_text())
        conn.execute("INSERT INTO model_config VALUES (true, .4)")
        for name, columns in COLUMNS.items():
            with conn.cursor().copy(f"COPY {name} ({', '.join(columns)}) FROM STDIN WITH (FORMAT CSV)") as copy:
                copy.write(tiny[name].to_csv(header=False, index=False))
        try:
            yield conn
        finally:
            conn.rollback()


def test_hand_calculated_sql(db):
    rows = query_frame(db, "SELECT * FROM driver_metrics ORDER BY driver_id")
    assert rows.completed_rides.tolist() == [1, 0, 3, 0]
    assert rows.reactivated.tolist() == [1, 0, 1, 0]
    groups = query_frame(db, "SELECT * FROM group_metrics ORDER BY variant")
    assert groups.assigned_users.tolist() == [2, 2]
    assert groups.reactivation_rate.tolist() == [.5, .5]
    assert groups.completed_rides.tolist() == [1, 3]
    assert groups.avg_rides_per_assigned_driver.tolist() == [.5, 1.5]
    assert [float(v) for v in groups.revenue] == [100., 300.]
    assert [float(v) for v in groups.bonus_cost] == [0., 300.]
    effect = query_frame(db, "SELECT * FROM experiment_effect").iloc[0]
    assert float(effect.absolute_uplift) == 0
    assert float(effect.incremental_contribution_before_bonus) == 80
    assert float(effect.net_incremental_contribution) == -220


def test_daily_windows_and_qualifiers(db):
    daily = query_frame(db, "SELECT * FROM daily_metrics")
    assert len(daily) == 14
    assert daily.completed_rides.sum() == 4
    assert set(daily.exposed_drivers) == {2}
    assert daily.active_drivers.sum() == 4
    qualifiers = query_frame(db, "SELECT * FROM bonus_qualifiers")
    assert qualifiers.driver_id.tolist() == [3]
    milestones = query_frame(db, "SELECT * FROM ride_milestones")
    assert milestones.driver_id.tolist() == [3]
    assert milestones.third_ride_at.iloc[0] == pd.Timestamp("2025-05-03", tz="UTC")
    assert len(query_frame(db, "SELECT * FROM country_metrics")) == 2


@pytest.mark.parametrize("statement", [
    "INSERT INTO drivers VALUES (1, 'RU', NOW())",
    "INSERT INTO drivers VALUES (99, 'XX', NOW())",
    "INSERT INTO rides VALUES (100, 99, NOW(), 5)",
    "INSERT INTO rides VALUES (100, 1, NOW(), -1)",
    "INSERT INTO experiment_assignments VALUES (1, 'other', NOW())",
    "INSERT INTO bonus_payments VALUES (100, 3, NOW(), 301)",
])
def test_database_constraints(db, statement):
    with pytest.raises(errors.IntegrityError):
        with db.transaction():
            db.execute(statement)

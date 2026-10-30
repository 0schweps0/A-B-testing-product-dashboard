"""Small deterministic relational fixtures; no production data or mocks of SQL."""
import pandas as pd
import pytest
from src.generate_data import generate


@pytest.fixture
def data():
    return generate(seed=42, per_arm=100)


@pytest.fixture
def tiny():
    t = pd.Timestamp("2025-05-01", tz="UTC")
    drivers = pd.DataFrame({"driver_id": [1, 2, 3, 4], "country": ["RU"]*4,
                            "signup_date": [t-pd.Timedelta(days=365)]*4})
    assignments = pd.DataFrame({"driver_id": [1, 2, 3, 4],
                                "variant": ["control", "control", "treatment", "treatment"],
                                "assigned_at": [t]*4})
    # Driver 1: left boundary included; driver 2: exactly +7 days excluded.
    # Driver 3: three rides => payout; driver 4: zero rides => kept in denominator.
    rides = pd.DataFrame({"ride_id": [1, 2, 3, 4, 5], "driver_id": [1, 2, 3, 3, 3],
                          "completed_at": [t, t+pd.Timedelta(days=7), t, t+pd.Timedelta(days=1), t+pd.Timedelta(days=2)],
                          "revenue": [100., 900., 100., 100., 100.]})
    payments = pd.DataFrame({"payment_id": [1], "driver_id": [3],
                             "paid_at": [t+pd.Timedelta(days=2)], "amount": [300.]})
    return {"drivers": drivers, "experiment_assignments": assignments,
            "rides": rides, "bonus_payments": payments}

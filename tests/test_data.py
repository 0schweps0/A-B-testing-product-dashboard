import pandas as pd
import pytest
from src.generate_data import generate
from src.validate_data import validate, window_rides
from src.design import sample_size
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize


def test_design_power():
    n = sample_size()
    effect = abs(proportion_effectsize(.14, .12))
    achieved = NormalIndPower().power(effect, nobs1=n, alpha=.05)
    assert achieved >= .8
    assert NormalIndPower().power(effect, nobs1=n-1, alpha=.05) < .8


def test_generated_integrity(data):
    assert validate(data)["drivers"] == 200
    assert data["drivers"].driver_id.is_unique
    a = data["experiment_assignments"]
    assert a.driver_id.is_unique
    assert a.variant.value_counts().to_dict() == {"control": 100, "treatment": 100}
    assert len(window_rides(data).driver_id.unique()) < 200


def test_seed_repeatability(data):
    for name, frame in generate(seed=42, per_arm=100).items():
        pd.testing.assert_frame_equal(data[name], frame)
    assert not data["experiment_assignments"].equals(generate(seed=43, per_arm=100)["experiment_assignments"])


def test_window_boundaries_and_zero_users(tiny):
    assert validate(tiny)["drivers"] == 4
    observed = window_rides(tiny)
    assert observed.ride_id.tolist() == [1, 3, 4, 5]
    assert 2 not in set(observed.driver_id)
    assert 4 not in set(observed.driver_id)


@pytest.mark.parametrize("mutation,match", [
    ("duplicate_driver", "duplicate primary key"),
    ("duplicate_assignment", "duplicate primary key"),
    ("bad_variant", "invalid variants"),
    ("bad_country", "invalid country"),
    ("null", "null values"),
    ("foreign_key", "foreign key"),
    ("recent_activity", "ineligible"),
    ("immature", "immature"),
    ("negative_revenue", "invalid revenue"),
    ("bonus_control", "eligibility"),
    ("early_bonus", "before third"),
    ("missing_bonus", "coverage"),
    ("wrong_bonus", "invalid bonus"),
    ("duplicate_bonus", "duplicate bonus"),
])
def test_invalid_data_rejected(tiny, mutation, match):
    if mutation == "duplicate_driver":
        tiny["drivers"] = pd.concat([tiny["drivers"], tiny["drivers"].iloc[[0]]])
    elif mutation == "duplicate_assignment":
        tiny["experiment_assignments"] = pd.concat([tiny["experiment_assignments"], tiny["experiment_assignments"].iloc[[0]]])
    elif mutation == "bad_variant":
        tiny["experiment_assignments"].loc[0, "variant"] = "invalid"
    elif mutation == "bad_country":
        tiny["drivers"].loc[0, "country"] = "XX"
    elif mutation == "null":
        tiny["drivers"].loc[0, "country"] = None
    elif mutation == "foreign_key":
        tiny["rides"].loc[0, "driver_id"] = 99
    elif mutation == "recent_activity":
        tiny["rides"].loc[0, "completed_at"] -= pd.Timedelta(days=1)
    elif mutation == "immature":
        tiny["experiment_assignments"]["assigned_at"] += pd.Timedelta(days=100)
    elif mutation == "negative_revenue":
        tiny["rides"].loc[0, "revenue"] = -1.
    elif mutation == "bonus_control":
        tiny["bonus_payments"].loc[0, "driver_id"] = 1
    elif mutation == "early_bonus":
        tiny["bonus_payments"].loc[0, "paid_at"] -= pd.Timedelta(days=1)
    elif mutation == "missing_bonus":
        tiny["bonus_payments"] = tiny["bonus_payments"].iloc[:0]
    elif mutation == "wrong_bonus":
        tiny["bonus_payments"].loc[0, "amount"] = 301.
    elif mutation == "duplicate_bonus":
        duplicate = tiny["bonus_payments"].copy()
        duplicate["payment_id"] = 2
        tiny["bonus_payments"] = pd.concat([tiny["bonus_payments"], duplicate])
    with pytest.raises(ValueError, match=match):
        validate(tiny)


def test_empty_payout_table_is_valid_and_preserves_schema():
    small = generate(seed=42, per_arm=1)
    assert small["bonus_payments"].empty
    assert validate(small)["bonus_payments"] == 0


def test_generation_rejects_nonpositive_size():
    with pytest.raises(ValueError, match="positive integer"):
        generate(per_arm=0)

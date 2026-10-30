"""Fail-fast relational, temporal and business-rule validation."""
import numpy as np
import pandas as pd
from src.config import AS_OF, BONUS, ROOT

TIME_COLUMNS = {"drivers": "signup_date", "experiment_assignments": "assigned_at",
                "rides": "completed_at", "bonus_payments": "paid_at"}
COLUMNS = {"drivers": ["driver_id", "country", "signup_date"],
           "experiment_assignments": ["driver_id", "variant", "assigned_at"],
           "rides": ["ride_id", "driver_id", "completed_at", "revenue"],
           "bonus_payments": ["payment_id", "driver_id", "paid_at", "amount"]}


def read_raw() -> dict[str, pd.DataFrame]:
    """Read explicit table schemas, preserving timezone-aware timestamps."""
    data = {}
    for name, columns in COLUMNS.items():
        dtypes = {col: "int64" for col in columns if col.endswith("_id")}
        dtypes.update({col: "float64" for col in columns if col in {"revenue", "amount"}})
        data[name] = pd.read_csv(ROOT / f"data/raw/{name}.csv", dtype=dtypes)
    for name, column in TIME_COLUMNS.items():
        data[name][column] = pd.to_datetime(data[name][column], utc=True, errors="raise")
    return data


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def window_rides(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Half-open observation window; keep zero-ride drivers in the assignment spine."""
    joined = data["rides"].merge(data["experiment_assignments"], on="driver_id", validate="many_to_one")
    return joined[(joined.completed_at >= joined.assigned_at) &
                  (joined.completed_at < joined.assigned_at + pd.Timedelta(days=7))].copy()


def validate(data: dict[str, pd.DataFrame]) -> dict[str, int]:
    """Validate keys, types, eligibility, maturity, payouts and their exact coverage."""
    for name, columns in COLUMNS.items():
        frame = data[name]
        require(list(frame.columns) == columns, f"{name}: unexpected schema")
        require(not frame.isna().any().any(), f"{name}: null values")
        key = columns[0]
        require(frame[key].is_unique, f"{name}: duplicate primary key")
        for col in [c for c in columns if c.endswith("_id")]:
            require(pd.api.types.is_integer_dtype(frame[col]) and (frame[col] > 0).all(), f"{name}: invalid ID")
        require(isinstance(frame[TIME_COLUMNS[name]].dtype, pd.DatetimeTZDtype), f"{name}: timestamp dtype")
    d, a, r, b = (data[k] for k in COLUMNS)
    require(set(d.country) <= {"RU", "KZ", "BY"}, "invalid country")
    require(set(a.variant) == {"control", "treatment"}, "invalid variants / empty arm")
    require(set(a.driver_id) == set(d.driver_id), "assignment coverage")
    for name in ["rides", "bonus_payments"]:
        require(set(data[name].driver_id) <= set(a.driver_id), f"{name}: foreign key")
    require(pd.api.types.is_numeric_dtype(r.revenue) and np.isfinite(r.revenue).all() and (r.revenue >= 0).all(), "invalid revenue")
    require(pd.api.types.is_numeric_dtype(b.amount) and (b.amount == BONUS).all(), "invalid bonus amount")
    require(b.driver_id.is_unique, "duplicate bonus per driver")
    cohort = a.merge(d, on="driver_id", validate="one_to_one")
    require((cohort.signup_date <= cohort.assigned_at).all(), "signup after assignment")
    require((a.assigned_at + pd.Timedelta(days=7) <= pd.Timestamp(AS_OF)).all(), "immature follow-up")
    history = r.merge(a, on="driver_id").merge(d[["driver_id", "signup_date"]], on="driver_id")
    require((history.completed_at >= history.signup_date).all(), "ride before signup")
    recent = (history.completed_at < history.assigned_at) & (history.completed_at >= history.assigned_at - pd.Timedelta(days=30))
    require(not recent.any(), "ineligible driver: activity in preceding 30 days")
    require((r.completed_at <= pd.Timestamp(AS_OF)).all(), "event after extraction")
    observed = window_rides(data)
    counts = observed.groupby("driver_id").size()
    eligible = set(a.loc[(a.variant == "treatment") & a.driver_id.isin(counts[counts >= 3].index), "driver_id"])
    require(set(b.driver_id) == eligible, "bonus eligibility/coverage mismatch")
    paid = b.merge(a, on="driver_id")
    require(((paid.paid_at >= paid.assigned_at) & (paid.paid_at < paid.assigned_at + pd.Timedelta(days=7))).all(), "payment outside window")
    third = observed.sort_values(["driver_id", "completed_at"]).groupby("driver_id").nth(2)
    third = third[["driver_id", "completed_at"]].rename(columns={"completed_at": "third_at"})
    paid = paid.merge(third, on="driver_id", how="left", validate="one_to_one")
    require((paid.paid_at >= paid.third_at).all(), "payment before third completion")
    return {name: len(frame) for name, frame in data.items()}


if __name__ == "__main__":
    print(validate(read_raw()))

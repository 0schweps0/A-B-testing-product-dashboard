"""Seeded simulation. Probabilities here are NEVER passed to analysis modules."""
import argparse
import json
import numpy as np
import pandas as pd
from src.config import BONUS, ROOT, SEED
from src.design import plan


def generate(seed: int = SEED, per_arm: int | None = None) -> dict[str, pd.DataFrame]:
    """Simulate eligible drivers with pre-period history and mature follow-up."""
    rng = np.random.default_rng(seed)
    if per_arm is not None and (not isinstance(per_arm, int) or per_arm < 1):
        raise ValueError("per_arm must be a positive integer")
    n = 2 * (per_arm if per_arm is not None else plan()["required_per_arm"])
    ids = np.arange(1, n + 1)
    country = rng.choice(["RU", "KZ", "BY"], n, p=[.65, .23, .12])
    # Fixed balanced allocation; shuffling occurs before any outcome is drawn.
    variant = rng.permutation(np.repeat(["control", "treatment"], n // 2))
    assigned = pd.Timestamp("2025-05-01", tz="UTC") + pd.to_timedelta(rng.integers(0, 7*86400, n), unit="s")
    signup = assigned - pd.to_timedelta(rng.integers(200, 1000, n), unit="D")
    drivers = pd.DataFrame({"driver_id": ids, "country": country, "signup_date": signup})
    assignments = pd.DataFrame({"driver_id": ids, "variant": variant, "assigned_at": assigned})
    country_shift = np.select([country == "KZ", country == "BY"], [.01, -.01], default=0.)
    probability = .12 + country_shift + .02 * (variant == "treatment")
    reactivated = rng.random(n) < probability
    counts = reactivated * (1 + rng.negative_binomial(2, .5, n))
    rides: list[dict] = []
    payments: list[dict] = []
    for i in range(n):
        # Every driver has old activity, and no completed rides in [-30d, 0).
        offsets = [-int(rng.integers(31*86400, 180*86400))]
        offsets += sorted(rng.integers(0, 7*86400, int(counts[i])).tolist())
        # Deliberate out-of-window future rides exercise the window filter.
        if rng.random() < .03:
            offsets.append(int(rng.integers(7*86400, 8*86400)))
        for seconds in offsets:
            rides.append({"ride_id": len(rides)+1, "driver_id": int(ids[i]),
                          "completed_at": assigned[i] + pd.Timedelta(seconds=seconds),
                          "revenue": round(float(rng.lognormal(np.log(130), .35)), 2)})
        if variant[i] == "treatment" and counts[i] >= 3:
            payments.append({"payment_id": len(payments)+1, "driver_id": int(ids[i]),
                             "paid_at": assigned[i] + pd.Timedelta(seconds=offsets[3]),
                             "amount": BONUS})
    bonuses = pd.DataFrame(payments, columns=["payment_id", "driver_id", "paid_at", "amount"])
    # Retain valid schemas even in small simulations with no qualifying payouts.
    bonuses = bonuses.astype({"payment_id": "int64", "driver_id": "int64", "amount": "float64"})
    bonuses["paid_at"] = pd.to_datetime(bonuses["paid_at"], utc=True)
    return {"drivers": drivers, "experiment_assignments": assignments,
            "rides": pd.DataFrame(rides), "bonus_payments": bonuses}


def main() -> None:
    """Write the analysis plan first, then raw simulation tables."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "data/raw").mkdir(parents=True, exist_ok=True)
    (ROOT / "reports/analysis_plan.json").write_text(json.dumps(plan(), indent=2) + "\n")
    for name, frame in generate(args.seed).items():
        frame.to_csv(ROOT / f"data/raw/{name}.csv", index=False)


if __name__ == "__main__":
    main()

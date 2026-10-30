"""Run: python -m src.run_pipeline. Requires the dedicated PostgreSQL service."""
import hashlib
import json
import logging
import platform
from importlib.metadata import version
import numpy as np
import pandas as pd
from src.config import ROOT
from src.generate_data import main as generate_main
from src.validate_data import read_raw, validate, window_rides
from src.load_to_postgres import connect, load, query_frame
from src.calculate_statistics import statistics_by_scope, economic_scenarios
from src.reporting import write_report, plots

LOG = logging.getLogger(__name__)


def verify_sql(data: dict[str, pd.DataFrame], metrics: pd.DataFrame) -> None:
    """Independent pandas parity check against every driver, not only totals."""
    rides = window_rides(data)
    expected = data["experiment_assignments"][["driver_id"]].merge(
        rides.groupby("driver_id").agg(completed_rides=("ride_id", "size"), revenue=("revenue", "sum")),
        on="driver_id", how="left").fillna(0).merge(
        data["bonus_payments"].groupby("driver_id").amount.sum().rename("bonus_cost"),
        on="driver_id", how="left").fillna(0).sort_values("driver_id")
    actual = metrics.sort_values("driver_id")
    if not np.array_equal(expected.driver_id, actual.driver_id):
        raise RuntimeError("SQL dropped or duplicated assignments")
    for column in ["completed_rides", "revenue", "bonus_cost"]:
        if not np.allclose(expected[column].astype(float), actual[column].astype(float), rtol=0, atol=1e-8):
            raise RuntimeError(f"SQL/pandas mismatch: {column}")


def run() -> dict:
    """Rebuild simulation, validate, load, materialize and export a consistent run."""
    for folder in ["data/raw", "data/processed", "data/dashboard", "reports"]:
        (ROOT / folder).mkdir(parents=True, exist_ok=True)
    LOG.info("Writing prospective plan and generating synthetic data")
    generate_main()
    data = read_raw()
    counts = validate(data)
    LOG.info("Validated source rows: %s", counts)
    load(data)
    with connect() as conn:
        frames = {name: query_frame(conn, f"SELECT * FROM {name} ORDER BY {order}") for name, order in {
            "driver_metrics": "driver_id", "group_metrics": "variant", "country_metrics": "country, variant",
            "daily_metrics": "country, variant, day_number", "calendar_activity": "activity_date, country, variant",
            "experiment_effect": "absolute_uplift"}.items()}
        driver_metrics = frames["driver_metrics"]
        for col in ["revenue", "bonus_cost", "contribution_before_bonus", "contribution_after_bonus"]:
            driver_metrics[col] = driver_metrics[col].astype(float)
        verify_sql(data, driver_metrics)
        results = statistics_by_scope(driver_metrics)
        scenarios = economic_scenarios(driver_metrics)
        sql_effect = frames["experiment_effect"].iloc[0]
        overall = results.iloc[0]
        for column in ["absolute_uplift", "relative_uplift", "net_incremental_contribution", "bonus_cost"]:
            if not np.isclose(float(sql_effect[column]), float(overall[column]), atol=1e-8):
                raise RuntimeError(f"SQL/statistics mismatch: {column}")
        columns = list(results.columns)
        # Explicit schema order permits changes to the DataFrame column order.
        with conn.cursor().copy(f"COPY statistical_results ({', '.join(columns)}) FROM STDIN WITH (FORMAT CSV, HEADER TRUE)") as copy:
            copy.write(results.to_csv(index=False))
        loaded_results = query_frame(conn, "SELECT * FROM statistical_results ORDER BY scope")
        if len(loaded_results) != len(results):
            raise RuntimeError("Statistics write-back incomplete")
    frames["driver_metrics"].to_csv(ROOT / "data/processed/driver_metrics.csv", index=False)
    for name, frame in frames.items():
        if name != "driver_metrics":
            frame.to_csv(ROOT / f"data/dashboard/{name}.csv", index=False)
    # Driver spine supports assignment-date filtering without truncating follow-up.
    driver_metrics.to_csv(ROOT / "data/dashboard/driver_metrics.csv", index=False)
    results.to_csv(ROOT / "data/dashboard/statistical_results.csv", index=False)
    scenarios.to_csv(ROOT / "data/dashboard/economic_scenarios.csv", index=False)
    evidence = {"source_counts": counts, "sql_pandas_driver_parity": "passed",
                "sql_statistics_effect_parity": "passed", "statistics_written_to_postgres": len(results),
                "python": platform.python_version(),
                "packages": {name: version(name) for name in ["numpy", "pandas", "scipy", "statsmodels", "psycopg"]},
                "raw_sha256": {name: hashlib.sha256((ROOT / f"data/raw/{name}.csv").read_bytes()).hexdigest() for name in data}}
    (ROOT / "reports/validation.json").write_text(json.dumps(evidence, indent=2) + "\n")
    write_report(frames["group_metrics"], results, frames["country_metrics"], scenarios)
    plots(frames["group_metrics"], frames["daily_metrics"], results, frames["country_metrics"])
    LOG.info("Export complete. %s", results.iloc[0].to_dict())
    return evidence


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        run()
    except Exception:
        LOG.error("Pipeline failed. Previous artifacts may be stale; fix the error and rerun.")
        raise

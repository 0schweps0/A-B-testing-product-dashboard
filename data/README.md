# Synthetic data artifacts

- `raw/`: four generated source CSVs, ignored by Git; regenerate with `python -m src.generate_data`.
- `processed/`: driver-level SQL output, ignored by Git.
- `dashboard/`: versioned CSV marts from the actual seeded run; local Streamlit and manual DataLens import use these files.

All data are synthetic. No real personal information is used. Revenue is platform commission in RUB-equivalent, not GMV. CSV datetimes are UTC. The repository includes precomputed dashboard artifacts so the dashboard can run without a database; rerun the pipeline to reproduce and replace them.

Source keys and fields are defined in `sql/01_schema.sql`. Empty payouts retain their schema. Ride histories have at least one old trip per simulated driver, no completed trips in the preceding 30 days, and a small number of intentionally out-of-window future trips. These trips are retained in raw data and correctly excluded from experiment metrics.

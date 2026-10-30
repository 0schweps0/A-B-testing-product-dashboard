# Dashboard guide

All data are synthetic. A local interactive Streamlit dashboard is implemented in [app.py](app.py). No DataLens publication or DataLens screenshot is claimed: no authenticated DataLens UI or cloud PostgreSQL connection was available.

## Local dashboard

From the repository root after the pipeline:

```bash
python -m streamlit run dashboard/app.py --server.address 127.0.0.1
```

Use the address printed by Streamlit in your local terminal. The app reads CSV, so PostgreSQL need not remain running. The actual local screenshot is in [screenshots/local_dashboard.png](../screenshots/local_dashboard.png).

Eight KPI cards show assigned drivers, control/treatment reactivation, absolute/relative uplift, p-value, bonus cost and net incremental contribution. Plotly charts show group reactivation, daily completed rides, country differences, Newcombe uplift interval, sensitivity of economics and calendar activity. A segment table and filtered CSV download are included.

Country changes the precomputed country inference (exploratory). Assignment-date and group filters change descriptive driver charts and the segment table. They **do not** recompute or silently subset inferential cards. The daily and calendar charts use complete assignment cohorts and are explicitly labelled. Selecting assignment date preserves all seven follow-up days; filtering primary inference by ride date would bias both numerator and denominator.

## DataLens: CSV route

A local PostgreSQL server is not reachable by DataLens through `localhost`. Do not expose this database publicly. Use the supported **Files** connection to upload the CSV files from `data/dashboard/` manually. See [official file connection instructions](https://yandex.cloud/en/docs/datalens/operations/connection/create-file). Menu labels and availability can depend on the current DataLens edition/account.

1. Open DataLens with your own account. Create a connection of type **Files**, upload one CSV and confirm delimiter `,`, header row, UTF-8 and decimal point `.`.
2. Create a separate dataset for each required grain below. Set string fields as dimensions; timestamps as Date/Datetime; numeric counts as integers and rates as decimal measures. Do not join aggregate datasets to driver rows.
3. Create charts in the chart editor, save them in a workbook, then create a dashboard and add the saved charts and selectors. Keep the complete-experiment inference section separate from descriptive filters.
4. Inspect every KPI against `reports/results.json` and every aggregate against the source CSV. A rate is a proportion (0–1), displayed as percent; absolute uplift in percentage points equals `absolute_uplift * 100`.
5. If the edition supports combined charts, use `ci_low`, `absolute_uplift`, `ci_high` in a combined point/interval chart. Otherwise use a table with all three values plus a zero reference, or a horizontal floating bar with endpoints `ci_low*100`, `ci_high*100`. Never present the interval as raw standard error. The fully rendered interactive interval is available locally.

### Datasets and grains

| CSV | Grain | Intended use |
| --- | --- | --- |
| `driver_metrics.csv` | one assigned driver | Cohort filters, denominator-safe descriptive KPIs |
| `group_metrics.csv` | variant, entire experiment | Complete-experiment group rates and totals |
| `country_metrics.csv` | country × variant | Country chart and segment table |
| `daily_metrics.csv` | country × variant × relative day 0–6 | Daily rides and exposure; all seven days retained |
| `calendar_activity.csv` | event date × country × variant with activity | Descriptive calendar series; no conversion denominator |
| `statistical_results.csv` | scope ALL/RU/KZ/BY | Precomputed tests, intervals and economic result |
| `experiment_effect.csv` | one entire-experiment row | SQL economic cross-check |
| `economic_scenarios.csv` | margin assumption × bonus assumption | Fixed-behavior sensitivity, not causal forecasts |

### Charts and aggregation rules

| Object | Dataset and fields | Aggregation |
| --- | --- | --- |
| Total assigned KPI | statistical results, scope=ALL | `n_control + n_treatment`, one row |
| Control rate KPI | statistical results, scope=ALL | `rate_control`, one row, percent |
| Treatment rate KPI | statistical results, scope=ALL | `rate_treatment`, one row, percent |
| Absolute uplift KPI | statistical results, scope=ALL | `absolute_uplift * 100`, suffix pp |
| Relative uplift KPI | statistical results, scope=ALL | `relative_uplift`, percent |
| p-value KPI | statistical results, scope=ALL | `p_value`, at least 5 significant digits |
| Bonus cost KPI | statistical results, scope=ALL | `bonus_cost`, RUB-equivalent |
| Net incremental contribution KPI | statistical results, scope=ALL | `net_incremental_contribution`, RUB-equivalent |
| Reactivation by group | driver metrics | variant vs `SUM(reactivated)/COUNT(driver_id)` |
| Daily rides | daily metrics | day_number vs `SUM(completed_rides)`, color variant |
| Reactivation by country | country metrics | country vs `SUM(reactivated_drivers)/SUM(assigned_users)`, color variant |
| Segment table | country metrics | country, variant, assigned_users, rate, avg rides, revenue, bonus, contribution |
| Uplift interval | statistical results | scope, absolute_uplift, ci_low, ci_high; ALL fixed or one country |
| Economic sensitivity | economic scenarios | bonus_amount vs net_incremental_contribution, color margin_rate |

Do not sum p-values, average subgroup rates without denominators, or sum cumulative counts across days. SUM is appropriate for rides/revenue/cost at their own grain. Weighted rate uses returned drivers / assigned drivers. `daily_metrics.active_drivers` can count the same person on different days; summing it does not yield unique reactivated drivers. Bonus costs must not be joined to individual rides.

### Filters and inference scope

- **Country:** apply to descriptive datasets that have a country field. For country inference, use a separate single-select scope selector on `statistical_results` limited to RU/KZ/BY; select exactly one row. Keep overall cards pinned to ALL.
- **Experiment group:** applies to descriptive charts and table only. Comparing only one arm cannot produce a new treatment effect; do not connect this selector to statistical-results cards.
- **Date:** label it **Assignment date (UTC)** on the driver dataset. It selects full cohorts, preserving seven-day exposure. Daily and calendar aggregate marts have different grains and must not inherit this selector. An optional **Activity date** selector may target only the calendar-activity chart, labelled descriptive.
- Use DataLens selector-to-chart bindings to exclude inferential cards from group/date selectors. Test bindings with a single country, a single arm and a single assignment date before sharing.

The local app follows these same scope rules. Country results are exploratory and unadjusted; segment rankings do not prove heterogeneous effects.

## Optional cloud PostgreSQL route

If a managed PostgreSQL instance is later provided, follow the official DataLens PostgreSQL connection instructions for that service and edition. Use TLS with verified CA, a dedicated read-only database role, and provider-documented network allowlisting. Load only synthetic marts and `statistical_results`, never secrets or local connection files. No cloud database was provisioned by this project and this route is untested.

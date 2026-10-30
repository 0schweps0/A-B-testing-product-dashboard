"""Artifacts derived exclusively from current-run SQL marts and inference."""
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from src.calculate_statistics import conclusion
from src.config import ROOT, MDE


def write_report(groups: pd.DataFrame, results: pd.DataFrame,
                 countries: pd.DataFrame, scenarios: pd.DataFrame) -> None:
    """Publish a calculated Markdown report with honest scope and decision rules."""
    r = results.loc[results.scope == "ALL"].iloc[0].to_dict()
    def table(frame: pd.DataFrame) -> str:
        # Avoid optional tabulate dependency; keep complete numeric values in CSV.
        cols = list(frame.columns)
        rows = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"]*len(cols)) + " |"]
        rows += ["| " + " | ".join(f"{v:.6g}" if isinstance(v, float) else str(v) for v in row) + " |" for row in frame.itertuples(index=False, name=None)]
        return "\n".join(rows)
    segment_effects = results[results.scope != "ALL"].sort_values("absolute_uplift", ascending=False)
    text = f"""# Experiment report — synthetic data only

No real drivers, company data, or production experiment are represented.

## Design and quality

The pre-specified plan is in [analysis_plan.json](analysis_plan.json). Complete randomization fixes equal arm sizes, with seed 42. Analysis uses all assigned drivers, a half-open seven-day window, and mature follow-up as of 2025-05-16 UTC. A 30-day inactivity condition is checked against simulated history. The pipeline validates every source table before a transactional load; PostgreSQL enforces keys and constraints. Source/SQL count and metric parity checks run before export.

## Primary result

{table(groups[["variant", "assigned_users", "reactivated_drivers", "reactivation_rate", "avg_rides_per_assigned_driver", "bonus_cost"]])}

- Absolute uplift: **{r['absolute_uplift']*100:.3f} percentage points**.
- Relative uplift: **{r['relative_uplift']*100:.2f}%**.
- Newcombe 95% confidence interval: **[{r['ci_low']*100:.3f}, {r['ci_high']*100:.3f}] percentage points**.
- Pooled two-proportion two-sided z-test p-value: **{r['p_value']:.6g}**.
- Planned MDE: {MDE*100:.1f} pp. MDE is a design target, not a post-hoc significance threshold; the interval should guide practical interpretation.
- SRM chi-square p-value: {r['srm_p_value']:.6g}. With exact balanced allocation this is structurally 1; it is only a pipeline integrity diagnostic. It cannot detect all randomization errors.

## Secondary outcomes and economics

Welch test for rides per assigned driver (including zeroes): p={r['rides_p_value_exploratory']:.6g}. The unit is a driver, never a ride. Secondary and country tests are exploratory, unadjusted for multiplicity and cannot independently justify rollout.

Revenue is platform commission, **not GMV**. All countries use RUB-equivalent simulated values, with no currency conversion claim. Contribution before incentives is revenue × 40%; fixed costs, fraud, opportunity cost, spillovers and taxes are omitted. Net incremental contribution scales the difference in per-assigned-driver contribution after bonus to the treatment population, correcting unequal arm sizes if present. It is not the treatment arm's total profit.

Net incremental contribution: **{r['net_incremental_contribution']:,.2f} RUB-equivalent**, driver-level Welch 95% CI **[{r['net_ci_low']:,.2f}, {r['net_ci_high']:,.2f}]**. Bonus cost: **{r['bonus_cost']:,.2f}**. The economic interval captures sampling variation under the specified model, not uncertainty about the 40% margin assumption.

Sensitivity analysis ([CSV](../data/dashboard/economic_scenarios.csv)) includes profitable and loss-making assumptions. Behavior is held fixed across bonus scenarios, so reduced-bonus profitability requires a new experiment.

{table(scenarios)}

## Country exploration

{table(segment_effects[["scope", "n_control", "n_treatment", "absolute_uplift", "ci_low", "ci_high", "p_value"]])}

The largest observed country uplift is {segment_effects.iloc[0]['scope']}; rankings are exploratory. No treatment-by-country interaction has been established and smaller strata have less power. Do not infer segment differences from one significant and another nonsignificant test.

## Decision and next experiments

{conclusion(r)}

Test lower incentive amounts and alternative qualification thresholds with a fresh power calculation and a pre-specified primary metric. Measure 28-day sustained activity, cannibalization, fraud and contribution with real unit economics. The current simulation measures seven-day reactivation, not long-term retention; daily activity is repeated activity, not a retained-user cohort estimate.

## Limits and verification

This is one seeded simulation under an assumed data-generating process. No causal claim about actual drivers follows. Follow-up is complete; there is no peeking or seed search. See [validation.json](validation.json) for current-run data checks. The executed notebook provides the same analysis, and automated tests include temporal boundaries and hand-calculated PostgreSQL aggregation fixtures. DataLens assets are ready for manual import; no hosted dashboard is claimed.
"""
    (ROOT / "reports/experiment_report.md").write_text(text)
    (ROOT / "reports/results.json").write_text(json.dumps(r, indent=2, allow_nan=False) + "\n")


def plots(groups: pd.DataFrame, daily: pd.DataFrame, results: pd.DataFrame,
          countries: pd.DataFrame) -> None:
    """Save real computed charts for README and notebook."""
    plt.style.use("seaborn-v0_8-whitegrid")
    palette = ["#475569", "#0284c7"]
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    axes[0, 0].bar(groups.variant, groups.reactivation_rate*100, color=palette)
    axes[0, 0].set(title="7-day reactivation", ylabel="Assigned drivers (%)")
    day = daily.groupby(["day_number", "variant"]).completed_rides.sum().unstack()
    day.plot(ax=axes[0, 1], color=palette)
    axes[0, 1].set(title="Completed rides by day since assignment", xlabel="Day (0–6)", ylabel="Rides")
    countries.pivot(index="country", columns="variant", values="reactivation_rate").mul(100).plot.bar(ax=axes[1, 0], color=palette, rot=0)
    axes[1, 0].set(title="Country exploration", ylabel="Reactivation (%)", xlabel="Country")
    r = results.iloc[0]
    axes[1, 1].errorbar(r.absolute_uplift*100, 0,
                       xerr=[[max(0, (r.absolute_uplift-r.ci_low)*100)], [max(0, (r.ci_high-r.absolute_uplift)*100)]],
                       fmt="o", capsize=6, color=palette[1])
    axes[1, 1].axvline(0, color="gray", linestyle="--")
    axes[1, 1].set(title="Newcombe 95% CI", xlabel="Treatment minus control (pp)", yticks=[])
    fig.suptitle("Driver Reactivation — synthetic experiment", fontsize=16)
    fig.savefig(ROOT / "reports/analysis.png", dpi=160)
    plt.close(fig)

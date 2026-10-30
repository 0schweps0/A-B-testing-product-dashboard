# Experiment report — synthetic data only

No real drivers, company data, or production experiment are represented.

## Design and quality

The pre-specified plan is in [analysis_plan.json](analysis_plan.json). Complete randomization fixes equal arm sizes, with seed 42. Analysis uses all assigned drivers, a half-open seven-day window, and mature follow-up as of 2025-05-16 UTC. A 30-day inactivity condition is checked against simulated history. The pipeline validates every source table before a transactional load; PostgreSQL enforces keys and constraints. Source/SQL count and metric parity checks run before export.

## Primary result

| variant | assigned_users | reactivated_drivers | reactivation_rate | avg_rides_per_assigned_driver | bonus_cost |
| --- | --- | --- | --- | --- | --- |
| control | 4433 | 498 | 0.112339 | 0.342206 | 0 |
| treatment | 4433 | 626 | 0.141214 | 0.445297 | 99000.00 |

- Absolute uplift: **2.887 percentage points**.
- Relative uplift: **25.70%**.
- Newcombe 95% confidence interval: **[1.503, 4.273] percentage points**.
- Pooled two-proportion two-sided z-test p-value: **4.39484e-05**.
- Planned MDE: 2.0 pp. MDE is a design target, not a post-hoc significance threshold; the interval should guide practical interpretation.
- SRM chi-square p-value: 1. With exact balanced allocation this is structurally 1; it is only a pipeline integrity diagnostic. It cannot detect all randomization errors.

## Secondary outcomes and economics

Welch test for rides per assigned driver (including zeroes): p=0.00012381. The unit is a driver, never a ride. Secondary and country tests are exploratory, unadjusted for multiplicity and cannot independently justify rollout.

Revenue is platform commission, **not GMV**. All countries use RUB-equivalent simulated values, with no currency conversion claim. Contribution before incentives is revenue × 40%; fixed costs, fraud, opportunity cost, spillovers and taxes are omitted. Net incremental contribution scales the difference in per-assigned-driver contribution after bonus to the treatment population, correcting unequal arm sizes if present. It is not the treatment arm's total profit.

Net incremental contribution: **-76,500.77 RUB-equivalent**, driver-level Welch 95% CI **[-86,642.43, -66,359.10]**. Bonus cost: **99,000.00**. The economic interval captures sampling variation under the specified model, not uncertainty about the 40% margin assumption.

Sensitivity analysis ([CSV](../data/dashboard/economic_scenarios.csv)) includes profitable and loss-making assumptions. Behavior is held fixed across bonus scenarios, so reduced-bonus profitability requires a new experiment.

| margin_rate | bonus_amount | incremental_revenue | qualifiers | net_incremental_contribution |
| --- | --- | --- | --- | --- |
| 0.2 | 0 | 56248.1 | 330 | 11249.6 |
| 0.2 | 50 | 56248.1 | 330 | -5250.38 |
| 0.2 | 150 | 56248.1 | 330 | -38250.4 |
| 0.2 | 300 | 56248.1 | 330 | -87750.4 |
| 0.4 | 0 | 56248.1 | 330 | 22499.2 |
| 0.4 | 50 | 56248.1 | 330 | 5999.23 |
| 0.4 | 150 | 56248.1 | 330 | -27000.8 |
| 0.4 | 300 | 56248.1 | 330 | -76500.8 |
| 0.6 | 0 | 56248.1 | 330 | 33748.8 |
| 0.6 | 50 | 56248.1 | 330 | 17248.8 |
| 0.6 | 150 | 56248.1 | 330 | -15751.2 |
| 0.6 | 300 | 56248.1 | 330 | -65251.2 |

## Country exploration

| scope | n_control | n_treatment | absolute_uplift | ci_low | ci_high | p_value |
| --- | --- | --- | --- | --- | --- | --- |
| BY | 517 | 522 | 0.0449951 | 0.00468715 | 0.0853763 | 0.0283944 |
| RU | 2914 | 2885 | 0.0301682 | 0.0134655 | 0.0469027 | 0.000401821 |
| KZ | 1002 | 1026 | 0.0162249 | -0.0147467 | 0.0471281 | 0.303508 |

The largest observed country uplift is BY; rankings are exploratory. No treatment-by-country interaction has been established and smaller strata have less power. Do not infer segment differences from one significant and another nonsignificant test.

## Decision and next experiments

Reactivation increased with a statistically significant two-sided result. Do not roll out the current offer: the modeled net contribution is negative, including its 95% interval.

Test lower incentive amounts and alternative qualification thresholds with a fresh power calculation and a pre-specified primary metric. Measure 28-day sustained activity, cannibalization, fraud and contribution with real unit economics. The current simulation measures seven-day reactivation, not long-term retention; daily activity is repeated activity, not a retained-user cohort estimate.

## Limits and verification

This is one seeded simulation under an assumed data-generating process. No causal claim about actual drivers follows. Follow-up is complete; there is no peeking or seed search. See [validation.json](validation.json) for current-run data checks. The executed notebook provides the same analysis, and automated tests include temporal boundaries and hand-calculated PostgreSQL aggregation fixtures. DataLens assets are ready for manual import; no hosted dashboard is claimed.

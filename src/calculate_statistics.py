"""Inference consumes observed driver-level SQL output, never simulator parameters."""
import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.proportion import confint_proportions_2indep, proportions_ztest
from src.config import ALPHA, BONUS, MARGIN_RATE


def compare_proportions(x_control: int, n_control: int, x_treatment: int,
                        n_treatment: int) -> dict[str, float | None]:
    """Pooled two-sided z-test and Newcombe Wilson-score CI for T minus C."""
    if min(n_control, n_treatment) <= 0 or not (0 <= x_control <= n_control and 0 <= x_treatment <= n_treatment):
        raise ValueError("Invalid binomial counts")
    pc, pt = x_control/n_control, x_treatment/n_treatment
    if x_control + x_treatment in (0, n_control + n_treatment):
        p_value = 1.0
    else:
        _, p_value = proportions_ztest([x_treatment, x_control], [n_treatment, n_control], alternative="two-sided")
    low, high = confint_proportions_2indep(x_treatment, n_treatment, x_control, n_control,
                                          compare="diff", method="newcomb", alpha=ALPHA)
    return {"rate_control": pc, "rate_treatment": pt, "absolute_uplift": pt-pc,
            "relative_uplift": pt/pc-1 if pc else None,
            "ci_low": float(low), "ci_high": float(high), "p_value": float(p_value)}


def welch_difference(control: np.ndarray, treatment: np.ndarray) -> dict[str, float]:
    """Driver-level unequal-variance comparison, with finite-sample t interval."""
    c, t = np.asarray(control, dtype=float), np.asarray(treatment, dtype=float)
    if min(len(c), len(t)) < 2 or not (np.isfinite(c).all() and np.isfinite(t).all()):
        raise ValueError("Need at least two finite observations per group")
    difference = float(t.mean() - c.mean())
    vc, vt = c.var(ddof=1)/len(c), t.var(ddof=1)/len(t)
    if vc + vt == 0:
        return {"difference": difference, "ci_low": difference, "ci_high": difference,
                "p_value": 1.0 if difference == 0 else 0.0}
    df = (vc+vt)**2 / (vc**2/(len(c)-1) + vt**2/(len(t)-1))
    se = np.sqrt(vc+vt)
    width = stats.t.ppf(1-ALPHA/2, df) * se
    return {"difference": difference, "ci_low": float(difference-width),
            "ci_high": float(difference+width),
            "p_value": float(2*stats.t.sf(abs(difference/se), df))}


def summarize(frame: pd.DataFrame, scope: str = "ALL") -> dict:
    """Intention-to-treat inference: every assigned driver appears exactly once."""
    if not frame.driver_id.is_unique:
        raise ValueError("Driver metrics must have one row per assignment")
    c = frame[frame.variant == "control"]
    t = frame[frame.variant == "treatment"]
    n_c, n_t = len(c), len(t)
    result = compare_proportions(int(c.reactivated.sum()), n_c, int(t.reactivated.sum()), n_t)
    result.update(scope=scope, n_control=n_c, n_treatment=n_t)
    result["srm_p_value"] = float(stats.chisquare([n_c, n_t]).pvalue)
    rides = welch_difference(c.completed_rides.to_numpy(), t.completed_rides.to_numpy())
    net = welch_difference(c.contribution_after_bonus.to_numpy(), t.contribution_after_bonus.to_numpy())
    result.update(rides_p_value_exploratory=rides["p_value"],
                  net_incremental_contribution=net["difference"]*n_t,
                  net_ci_low=net["ci_low"]*n_t, net_ci_high=net["ci_high"]*n_t,
                  bonus_cost=float(t.bonus_cost.sum()))
    return result


def statistics_by_scope(frame: pd.DataFrame) -> pd.DataFrame:
    """Country tests are exploratory; overall test is the single confirmatory test."""
    return pd.DataFrame([summarize(frame)] + [summarize(g, str(country))
                        for country, g in frame.groupby("country", sort=True)])


def economic_scenarios(frame: pd.DataFrame) -> pd.DataFrame:
    """Sensitivity only: hold behavioral response fixed as margin and bonus vary.

    Changing a bonus could change behavior, so these are not causal forecasts.
    """
    c, t = (frame[frame.variant == v] for v in ["control", "treatment"])
    extra_revenue = (t.revenue.astype(float).mean() - c.revenue.astype(float).mean()) * len(t)
    qualifiers = int((t.bonus_cost.astype(float) > 0).sum())
    return pd.DataFrame([{"margin_rate": margin, "bonus_amount": bonus,
                          "incremental_revenue": extra_revenue,
                          "qualifiers": qualifiers,
                          "net_incremental_contribution": extra_revenue*margin - qualifiers*bonus}
                         for margin in [.2, MARGIN_RATE, .6] for bonus in [0., 50., 150., BONUS]])


def conclusion(result: dict) -> str:
    """Generate a decision using calculated evidence, including uncertainty."""
    significant = result["p_value"] < ALPHA
    primary = ("Reactivation increased with a statistically significant two-sided result."
               if significant and result["absolute_uplift"] > 0 else
               "The primary result does not establish an increase in reactivation."
               if not significant else "Reactivation decreased significantly.")
    if result["net_ci_low"] > 0:
        decision = "Economics support a staged follow-up test; long-term safety and retention still need validation."
    elif result["net_ci_high"] < 0:
        decision = "Do not roll out the current offer: the modeled net contribution is negative, including its 95% interval."
    else:
        decision = "Do not roll out yet: the net-contribution interval includes zero."
    return primary + " " + decision

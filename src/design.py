"""Prospective planning, evaluated before generating outcomes."""
import math
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize
from src.config import ALPHA, BASELINE, MDE, POWER


def sample_size(baseline: float = BASELINE, mde: float = MDE,
                alpha: float = ALPHA, power: float = POWER) -> int:
    """Per-arm size: two independent proportions, two-sided normal approximation."""
    if not 0 < baseline < baseline + mde < 1:
        raise ValueError("Require 0 < baseline < baseline + MDE < 1")
    effect = abs(proportion_effectsize(baseline + mde, baseline))
    return math.ceil(NormalIndPower().solve_power(effect, alpha=alpha, power=power,
                                                 ratio=1, alternative="two-sided"))


def plan() -> dict:
    """Return the pre-specified analysis plan, independent of generated data."""
    n = sample_size()
    return {"baseline": BASELINE, "mde_absolute": MDE, "alpha": ALPHA,
            "power": POWER, "required_per_arm": n, "total_assigned": 2*n,
            "allocation": "complete randomization, fixed equal arm sizes",
            "H0": "p_treatment = p_control", "H1": "p_treatment != p_control",
            "primary": "at least one completed ride in [assignment, assignment + 7 days)",
            "secondary": ["rides per assigned driver", "platform revenue", "bonus cost",
                          "contribution after bonus"],
            "analysis": "intention-to-treat; two-sided pooled z-test; Newcombe 95% CI",
            "segments": "exploratory country comparisons; no subgroup rollout claims",
            "economic_model": "revenue is platform commission in RUB-equivalent; 40% contribution before bonuses",
            "as_of": "2025-05-16T00:00:00Z"}

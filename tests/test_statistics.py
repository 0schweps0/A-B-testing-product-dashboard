import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm, ttest_ind
from src.calculate_statistics import compare_proportions, welch_difference, summarize


def test_proportion_test_reference():
    r = compare_proportions(120, 1000, 140, 1000)
    pooled = 260/2000
    expected_z = .02 / np.sqrt(pooled*(1-pooled)*(.001+.001))
    assert r["p_value"] == pytest.approx(2*norm.sf(abs(expected_z)))
    assert r["absolute_uplift"] == pytest.approx(.02)
    assert r["relative_uplift"] == pytest.approx(1/6)
    assert r["ci_low"] < .02 < r["ci_high"]
    reverse = compare_proportions(140, 1000, 120, 1000)
    assert reverse["ci_low"] == pytest.approx(-r["ci_high"])
    assert reverse["p_value"] == pytest.approx(r["p_value"])


def test_newcombe_interval_reference():
    # Independent Wilson interval construction (Newcombe method 10).
    r = compare_proportions(120, 1000, 140, 1000)
    z = norm.ppf(.975)
    def wilson(p):
        center = (p + z*z/2000)/(1+z*z/1000)
        width = z*np.sqrt(p*(1-p)/1000 + z*z/(4*1000**2))/(1+z*z/1000)
        return center-width, center+width
    lc, uc = wilson(.12)
    lt, ut = wilson(.14)
    assert r["ci_low"] == pytest.approx(.02-np.sqrt((.14-lt)**2+(uc-.12)**2))
    assert r["ci_high"] == pytest.approx(.02+np.sqrt((ut-.14)**2+(.12-lc)**2))


def test_degenerate_proportions():
    r = compare_proportions(0, 100, 0, 100)
    assert r["p_value"] == 1
    assert r["relative_uplift"] is None
    assert r["ci_low"] < 0 < r["ci_high"]
    with pytest.raises(ValueError):
        compare_proportions(0, 0, 1, 2)


def test_welch_reference():
    c, t = np.array([0, 0, 1, 4, 6]), np.array([0, 2, 3, 4, 15, 16])
    result = welch_difference(c, t)
    reference = ttest_ind(t, c, equal_var=False)
    assert result["p_value"] == pytest.approx(reference.pvalue)
    assert result["ci_low"] == pytest.approx(reference.confidence_interval().low)
    assert result["ci_high"] == pytest.approx(reference.confidence_interval().high)


def test_economics_unequal_groups_and_zeroes():
    # C mean contribution=10; T mean after incentive=20 => 3*(20-10)=30.
    frame = pd.DataFrame({"driver_id": [1, 2, 3, 4, 5], "variant": ["control"]*2+["treatment"]*3,
                          "reactivated": [0, 1, 0, 1, 1], "completed_rides": [0, 1, 0, 1, 3],
                          "contribution_after_bonus": [0., 20., 0., 20., 40.],
                          "bonus_cost": [0., 0., 0., 0., 300.]})
    result = summarize(frame)
    assert result["rate_control"] == .5
    assert result["rate_treatment"] == pytest.approx(2/3)
    assert result["net_incremental_contribution"] == pytest.approx(30)
    assert result["bonus_cost"] == 300
    with pytest.raises(ValueError, match="one row"):
        summarize(pd.concat([frame, frame.iloc[[0]]]))

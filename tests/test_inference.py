import numpy as np
import pandas as pd
import pytest

from quantrail.stats.inference import circular_indices, cscv_pbo, deflated_sharpe, holm, paired_bootstrap


def test_identical_paths_share_indices_and_have_zero_difference():
    r = np.sin(np.arange(100)) * 0.01
    frame = pd.DataFrame({"B0": r, "S1": r, "S2": r}, index=pd.bdate_range("2020-01-01", periods=100))
    result = paired_bootstrap(frame, block_length=10, resamples=200)
    assert (result[["annual_log_difference", "ci_lower_log", "ci_upper_log"]] == 0).all().all()
    assert (result.holm_p == 1).all()
    pd.testing.assert_frame_equal(result, paired_bootstrap(frame, block_length=10, resamples=200))
    ix = circular_indices(100, 10, 200)
    np.testing.assert_array_equal(frame.B0.to_numpy()[ix], frame.S1.to_numpy()[ix])
    # Each block is 10 consecutive (circular) days.
    np.testing.assert_array_equal(np.diff(ix.reshape(200, 10, 10), axis=2) % 100, np.ones((200, 10, 9)))


def test_constant_log_difference_annualises_with_252():
    r = np.sin(np.arange(100)) * 0.01
    frame = pd.DataFrame({"B0": r, "S1": np.expm1(np.log1p(r) + 0.001)},
                         index=pd.bdate_range("2020-01-01", periods=100))
    out = paired_bootstrap(frame, block_length=20, resamples=200).loc["S1"]
    assert out.annual_log_difference == pytest.approx(0.252)
    assert out.growth_difference == pytest.approx(np.expm1(0.252))
    assert out.ci_lower_log == pytest.approx(0.252)
    assert out.p_value == 0


def test_holm_known_answer():
    # Sorted p: .005,.01,.03,.04,.2 -> x5,x4,x3,x2,x1 = .025,.04,.09,.08,.2 -> monotone .025,.04,.09,.09,.2
    np.testing.assert_allclose(holm([0.01, 0.04, 0.03, 0.2, 0.005]), [0.04, 0.09, 0.09, 0.2, 0.025])


def test_dsr_zero_sharpe_is_one_half_and_more_trials_raise_the_bar():
    r = np.tile([-0.01, 0.01], 100)
    assert deflated_sharpe(r, cross_trial_variance=0, trials=5)["dsr"] == 0.5
    a = deflated_sharpe(r + 0.001, cross_trial_variance=0.001, trials=5)
    b = deflated_sharpe(r + 0.001, cross_trial_variance=0.001, trials=82)
    assert a["threshold_daily_sharpe"] < b["threshold_daily_sharpe"]
    assert a["dsr"] > b["dsr"]


def test_pbo_zero_for_a_stable_winner_with_all_balanced_splits():
    oscillation = np.tile([-0.01, 0.01], 32)
    frame = pd.DataFrame({"best": oscillation + 0.003, "middle": oscillation + 0.002,
                          "worst": oscillation + 0.001})
    out = cscv_pbo(frame)
    assert out["pbo"] == 0
    assert out["splits"] == 12870  # C(16, 8)
    assert sum(out["block_sizes"]) == 64


def test_pbo_one_for_a_full_rank_reversal():
    noise = np.tile([-0.01, 0.01], 16)
    a = noise + np.repeat([0.003, -0.003], 16)
    b = noise - np.repeat([0.003, -0.003], 16)
    assert cscv_pbo(pd.DataFrame({"a": a, "b": b}), segments=2)["pbo"] == 1


def test_invalid_inputs_fail_loudly():
    with pytest.raises(ValueError):
        paired_bootstrap(pd.DataFrame({"B0": [0, -1], "S1": [0, 0.1]}), block_length=1)
    with pytest.raises(ValueError):
        deflated_sharpe([0, 0], cross_trial_variance=0, trials=5)

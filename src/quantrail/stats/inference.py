"""Inference over aligned daily returns of several strategies and one baseline.

The bootstrap resamples realised strategy paths; it is conditional inference, not a
market simulator. DSR follows Bailey and Lopez de Prado (2014) with a caller-supplied,
fixed cross-trial variance of unannualised daily Sharpe ratios. Moments are empirical
central moments (ordinary, not excess, kurtosis). CSCV uses all C(S, S/2) training
subsets of S contiguous blocks; ties use average out-of-sample ranks and the first
declared candidate for in-sample ties. None of these estimates future profitability.
"""

from __future__ import annotations

import math
from itertools import combinations
from statistics import NormalDist

import numpy as np
import pandas as pd


def _matrix(returns):
    a = np.asarray(returns, dtype=float)
    if a.ndim != 2 or len(a) < 2 or not np.isfinite(a).all() or (a <= -1).any():
        raise ValueError('Need finite aligned daily returns, each greater than -1.')
    return a


def circular_indices(n, block_length, resamples, seed=0):
    """One index array is shared by all columns, including the baseline."""
    if min(n, block_length, resamples) <= 0:
        raise ValueError('Sample, block and resample counts must be positive.')
    starts = np.random.default_rng(seed).integers(0, n, (resamples, math.ceil(n / block_length)))
    return ((starts[..., None] + np.arange(block_length)) % n).reshape(resamples, -1)[:, :n]


def holm(p_values):
    p = np.asarray(p_values, dtype=float)
    if p.ndim != 1 or not len(p) or not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError('p-values must be a nonempty vector in [0, 1].')
    order = np.argsort(p, kind='stable')
    adjusted = np.minimum(1, np.maximum.accumulate(p[order] * np.arange(len(p), 0, -1)))
    result = np.empty_like(p)
    result[order] = adjusted
    return result


def paired_bootstrap(returns, *, baseline='B0', block_length, resamples=10000, seed=0):
    """Two-sided percentile CI and centered p-value, then Holm across challengers."""
    if (not isinstance(returns, pd.DataFrame) or not returns.index.is_unique
            or not returns.index.is_monotonic_increasing):
        raise ValueError('Returns must have unique increasing shared dates.')
    a = _matrix(returns)
    base = returns.columns.get_loc(baseline)
    positions = [i for i in range(a.shape[1]) if i != base]
    if not positions:
        raise ValueError('At least one challenger is required.')
    diff = np.log1p(a[:, positions]) - np.log1p(a[:, [base]])
    theta = diff.mean(axis=0) * 252
    indices = circular_indices(len(a), block_length, resamples, seed)
    # Batches bound memory while preserving the single shared index draw.
    samples = np.concatenate([diff[indices[i:i + 128]].mean(axis=1) * 252
                              for i in range(0, resamples, 128)])
    lower, upper = np.quantile(samples, [0.025, 0.975], axis=0)
    p = (np.abs(samples - theta) >= np.abs(theta)).mean(axis=0)
    return pd.DataFrame({'annual_log_difference': theta, 'growth_difference': np.expm1(theta),
                         'ci_lower_log': lower, 'ci_upper_log': upper,
                         'ci_lower_growth': np.expm1(lower), 'ci_upper_growth': np.expm1(upper),
                         'p_value': p, 'holm_p': holm(p)},
                        index=returns.columns[positions])


def daily_sharpe(returns):
    r = np.asarray(returns, dtype=float)
    if r.ndim != 1 or len(r) < 2 or not np.isfinite(r).all():
        raise ValueError('Need a finite daily return series.')
    std = r.std(ddof=1)
    if std <= 0:
        raise ValueError('Sharpe is undefined for zero variance.')
    return float(r.mean() / std)


def deflated_sharpe(returns, *, cross_trial_variance, trials):
    """DSR with a supplied, fixed variance of unannualized daily Sharpe ratios."""
    if trials < 2 or cross_trial_variance < 0 or not math.isfinite(cross_trial_variance):
        raise ValueError('DSR requires N >= 2 and finite nonnegative Sharpe variance.')
    r = np.asarray(returns, dtype=float)
    sr = daily_sharpe(r)
    centered = r - r.mean()
    m2 = np.mean(centered ** 2)
    skew = float(np.mean(centered ** 3) / m2 ** 1.5)
    kurtosis = float(np.mean(centered ** 4) / m2 ** 2)
    gamma = 0.5772156649015329
    normal = NormalDist()
    threshold = math.sqrt(cross_trial_variance) * (
        (1 - gamma) * normal.inv_cdf(1 - 1 / trials)
        + gamma * normal.inv_cdf(1 - 1 / (trials * math.e)))
    denominator = 1 - skew * sr + (kurtosis - 1) * sr ** 2 / 4
    if denominator <= 0:
        raise ValueError('DSR sampling variance is not positive.')
    z = (sr - threshold) * math.sqrt(len(r) - 1) / math.sqrt(denominator)
    return {'dsr': normal.cdf(z), 'daily_sharpe': sr, 'threshold_daily_sharpe': threshold,
            'cross_trial_variance': cross_trial_variance, 'trials': trials,
            'skewness': skew, 'kurtosis': kurtosis, 'observations': len(r)}


def cscv_pbo(returns, *, segments=16):
    """CSCV by contiguous blocks, using daily Sharpe and all balanced splits.

    np.array_split keeps every observation, with block sizes differing by at most
    one. IS ties select the first declared candidate; OOS ties use average rank.
    PBO counts logit <= 0 (at or below the OOS median).
    """
    a = _matrix(returns)
    if segments < 2 or segments % 2 or len(a) < segments * 2 or a.shape[1] < 2:
        raise ValueError('CSCV requires even segments, >=2 observations per block and >=2 candidates.')
    blocks = np.array_split(a, segments)
    counts = np.array([len(b) for b in blocks])
    sums = np.array([b.sum(axis=0) for b in blocks])
    squares = np.array([(b ** 2).sum(axis=0) for b in blocks])
    subsets = np.array(list(combinations(range(segments), segments // 2)))

    def sharpe(n, total, sq):
        variance = (sq - total ** 2 / n[:, None]) / (n[:, None] - 1)
        if (variance <= 0).any():
            raise ValueError('CSCV contains a zero-variance candidate/subset.')
        return (total / n[:, None]) / np.sqrt(variance)

    n = counts[subsets].sum(axis=1)
    sums_is = sums[subsets].sum(axis=1)
    squares_is = squares[subsets].sum(axis=1)
    ins = sharpe(n, sums_is, squares_is)
    outs = sharpe(len(a) - n, sums.sum(axis=0) - sums_is, squares.sum(axis=0) - squares_is)
    winners = ins.argmax(axis=1)
    chosen = outs[np.arange(len(winners)), winners]
    ranks = (outs < chosen[:, None]).sum(axis=1) + ((outs == chosen[:, None]).sum(axis=1) + 1) / 2
    omega = ranks / (a.shape[1] + 1)
    logits = np.log(omega / (1 - omega))
    return {'pbo': float((logits <= 0).mean()), 'splits': len(subsets), 'segments': segments,
            'candidates': list(returns.columns) if hasattr(returns, 'columns') else list(range(a.shape[1])),
            'block_sizes': counts.tolist(),
            'is_tie_splits': int(((ins == ins.max(axis=1)[:, None]).sum(axis=1) > 1).sum()),
            'oos_median_ties': int((logits == 0).sum()),
            'logit_quantiles': np.quantile(logits, [0, .25, .5, .75, 1]).tolist()}

"""Performance metrics with fixed, documented formulas.

Inputs are a daily NAV series (indexed by date) and the starting capital; the first
day's return is measured against capital. BRAIN-style metrics additionally need the
traded value per day. All functions are pure and deterministic.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252
FITNESS_TURNOVER_FLOOR = 0.125


def _nav(nav) -> pd.Series:
    if not isinstance(nav, pd.Series) or nav.empty:
        raise ValueError("nav must be a non-empty pandas Series indexed by date")
    if not isinstance(nav.index, pd.DatetimeIndex) or not nav.index.is_monotonic_increasing:
        raise ValueError("nav must have an increasing DatetimeIndex")
    values = nav.to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("nav must be finite and positive")
    return nav.astype(float)


def daily_returns(nav, capital) -> pd.Series:
    nav = _nav(nav)
    previous = nav.shift(1)
    previous.iloc[0] = float(capital)
    return nav / previous - 1


def cagr(nav, capital) -> float:
    """(final / capital) ** (365.25 / calendar days between first and last date) - 1."""
    nav = _nav(nav)
    days = (nav.index[-1] - nav.index[0]).days
    if days <= 0:
        raise ValueError("CAGR needs at least two distinct dates")
    return float((nav.iloc[-1] / capital) ** (365.25 / days) - 1)


def annual_volatility(nav, capital) -> float:
    return float(daily_returns(nav, capital).std(ddof=1) * np.sqrt(TRADING_DAYS))


def sharpe(nav, capital, risk_free_daily=0.0) -> float:
    excess = daily_returns(nav, capital) - risk_free_daily
    return float(excess.mean() / excess.std(ddof=1) * np.sqrt(TRADING_DAYS))


def max_drawdown(nav, capital) -> float:
    """Most negative fall from a running peak, starting capital included (e.g. -0.34)."""
    path = pd.concat([pd.Series([float(capital)]), _nav(nav).reset_index(drop=True)])
    return float((path / path.cummax() - 1).min())


def longest_underwater_days(nav, capital) -> int:
    """Longest calendar-day stretch spent below a previous peak."""
    nav = _nav(nav)
    peak, start, longest = float(capital), None, 0
    for day, value in nav.items():
        if value >= peak:
            peak, start = value, None
        else:
            start = start or day
            longest = max(longest, (day - start).days)
    return longest


def yearly_returns(nav, capital) -> pd.Series:
    r = daily_returns(nav, capital)
    return (1 + r).groupby(r.index.year).prod() - 1


def summary(nav, capital) -> dict:
    return {
        "start": f"{_nav(nav).index[0]:%Y-%m-%d}", "end": f"{nav.index[-1]:%Y-%m-%d}",
        "final_nav": float(nav.iloc[-1]), "cagr": cagr(nav, capital),
        "annual_volatility": annual_volatility(nav, capital), "sharpe": sharpe(nav, capital),
        "max_drawdown": max_drawdown(nav, capital),
        "longest_underwater_days": longest_underwater_days(nav, capital),
        "yearly_returns": {str(k): float(v) for k, v in yearly_returns(nav, capital).items()},
    }


def brain_style(nav, traded_value, capital) -> dict:
    """WorldQuant BRAIN-style summary with the previous close NAV as book size.

    - Sharpe   = mean(daily return) / std(daily return) * sqrt(252)
    - Turnover = mean(daily traded value / book size)
    - Returns  = mean(daily return) * 252
    - Fitness  = Sharpe * sqrt(|Returns| / max(Turnover, 0.125))
    - Margin   = total PnL / total traded value, in 1/10,000 (permyriad)
    - Drawdown = largest peak-to-trough fall, as a positive fraction

    traded_value: Series of absolute traded value per date (missing dates mean zero).
    Margin is NaN when nothing traded.
    """
    nav = _nav(nav)
    book = nav.shift(1).fillna(float(capital))
    pnl = nav - book
    r = pnl / book
    traded = pd.Series(traded_value, dtype=float).reindex(nav.index, fill_value=0.0)
    s = r.mean() / r.std(ddof=1) * np.sqrt(TRADING_DAYS)
    turnover = (traded / book).mean()
    returns = r.mean() * TRADING_DAYS
    total = traded.sum()
    return {
        "sharpe": float(s),
        "turnover": float(turnover),
        "fitness": float(s * np.sqrt(abs(returns) / max(turnover, FITNESS_TURNOVER_FLOOR))),
        "returns": float(returns),
        "drawdown": -max_drawdown(nav, capital),
        "margin_permyriad": float(pnl.sum() / total * 1e4) if total else float("nan"),
    }


def brain_style_by_year(nav, traded_value, capital) -> pd.DataFrame:
    """brain_style per calendar year, each year starting from the previous year-end NAV."""
    nav = _nav(nav)
    traded = pd.Series(traded_value, dtype=float).reindex(nav.index, fill_value=0.0)
    rows = {}
    for year, part in nav.groupby(nav.index.year):
        before = nav[nav.index < part.index[0]]
        start = float(before.iloc[-1]) if len(before) else float(capital)
        rows[year] = brain_style(part, traded[part.index], start)
    return pd.DataFrame(rows).T

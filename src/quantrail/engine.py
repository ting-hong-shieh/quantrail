"""Daily target-weight simulation of one instrument plus cash on the QuantRail ledger.

Execution model:
- A target decided at the close of day t executes at the next tradable session's raw
  open with adverse slippage in the fill price; units change only at the fill.
- Untradable sessions produce NO_FILL with a reason; the target stays pending until a
  tradable session or until a newer decision replaces it (REPLACED).
- Cash settles on the market's settlement date at the end of that day; buying power
  never counts unsettled receivables.
- Cash dividends: entitlement before the ex-date open on units held at the prior close;
  the receivable becomes cash at the end of the payment date and is reinvested buy-only
  toward the last effective target, using at most the paid amount.
- A decision is skipped (BAND_SKIP) when |target - weight at the decision close| is below
  `no_trade_band`; the initial build is never banded.

Input tables (one instrument):
- prices: session_date, open, close, quote_valid
- calendar: session_date, asset_tradable, reason
- actions: action_id, action_type ("CASH_DISTRIBUTION" | "SPLIT"), ex_date, payment_date,
  cash_per_entitled_unit, effective_date, split_new_per_old
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

import pandas as pd

from .accounting.ledger import Fill, Ledger

D = Decimal


def _price(value) -> Decimal:
    return D(str(round(float(value), 6)))


@dataclass
class Result:
    daily: pd.DataFrame
    orders: pd.DataFrame
    events: pd.DataFrame
    meta: dict = field(default_factory=dict)


def run_target_weights(*, instrument, costs, settle, prices, calendar, actions, start, end, capital,
                       initial_target, decisions=None, no_trade_band=0.0, slippage_bps=0.0,
                       label="run") -> Result:
    """Simulate from the first session >= start through end.

    costs: object with fees(instrument, side, quantity, price, day) -> (commission, tax) and,
        optionally, commission_rate (used only for the first affordability estimate).
    settle: callable(trade_date) -> settlement date.
    """
    sessions = pd.DatetimeIndex(calendar["session_date"])
    days = sessions[(sessions >= pd.Timestamp(start)) & (sessions <= pd.Timestamp(end))]
    if len(days) == 0:
        raise ValueError("No sessions in the requested window.")
    decisions = (decisions if decisions is not None
                 else pd.Series(dtype=float, index=pd.DatetimeIndex([]))).sort_index()
    if ((decisions < 0) | (decisions > 1)).any() or not 0 <= initial_target <= 1:
        raise ValueError("Target weights must be within [0, 1]; no leverage or shorting.")
    currency = instrument.quote_currency
    slip = D(str(slippage_bps)) / D("10000")
    rate = D(str(getattr(costs, "commission_rate", 0)))
    quotes = prices.set_index("session_date")
    tradable = calendar.set_index("session_date")

    splits = {r["effective_date"]: r for _, r in actions[actions["action_type"] == "SPLIT"].iterrows()}
    dividend_rows = actions[actions["action_type"] == "CASH_DISTRIBUTION"]
    dividends = {r["ex_date"]: r for _, r in dividend_rows.iterrows()}

    ledger = Ledger({currency: capital})
    pending = float(initial_target)
    consumed_through = pd.Timestamp(start) - pd.Timedelta(1, unit="D")
    effective_target = None
    last_close = None
    reinvest_budget = D("0")
    daily, orders, events = [], [], []

    for day in days:
        d = day.date()
        units_before = ledger.position(instrument.id)
        entitled = D("0")
        # 1. Events effective before the open.
        if day in splits:
            row = splits[day]
            ratio = D(str(row["split_new_per_old"]))
            ledger.split(instrument, ratio, d)
            if last_close is not None:
                last_close /= ratio
            events.append({"date": day, "type": "SPLIT",
                           "detail": f"{units_before} -> {ledger.position(instrument.id)} units"})
            units_before = ledger.position(instrument.id)
        if day in dividends:
            row = dividends[day]
            per_unit = _price(row["cash_per_entitled_unit"])
            entitled = ledger.entitle_cash_dividend(instrument, per_unit, d, row["payment_date"].date(),
                                                    str(row["action_id"]))
            events.append({"date": day, "type": "DIV_ENTITLEMENT",
                           "detail": f"{units_before} units x {per_unit} = {entitled}"})
        # 2. Decisions made at earlier closes become pending for this open.
        new = decisions[(decisions.index > consumed_through) & (decisions.index < day)]
        for decided_at, target in new.items():
            consumed_through = decided_at
            close_weight = daily[-1]["weight"] if daily and daily[-1]["date"] == decided_at else None
            banded = close_weight is not None and abs(target - close_weight) < no_trade_band - 1e-12
            if no_trade_band and banded:
                events.append({"date": day, "type": "BAND_SKIP",
                               "detail": f"target {target:.4f} vs close weight {close_weight:.4f}"})
                continue
            if pending is not None:
                events.append({"date": day, "type": "REPLACED", "detail": f"pending {pending} -> {target}"})
            pending = float(target)
        reinvesting = pending is None and reinvest_budget > 0 and effective_target is not None
        # 3. Trade at the open if possible.
        status = tradable.loc[day] if day in tradable.index else None
        quote = quotes.loc[day] if day in quotes.index else None
        can_trade = (status is not None and bool(status["asset_tradable"])
                     and quote is not None and bool(quote["quote_valid"]))
        commission = tax = slippage = D("0")
        open_price = _price(quote["open"]) if can_trade else None
        if pending is not None or reinvesting:
            target = pending if pending is not None else effective_target
            if not can_trade:
                reason = (status["reason"] if status is not None and status["reason"]
                          else "RAW_PRICE_MISSING" if quote is None else "INVALID_QUOTE")
                events.append({"date": day, "type": "NO_FILL", "detail": reason})
            else:
                snap = ledger.snapshot(currency)
                nav_open = units_before * open_price + snap.net
                desired = instrument.floor_quantity(D(str(target)) * nav_open / open_price)
                delta = desired - units_before
                if reinvesting:
                    delta = max(delta, D("0"))  # buy-only: never sell because of a dividend
                side = "BUY" if delta > 0 else "SELL"
                fill_price = (open_price * (1 + slip if delta > 0 else 1 - slip)).quantize(D("0.0001"))
                quantity = abs(delta)
                if delta > 0:
                    power = ledger.buying_power(currency)
                    if reinvesting:
                        power = min(power, reinvest_budget)
                    estimate = instrument.floor_quantity(power / (fill_price * (1 + rate)))
                    quantity = instrument.floor_quantity(min(quantity, estimate))
                    while quantity > 0:
                        c, t = costs.fees(instrument, "BUY", quantity, fill_price, d)
                        if quantity * fill_price + c + t <= power:
                            break
                        quantity = instrument.floor_quantity(quantity - instrument.quantity_step)
                    if quantity < delta:
                        events.append({"date": day, "type": "CASH_CONSTRAINED",
                                       "detail": f"target {delta} filled {quantity} units"})
                if quantity > 0:
                    commission, tax = costs.fees(instrument, side, quantity, fill_price, d)
                    ledger.book_fill(Fill(instrument, side, quantity, fill_price, d, settle(d),
                                          commission, tax, f"{label}-{d:%Y%m%d}"))
                    # Signed, so tick rounding in the trader's favour is not booked as a cost.
                    per_unit = fill_price - open_price if side == "BUY" else open_price - fill_price
                    slippage = per_unit * quantity
                    orders.append({"date": day, "side": side, "quantity": float(quantity),
                                   "open": float(open_price), "fill_price": float(fill_price),
                                   "target_weight": target, "reinvestment": reinvesting,
                                   "commission": float(commission), "tax": float(tax),
                                   "slippage": float(slippage)})
                elif delta != 0:
                    events.append({"date": day, "type": "NO_FILL", "detail": "INSUFFICIENT_CASH"})
                if pending is not None:
                    effective_target, pending = pending, None
                reinvest_budget = D("0")
        # 4. End of day: settlements; paid dividends become reinvestable cash.
        for obligation in ledger.settle_through(d):
            if obligation.reference.startswith("div:"):
                events.append({"date": day, "type": "DIV_PAYMENT", "detail": str(obligation.amount)})
                reinvest_budget += obligation.amount
        # 5. Valuation at the close (last valid close on untradable days, flagged).
        close = _price(quote["close"]) if can_trade else last_close
        if close is None:
            raise ValueError(f"No valid price to value the position on {d}.")
        snap = ledger.snapshot(currency)
        held = ledger.position(instrument.id)
        nav = held * close + snap.net
        reference = last_close if last_close is not None else close
        overnight = units_before * ((open_price if can_trade else close) - reference)
        intraday = held * (close - open_price) if can_trade else D("0")
        daily.append({"date": day, "units": float(held), "close_used": float(close),
                      "valuation_stale": not can_trade, "settled_cash": float(snap.settled),
                      "receivable": float(snap.receivable), "payable": float(snap.payable),
                      "nav": float(nav), "weight": float(held * close / nav) if nav else float("nan"),
                      "effective_target": effective_target, "pending_target": pending,
                      "overnight_pnl": float(overnight), "intraday_pnl": float(intraday),
                      "dividend_entitled": float(entitled), "commission": float(commission),
                      "tax": float(tax), "slippage": float(slippage)})
        last_close = close

    daily = pd.DataFrame(daily).set_index("date")
    previous = daily["nav"].shift(1).fillna(float(capital))
    explained = (daily["overnight_pnl"] + daily["intraday_pnl"] + daily["dividend_entitled"]
                 - daily["commission"] - daily["tax"] - daily["slippage"])
    daily["identity_residual"] = daily["nav"] - previous - explained
    return Result(daily, pd.DataFrame(orders), pd.DataFrame(events),
                  {"instrument": instrument.id, "currency": currency, "label": label})

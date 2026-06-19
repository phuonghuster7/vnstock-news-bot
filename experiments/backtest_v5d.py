"""
Phase 5d: Backtest Nâng cao - Bước cuối
- Sử dụng Signal từ V4 (Pure momentum).
- KHÔNG dùng Market Regime Filter.
- KHÔNG dùng ATR Stop-loss.
- Fundamental Pre-filter: Loại PE > 40, PE < 0, PB > 10, ROE < 0.08.
- TOPK = 5.
"""
import os
import pandas as pd
import numpy as np
import qlib
from qlib.data import D
import pickle

# ─── Constants ───────────────────────────────────────────────────────────────
QLIB_DIR     = os.path.expanduser("~/.qlib/qlib_data/vn_data")
TEST_START   = "2024-01-02"
TEST_END     = "2026-06-01"
TOPK         = 5
COMMISSION   = 0.0015          # 0.15% mỗi chiều
INIT_CAPITAL = 1_000_000_000   # 1 tỷ VND
T_PLUS       = 2               # T+2 settlement

# ─── 1. Fundamental Filter ───────────────────────────────────────────────────
class FundamentalFilter:
    RULES = {
        "pe_max":  40.0,
        "pe_min":   0.0,
        "roe_min":  0.08,
        "pb_max":  10.0,
    }
    def __init__(self):
        # Fetch fundamental features from Qlib (since they were saved in V5)
        self.fund_df = D.features(D.instruments("vn30"), ["$pe", "$roe", "$pb"], start_time=TEST_START, end_time=TEST_END)
        self.fund_df.columns = ["pe", "roe", "pb"]

    def filter_universe(self, universe: list, date: pd.Timestamp) -> list:
        try:
            # We use xs to get cross-section for a specific date
            day_data = self.fund_df.xs(date, level="datetime")
        except KeyError:
            return universe
            
        filtered = []
        for sym in universe:
            if sym not in day_data.index:
                filtered.append(sym)
                continue
                
            row = day_data.loc[sym]
            pe  = row.get("pe", np.nan)
            roe = row.get("roe", np.nan)
            pb  = row.get("pb", np.nan)
            
            if not np.isnan(pe) and (pe <= self.RULES["pe_min"] or pe > self.RULES["pe_max"]):
                continue
            if not np.isnan(roe) and roe < self.RULES["roe_min"]:
                continue
            if not np.isnan(pb) and pb > self.RULES["pb_max"]:
                continue
                
            filtered.append(sym)
        return filtered

# ─── Backtest Logic ──────────────────────────────────────────────────────────
def load_price_map(symbols, start, end):
    raw = D.features(symbols, ["$close"], start_time=start, end_time=end)
    raw.columns = ["close"]
    raw = raw.reset_index()
    raw["datetime"] = pd.to_datetime(raw["datetime"])
    price_map = {}
    for row in raw.itertuples(index=False):
        price_map[(row.datetime, row.instrument)] = row.close
    return price_map

def run_backtest_v5d(pred_df: pd.DataFrame, price_map: dict, test_dates: list):
    holdings     = {}     # {sym: shares}
    cash         = float(INIT_CAPITAL)
    pending_cash = []     # [(settle_date, amount)]
    equity_curve = []     # [(date, nav)]
    trade_log    = []
    
    fund_filter = FundamentalFilter()

    def get_price(ts, sym):
        return price_map.get((ts, sym), np.nan)

    def flush_pending(today):
        nonlocal cash
        remaining = []
        for settle_date, amt in pending_cash:
            if settle_date <= today:
                cash += amt
            else:
                remaining.append((settle_date, amt))
        pending_cash.clear()
        pending_cash.extend(remaining)

    for i, date in enumerate(test_dates):
        flush_pending(date)
        
        mask = pred_df["datetime"] == date
        day_scores = pred_df.loc[mask].set_index("instrument")["score"]
        
        target_syms = set()
        
        if not day_scores.empty:
            # 1. Apply Fundamental Filter
            valid_symbols = fund_filter.filter_universe(day_scores.index.tolist(), date)
            day_scores = day_scores[day_scores.index.isin(valid_symbols)]
            
            # 2. Pick TOPK
            valid = day_scores.dropna().sort_values(ascending=False)
            target_syms = set(valid.index[:TOPK].tolist())
            
        current_syms = set(holdings.keys())

        # Bán (Những mã rớt khỏi TOPK)
        for sym in list(current_syms - target_syms):
            price = get_price(date, sym)
            if np.isnan(price) or price <= 0:
                continue
            shares = holdings.pop(sym)
            proceeds = shares * price * (1 - COMMISSION)
            settle_idx = min(i + T_PLUS, len(test_dates) - 1)
            pending_cash.append((test_dates[settle_idx], proceeds))
            trade_log.append((date, "SELL", sym, shares, price, proceeds))

        # Mua mới các mã trong TOPK
        buy_syms = list(target_syms - set(holdings.keys()))
        if buy_syms:
            per_sym = cash / len(buy_syms)
            for sym in buy_syms:
                price = get_price(date, sym)
                if np.isnan(price) or price <= 0:
                    continue
                cost_per_share = price * (1 + COMMISSION)
                lot_size = 100
                shares = int((per_sym / cost_per_share) // lot_size) * lot_size
                if shares <= 0:
                    continue
                total_cost = shares * cost_per_share
                if total_cost > cash:
                    shares = int((cash / cost_per_share) // lot_size) * lot_size
                    total_cost = shares * cost_per_share
                if shares <= 0:
                    continue
                cash -= total_cost
                holdings[sym] = holdings.get(sym, 0) + shares
                
                trade_log.append((date, "BUY", sym, shares, price, total_cost))

        # Calculate NAV
        hv = sum(shares * get_price(date, sym) for sym, shares in holdings.items() if not np.isnan(get_price(date, sym)))
        pending_total = sum(amt for _, amt in pending_cash)
        equity_curve.append((date, cash + hv + pending_total))

    return equity_curve, trade_log

def compute_tearsheet(equity_curve):
    df = pd.DataFrame(equity_curve, columns=["date", "nav"]).set_index("date").sort_index()
    df["returns"] = df["nav"].pct_change()
    
    total_return = df["nav"].iloc[-1] / df["nav"].iloc[0] - 1
    n_days       = len(df)
    ann_return   = (1 + total_return) ** (252 / n_days) - 1
    ann_vol      = df["returns"].std() * np.sqrt(252)
    risk_free    = 0.045
    sharpe       = (ann_return - risk_free) / ann_vol if ann_vol > 0 else 0
    peak         = df["nav"].cummax()
    max_dd       = ((df["nav"] - peak) / peak).min()
    calmar       = ann_return / abs(max_dd) if max_dd != 0 else 0
    win_rate     = (df["returns"].dropna() > 0).mean()

    metrics = {
        "Total Return":    f"{total_return:.2%}",
        "Ann. Return":     f"{ann_return:.2%}",
        "Ann. Volatility": f"{ann_vol:.2%}",
        "Sharpe Ratio":    f"{sharpe:.3f}",
        "Max Drawdown":    f"{max_dd:.2%}",
        "Calmar Ratio":    f"{calmar:.3f}",
        "Win Rate (daily)": f"{win_rate:.2%}",
        "Trading Days":    str(n_days),
    }
    return metrics, df

def main():
    print("=" * 60)
    print("PHASE 5d — BACKTEST VN30 V4 WITH FUNDAMENTAL PRE-FILTER ONLY")
    print("=" * 60)

    qlib.init(provider_uri=QLIB_DIR)

    pred_path = os.path.join(os.path.dirname(__file__), "..", "results", "v4", "pred.pkl")
    if not os.path.exists(pred_path):
        raise FileNotFoundError(f"Missing V4 predictions at {pred_path}")
        
    with open(pred_path, "rb") as f:
        pred_df = pickle.load(f)

    if isinstance(pred_df.index, pd.MultiIndex):
        pred_df = pred_df.reset_index()
        pred_df.columns = ["datetime", "instrument", "score"]
    pred_df["datetime"] = pd.to_datetime(pred_df["datetime"])

    pred_test = pred_df[pred_df["datetime"] >= TEST_START].copy()
    test_dates = sorted([pd.Timestamp(d) for d in pred_test["datetime"].unique()])
    symbols    = pred_test["instrument"].unique().tolist()

    print(f"Loading prices for {len(symbols)} symbols ...")
    price_map = load_price_map(symbols, TEST_START, TEST_END)

    print(f"Running backtest (TOPK={TOPK}) on {len(test_dates)} trading days ...")
    equity_curve, trade_log = run_backtest_v5d(pred_test, price_map, test_dates)

    metrics, nav_df = compute_tearsheet(equity_curve)

    print("\n" + "=" * 60)
    print("  BACKTEST TEARSHEET V5d (Fundamental Pre-Filter)")
    print("=" * 60)
    for k, v in metrics.items():
        print(f"  {k:<22}: {v}")
    print("=" * 60)

    peak = nav_df["nav"].cummax()
    drawdowns = (nav_df["nav"] - peak) / peak
    nav_df["drawdown"] = drawdowns
    
    print("\nMonthly NAV (end of month):")
    monthly = nav_df.resample("M").last()
    for dt, row in monthly.iterrows():
        val = row["nav"]
        dd = row["drawdown"] * 100
        pct = (val / INIT_CAPITAL - 1) * 100
        sign = "+" if pct >= 0 else ""
        print(f"  {dt.strftime('%Y-%m')}  {val/1e9:8.4f} tỷ  ({sign}{pct:>6.2f}%)  DD: {dd:>6.2f}%")

    trades_df = pd.DataFrame(
        trade_log, columns=["date", "action", "symbol", "shares", "price", "amount"]
    )
    print(f"\nTotal trades: {len(trades_df)}")
    if not trades_df.empty:
        print(trades_df["action"].value_counts().to_string())

    out_dir = os.path.join(os.path.dirname(__file__), "..", "results", "v5d_fund_filter")
    os.makedirs(out_dir, exist_ok=True)
    nav_df.to_csv(os.path.join(out_dir, "backtest_nav.csv"))
    trades_df.to_csv(os.path.join(out_dir, "trade_log.csv"), index=False)
    print(f"\nResults saved → {os.path.abspath(out_dir)}")

if __name__ == "__main__":
    main()

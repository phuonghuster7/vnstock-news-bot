"""
Phase 5b: Backtest Nâng cao - Bước 1
- Sử dụng Signal từ V4 (Pure momentum).
- Market Regime Filter: MA50 của VNINDEX.
    * Bullish: Mua bình thường.
    * Bearish: Ngừng mua mới, bán dần. Chỉ bearish khi 3 ngày liên tiếp < MA50.
- TOPK = 5.
"""
import os
import pandas as pd
import numpy as np
import qlib
from qlib.data import D
import pickle
from vnstock import Quote

# ─── Constants ───────────────────────────────────────────────────────────────
QLIB_DIR     = os.path.expanduser("~/.qlib/qlib_data/vn_data")
TEST_START   = "2024-01-02"
TEST_END     = "2026-06-01"
TOPK         = 5
COMMISSION   = 0.0015          # 0.15% mỗi chiều
INIT_CAPITAL = 1_000_000_000   # 1 tỷ VND
T_PLUS       = 2               # T+2 settlement

# ─── 1. Market Regime Filter ──────────────────────────────────────────────────
class RegimeAwareStrategy:
    """
    Chỉ hold position khi VN-Index trend UP.
    Regime = 1 (bullish): VN-Index close > MA50
    """
    def __init__(self, start_date: str, end_date: str, ma_window: int = 50):
        self.ma_window = ma_window
        # Fetch VNINDEX data with padding
        fetch_start = (pd.to_datetime(start_date) - pd.Timedelta(days=ma_window*2)).strftime("%Y-%m-%d")
        quote = Quote(source="kbs", symbol="VNINDEX")
        self.vnindex = quote.history(start=fetch_start, end=end_date, interval="1D")
        
        if self.vnindex is not None and not self.vnindex.empty:
            if 'time' not in self.vnindex.columns:
                self.vnindex['time'] = self.vnindex.index
            self.vnindex['date'] = pd.to_datetime(self.vnindex['time']).dt.strftime('%Y-%m-%d')
            self.vnindex = self.vnindex.set_index('date')
            self._compute_regime()
        else:
            print("Warning: Could not fetch VNINDEX. Regime filter will be disabled (always bullish).")
            self.regime_confirmed = pd.Series()

    def _compute_regime(self):
        close = self.vnindex["close"]
        ma = close.rolling(self.ma_window).mean()
        regime = (close > ma).astype(int)
        
        # Sửa lỗi logic: 
        # Để tránh bearish quá sớm, ta chỉ cho regime = 0 (bearish) khi 3 ngày liên tiếp nằm dưới MA50.
        # Nghĩa là nếu max của 3 ngày gần nhất = 1 (có ít nhất 1 ngày bullish) thì vẫn giữ là 1.
        confirmed = regime.rolling(3).max()
        self.regime_confirmed = confirmed.fillna(1)
        self.regime_confirmed.index = pd.to_datetime(self.regime_confirmed.index)

    def is_bullish(self, date: pd.Timestamp) -> bool:
        if self.regime_confirmed.empty:
            return True
        try:
            idx = self.regime_confirmed.index.get_indexer([date], method='pad')[0]
            if idx >= 0:
                return bool(self.regime_confirmed.iloc[idx] == 1)
            return True
        except Exception:
            return True

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

def run_backtest_v5b(pred_df: pd.DataFrame, price_map: dict, test_dates: list):
    holdings     = {}     # {sym: shares}
    cash         = float(INIT_CAPITAL)
    pending_cash = []     # [(settle_date, amount)]
    equity_curve = []     # [(date, nav)]
    trade_log    = []
    
    regime_filter = RegimeAwareStrategy(TEST_START, TEST_END)

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
        
        # Lấy dự đoán của ngày
        mask = pred_df["datetime"] == date
        day_scores = pred_df.loc[mask].set_index("instrument")["score"]
        
        target_syms = set()
        
        # Check Regime
        is_bullish = regime_filter.is_bullish(date)
        
        if not day_scores.empty and is_bullish:
            valid = day_scores.dropna().sort_values(ascending=False)
            target_syms = set(valid.index[:TOPK].tolist())
        # Nếu bearish, target_syms = set() -> sẽ bán dần những cổ rơi khỏi TOPK (tức là bán hết danh mục)
        
        current_syms = set(holdings.keys())

        # Bán
        for sym in list(current_syms - target_syms):
            price = get_price(date, sym)
            if np.isnan(price) or price <= 0:
                continue
            shares = holdings.pop(sym)
            proceeds = shares * price * (1 - COMMISSION)
            settle_idx = min(i + T_PLUS, len(test_dates) - 1)
            pending_cash.append((test_dates[settle_idx], proceeds))
            action = "SELL" if is_bullish else "SELL_REGIME"
            trade_log.append((date, action, sym, shares, price, proceeds))

        # Mua (chỉ mua khi bullish)
        if is_bullish:
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
    print("PHASE 5b — BACKTEST VN30 V4 WITH REGIME FILTER (ONLY)")
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
    equity_curve, trade_log = run_backtest_v5b(pred_test, price_map, test_dates)

    metrics, nav_df = compute_tearsheet(equity_curve)

    print("\n" + "=" * 60)
    print("  BACKTEST TEARSHEET V5b (Regime ONLY)")
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

    out_dir = os.path.join(os.path.dirname(__file__), "..", "results", "v5b_regime_only")
    os.makedirs(out_dir, exist_ok=True)
    nav_df.to_csv(os.path.join(out_dir, "backtest_nav.csv"))
    trades_df.to_csv(os.path.join(out_dir, "trade_log.csv"), index=False)
    print(f"\nResults saved → {os.path.abspath(out_dir)}")

if __name__ == "__main__":
    main()

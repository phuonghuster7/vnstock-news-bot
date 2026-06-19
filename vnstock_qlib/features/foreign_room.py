"""
vnstock_qlib/features/foreign_room.py
──────────────────────────────────────
Room ngoại còn lại = tín hiệu demand constraint.

Logic:
  Room < 5%  → gần hết room → ngoại không thể mua thêm → FILTER ra
  Room 5-20% → cảnh báo, giữ nhưng đánh dấu
  Room > 20% → OK

Dùng làm POST-FILTER sau liquidity filter.
Data source: vnstock Trading.price_board() → match_current_room / match_total_room
Cache: cache/foreign_room_latest.csv (1 file/ngày)
"""
import os
import warnings
import pandas as pd
from datetime import datetime
from pathlib import Path

warnings.filterwarnings("ignore")

CACHE_DIR    = Path(__file__).parents[2] / "cache"
CACHE_FILE   = CACHE_DIR / "foreign_room_latest.csv"
ROOM_FILTER  = 5.0    # % — loại mã dưới ngưỡng này
ROOM_WARN    = 20.0   # % — cảnh báo nhưng không loại
BATCH_SIZE   = 30     # mã mỗi lần gọi API


def _flatten_board(board: pd.DataFrame) -> pd.DataFrame:
    """Flatten MultiIndex columns từ price_board()."""
    if isinstance(board.columns, pd.MultiIndex):
        board.columns = ['_'.join(str(c) for c in col).strip()
                         for col in board.columns.values]
    return board


def fetch_foreign_room(symbols: list,
                       use_cache: bool = True,
                       cache_ttl_hours: int = 8) -> pd.DataFrame:
    """
    Fetch room ngoại cho tất cả symbols.

    Args:
        symbols: danh sách mã
        use_cache: dùng cache nếu còn hiệu lực
        cache_ttl_hours: số giờ cache còn hiệu lực

    Returns:
        DataFrame với columns: [symbol, current_room, total_room, room_pct, fetch_time]
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # ── Kiểm tra cache ─────────────────────────────────────────────────────
    if use_cache and CACHE_FILE.exists():
        age_hours = (datetime.now().timestamp() -
                     CACHE_FILE.stat().st_mtime) / 3600
        if age_hours < cache_ttl_hours:
            df = pd.read_csv(CACHE_FILE)
            # Kiểm tra có đủ symbols không
            cached_syms = set(df["symbol"].tolist())
            missing = [s for s in symbols if s not in cached_syms]
            if not missing:
                return df[df["symbol"].isin(symbols)].reset_index(drop=True)
            # Thiếu một số mã → fetch thêm

    # ── Fetch từ API ───────────────────────────────────────────────────────
    from vnstock import Trading
    t = Trading(symbol=symbols[0], source="VCI")

    all_rows = []
    # Gọi 1 lần toàn bộ (price_board chấp nhận list lớn)
    try:
        board = t.price_board(symbols_list=symbols)
        board = _flatten_board(board)

        sym_col   = next((c for c in board.columns if c.endswith("symbol")),   None)
        room_col  = next((c for c in board.columns if c.endswith("current_room")), None)
        total_col = next((c for c in board.columns if c.endswith("total_room")),   None)

        if sym_col and room_col and total_col:
            df = board[[sym_col, room_col, total_col]].copy()
            df.columns = ["symbol", "current_room", "total_room"]
            df["current_room"] = pd.to_numeric(df["current_room"], errors="coerce")
            df["total_room"]   = pd.to_numeric(df["total_room"],   errors="coerce")
            df["room_pct"]     = (df["current_room"] / df["total_room"] * 100).round(2)
            df["fetch_time"]   = datetime.now().strftime("%Y-%m-%d %H:%M")
            all_rows.append(df)
        else:
            print(f"  ⚠ Không tìm thấy room columns. Available: {board.columns[:10].tolist()}")

    except Exception as e:
        print(f"  ⚠ Lỗi fetch room ngoại: {e}")

    if not all_rows:
        # Trả về DataFrame rỗng với NA — không block pipeline
        return pd.DataFrame({
            "symbol": symbols,
            "current_room": [None] * len(symbols),
            "total_room":   [None] * len(symbols),
            "room_pct":     [None] * len(symbols),
            "fetch_time":   [datetime.now().strftime("%Y-%m-%d %H:%M")] * len(symbols),
        })

    result = pd.concat(all_rows, ignore_index=True)

    # ── Cache ──────────────────────────────────────────────────────────────
    result.to_csv(CACHE_FILE, index=False)
    n_critical = (result["room_pct"] < ROOM_FILTER).sum()
    n_warn     = ((result["room_pct"] >= ROOM_FILTER) & (result["room_pct"] < ROOM_WARN)).sum()
    print(f"  Room data: {len(result)} mã | "
          f"🔴 Filter(<{ROOM_FILTER}%): {n_critical} | "
          f"🟡 Warn(<{ROOM_WARN}%): {n_warn} | "
          f"🟢 OK: {len(result) - n_critical - n_warn}")

    return result


def apply_room_filter(ranking: pd.DataFrame,
                      room_df: pd.DataFrame = None,
                      threshold: float = ROOM_FILTER) -> pd.DataFrame:
    """
    Post-filter: loại mã room < threshold%.
    Mã không có room data → giữ nguyên (không phạt).

    Args:
        ranking: DataFrame có cột 'symbol', 'score'
        room_df: kết quả từ fetch_foreign_room() (None → đọc cache)
        threshold: % room tối thiểu

    Returns:
        DataFrame đã filter, cột 'rank' được cập nhật
    """
    # Load room data
    if room_df is None:
        if CACHE_FILE.exists():
            room_df = pd.read_csv(CACHE_FILE)
        else:
            print("  ⚠ Không có room cache — bỏ qua room filter")
            return ranking

    merged = ranking.merge(
        room_df[["symbol", "room_pct"]],
        on="symbol", how="left"
    )

    no_data  = merged["room_pct"].isna()        # không có data → giữ
    room_ok  = merged["room_pct"] >= threshold  # đủ room → giữ

    filtered = merged[no_data | room_ok].copy()
    removed  = merged[~(no_data | room_ok)].copy()

    # Log
    if not removed.empty:
        rm_list = [f"{r['symbol']}({r['room_pct']:.1f}%)"
                   for _, r in removed.iterrows()]
        print(f"  ⚠ Room filter: loại {len(removed)} mã — {', '.join(rm_list)}")
    else:
        print(f"  ✓ Room filter: tất cả {len(ranking)} mã pass (>{threshold}%)")

    # Warning cho mã room 5-20%
    warn_mask = (~no_data) & room_ok & (merged["room_pct"] < ROOM_WARN)
    if warn_mask.any():
        w_list = [f"{r['symbol']}({r['room_pct']:.1f}%)"
                  for _, r in merged[warn_mask].iterrows()]
        print(f"  🟡 Room warning (<{ROOM_WARN}%): {', '.join(w_list)}")

    filtered = filtered.drop(columns=["room_pct"], errors="ignore")
    filtered["rank"] = range(1, len(filtered) + 1)
    return filtered.reset_index(drop=True)


# ── CLI test ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    syms = sys.argv[1:] if len(sys.argv) > 1 else [
        "VCB", "HPG", "VNM", "TCB", "MBB", "ACB", "FPT",
        "VPB", "CTG", "BID", "HDB", "NLG", "BVH", "PVT"
    ]
    print(f"Fetching room data for {len(syms)} symbols ...")
    df = fetch_foreign_room(syms, use_cache=False)
    print(df.sort_values("room_pct").to_string(index=False))

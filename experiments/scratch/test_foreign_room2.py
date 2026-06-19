"""
Test room ngoại thực tế + tính room_pct cho VN100.
Báo: mã nào room < 5%, < 20%, distribution.
"""
import pandas as pd
import warnings
warnings.filterwarnings("ignore")

SYMBOLS = ["VCB", "HPG", "VNM", "ACB", "FPT", "TCB", "MBB", "VHM",
           "VIC", "SSI", "STB", "EIB", "VPB", "HDB", "BID", "CTG",
           "MSN", "GAS", "POW", "PLX", "BSR", "PVT", "NLG", "BVH"]

print("=" * 55)
print(f"  Foreign Room Test — {len(SYMBOLS)} mã")
print("=" * 55)

try:
    from vnstock import Trading
    t = Trading(symbol="VCB", source="VCI")
    board = t.price_board(symbols_list=SYMBOLS)
    
    # MultiIndex columns → flatten
    if isinstance(board.columns, pd.MultiIndex):
        board.columns = ['_'.join(c).strip() for c in board.columns.values]
    
    print(f"Columns sample: {board.columns[:10].tolist()}")
    
    # Tìm cột symbol, current_room, total_room
    sym_col     = next((c for c in board.columns if c.endswith("symbol")), None)
    room_col    = next((c for c in board.columns if c.endswith("current_room")), None)
    total_col   = next((c for c in board.columns if c.endswith("total_room")), None)
    
    print(f"  sym_col:   {sym_col}")
    print(f"  room_col:  {room_col}")
    print(f"  total_col: {total_col}")
    
    if room_col and total_col:
        df = board[[sym_col, room_col, total_col]].copy()
        df.columns = ["symbol", "current_room", "total_room"]
        df["current_room"] = pd.to_numeric(df["current_room"], errors="coerce")
        df["total_room"]   = pd.to_numeric(df["total_room"],   errors="coerce")
        df["room_pct"] = (df["current_room"] / df["total_room"] * 100).round(2)
        
        df = df.sort_values("room_pct")
        
        print(f"\n  {'Symbol':<8} {'Room Left':>12} {'Total Room':>12} {'Room %':>8}")
        print(f"  {'-'*48}")
        for _, row in df.iterrows():
            flag = "🔴" if row["room_pct"] < 5 else "🟡" if row["room_pct"] < 20 else "🟢"
            print(f"  {flag} {row['symbol']:<6} {row['current_room']:>14,.0f} {row['total_room']:>12,.0f} {row['room_pct']:>7.1f}%")
        
        # Summary
        print(f"\n  Summary:")
        print(f"    Room < 5%  (FILTERED): {(df['room_pct'] < 5).sum()} mã")
        print(f"    Room 5-20% (WARNING):  {((df['room_pct'] >= 5) & (df['room_pct'] < 20)).sum()} mã")
        print(f"    Room > 20% (OK):       {(df['room_pct'] >= 20).sum()} mã")
    else:
        print("Không tìm thấy room columns!")
        print("All columns:", board.columns.tolist()[:20])

except Exception as e:
    import traceback
    print(f"Error: {e}")
    traceback.print_exc()

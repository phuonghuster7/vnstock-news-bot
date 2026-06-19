"""
Test fetch room ngoại từ vnstock.
Thử các method khác nhau để tìm đúng field room_pct.
"""
import pandas as pd
import warnings
warnings.filterwarnings("ignore")

SYMBOLS = ["VCB", "HPG", "VNM"]

# ── Method 1: Thử Trading.price_board ──────────────────────────────────────
print("=" * 55)
print("Method 1: Trading.price_board()")
print("=" * 55)
try:
    from vnstock import Trading
    t = Trading(symbol="VCB", source="VCI")
    board = t.price_board(symbols_list=SYMBOLS)
    print(f"Type: {type(board)}")
    if board is not None and not (hasattr(board, 'empty') and board.empty):
        print(f"Shape: {board.shape}")
        print(f"Columns: {board.columns.tolist()}")
        print(board.head(3).to_string())
    else:
        print("Empty result")
except Exception as e:
    print(f"Error: {e}")

# ── Method 2: Thử Listing.symbols_by_group hoặc foreign_room ──────────────
print("\n" + "=" * 55)
print("Method 2: Stock / Trading methods")
print("=" * 55)
try:
    from vnstock import Trading
    t = Trading(symbol="VCB", source="VCI")
    # List available methods
    methods = [m for m in dir(t) if not m.startswith("_")]
    print(f"Available methods: {methods}")
except Exception as e:
    print(f"Error: {e}")

# ── Method 3: Thử vnstock Listing hoặc Company ────────────────────────────
print("\n" + "=" * 55)
print("Method 3: Listing / Company")
print("=" * 55)
try:
    from vnstock import Listing
    listing = Listing()
    methods = [m for m in dir(listing) if not m.startswith("_") and "room" in m.lower()]
    print(f"Room-related methods in Listing: {methods}")
except Exception as e:
    print(f"Listing error: {e}")

# ── Method 4: Thử Quote hoặc Screener ────────────────────────────────────
print("\n" + "=" * 55)
print("Method 4: Screener / full market board")
print("=" * 55)
try:
    from vnstock import Screener
    sc = Screener()
    methods = [m for m in dir(sc) if not m.startswith("_")]
    print(f"Screener methods: {methods[:15]}")
except Exception as e:
    print(f"Screener error: {e}")

# ── Method 5: Thử trực tiếp price board toàn thị trường ──────────────────
print("\n" + "=" * 55)
print("Method 5: Market board (foreign_room field)")  
print("=" * 55)
try:
    from vnstock import Trading
    t = Trading(symbol="VCB", source="VCI")
    board = t.price_board(symbols_list=["VCB", "HPG", "VNM"])
    # Tìm cột liên quan đến foreign
    if board is not None:
        foreign_cols = [c for c in board.columns if any(k in str(c).lower() 
                        for k in ["foreign", "room", "nn", "nuoc_ngoai", "nước ngoài"])]
        print(f"Foreign-related columns: {foreign_cols}")
        if foreign_cols:
            print(board[["symbol"] + foreign_cols].to_string() if "symbol" in board.columns 
                  else board[foreign_cols].head())
except Exception as e:
    print(f"Error: {e}")

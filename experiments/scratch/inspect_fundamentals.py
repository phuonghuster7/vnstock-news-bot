from vnstock import Finance
import pandas as pd

def inspect_fundamentals(symbol="FPT"):
    print(f"Fetching ratios for {symbol}...")
    try:
        finance = Finance(source="kbs", symbol=symbol)
        df = finance.ratio(period="quarter")
        print("Columns:", df.columns.tolist())
        print("Head:")
        print(df.head())
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    inspect_fundamentals()

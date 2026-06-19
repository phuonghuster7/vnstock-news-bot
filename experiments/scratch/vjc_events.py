import pandas as pd
import time
from vnstock import Company, Quote

company = Company(symbol="VJC", source="vci")
try:
    events = company.events()
    if events is not None and not events.empty:
        # Filter stock dividends or stock splits
        stock_divs = events[events['event_list_name'].str.contains('cổ phiếu|thưởng|phát hành', case=False, na=False)]
        print("--- VJC STOCK DIVIDEND HISTORY ---")
        print(stock_divs[['event_title', 'event_list_name', 'ratio', 'exright_date', 'record_date']].to_string(index=False))
    else:
        print("No events found.")
except Exception as e:
    print("Error getting events:", e)

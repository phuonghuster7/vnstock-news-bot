import pandas as pd
import time
from vnstock import Company

targets = ['ACB', 'CII', 'NLG']

for sym in targets:
    print(f"\n=================== {sym} DETAILED SCAN ===================")
    company = Company(symbol=sym, source='vci')
    
    # Get Events
    try:
        events = company.events()
        if events is not None and not events.empty:
            print("\n--- EVENTS & DIVIDENDS ---")
            # Filter dividend related events
            div_events = events[events['event_list_name'].str.contains('cổ tức|phát hành|thưởng', case=False, na=False)]
            if not div_events.empty:
                cols = ['event_title', 'event_list_name', 'ratio', 'value', 'exright_date', 'record_date']
                cols_to_print = [c for c in cols if c in div_events.columns]
                print(div_events[cols_to_print].head(5).to_string(index=False))
            else:
                print("No dividend events found in history.")
        else:
            print("No events database available.")
    except Exception as e:
        print(f"Error fetching events: {e}")
        
    # Get News
    try:
        news = company.news()
        if news is not None and not news.empty:
            print("\n--- DETAILED NEWS (DIVIDEND/TRANSACTION) ---")
            # Filter news containing dividend or related keywords
            keywords = 'cổ tức|phát hành|trái phiếu|sở hữu|đăng ký'
            filtered_news = news[news['news_title'].str.contains(keywords, case=False, na=False)]
            if not filtered_news.empty:
                print(filtered_news[['news_title', 'public_date']].head(7).to_string(index=False))
            else:
                print("No recent news matched keywords.")
        else:
            print("No news database available.")
    except Exception as e:
        print(f"Error fetching news: {e}")
        
    time.sleep(0.5)

import pandas as pd
import time
from vnstock import Company

candidates = ['ACB', 'CII', 'NLG', 'HCM']
sources = ['vci', 'kbs']

print("Fetching news for candidates...")
for sym in candidates:
    print(f"\n=================== {sym} NEWS ===================")
    for src in sources:
        try:
            company = Company(symbol=sym, source=src)
            df_news = company.news()
            if df_news is not None and not df_news.empty:
                print(f"Source: {src.upper()} - Found {len(df_news)} articles.")
                # Show top 5 latest news titles
                if src == 'vci':
                    cols = ['news_title', 'public_date'] if 'news_title' in df_news.columns else df_news.columns[:3]
                else:
                    cols = ['head', 'publish_time'] if 'head' in df_news.columns else df_news.columns[:3]
                
                print(df_news[cols].head(5).to_string(index=False))
            else:
                print(f"Source: {src.upper()} - No news found.")
        except Exception as e:
            print(f"Source: {src.upper()} - Error: {e}")
        time.sleep(0.5)

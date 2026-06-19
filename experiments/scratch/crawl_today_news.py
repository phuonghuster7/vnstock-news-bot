import pandas as pd
from vnstock_news import Crawler

def crawl_today_news():
    sites = ['cafef', 'vietstock']
    all_titles = []
    
    for site in sites:
        print(f"--- Fetching latest news from {site.upper()} ---")
        try:
            crawler = Crawler(site_name=site)
            # Fetch latest articles from feeds
            articles = crawler.get_articles_from_feed(limit_per_feed=30)
            if articles:
                df = pd.DataFrame(articles)
                titles = df['title'].tolist()
                for t in titles:
                    print(f"* {t}")
                    all_titles.append((site, t))
            else:
                print("No articles found in feeds.")
        except Exception as e:
            print(f"Error fetching from {site}: {e}")
            
    print(f"\nSuccessfully crawled {len(all_titles)} titles.")

if __name__ == "__main__":
    crawl_today_news()

import os
from newsapi import NewsApiClient
import csv
from sqlmodel import Session
from .models import NewsItem

NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")

def import_news_from_csv_or_api(code: str, engine):
    # Try NewsAPI first
    items = []
    if NEWSAPI_KEY:
        newsapi = NewsApiClient(api_key=NEWSAPI_KEY)
        q = f"{code} OR Apple"
        res = newsapi.get_everything(q=q, language='en', sort_by='relevancy', page_size=50)
        for a in res.get('articles', []):
            items.append({
                'title': a['title'],
                'url': a['url'],
                'published_at': a['publishedAt'][:10] if a.get('publishedAt') else None,
                'content': a.get('content') or a.get('description'),
                'source': a['source']['name']
            })
    else:
        # fallback: read local CSV at data/news_{code}.csv expected
        path = f"data/news_{code.lower()}.csv"
        if os.path.exists(path):
            with open(path, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for r in reader:
                    items.append({
                        'title': r.get('title'),
                        'url': r.get('url'),
                        'published_at': r.get('published_at'),
                        'content': r.get('content'),
                        'source': r.get('source')
                    })
    # store into DB
    count = 0
    with Session(engine) as session:
        for it in items:
            ni = NewsItem(
                stock_code=code.upper(),
                title=it['title'] or '',
                url=it.get('url'),
                published_at=it.get('published_at'),
                content=it.get('content'),
                source=it.get('source')
            )
            session.add(ni)
            count += 1
        session.commit()
    return count

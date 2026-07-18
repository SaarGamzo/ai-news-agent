import feedparser

from app.models import NewsArticle
from datetime import datetime


class RSSCollector:

    def __init__(self, feed_url: str, source: str):
        self.feed_url = feed_url
        self.source = source

    def collect(self):

        feed = feedparser.parse(self.feed_url)

        articles = []

        for entry in feed.entries:

            published = datetime.now()
            if getattr(entry, "published_parsed", None):
                published = datetime(*entry.published_parsed[:6])

            articles.append(
                NewsArticle(
                    title=entry.title,
                    url=entry.link,
                    summary=getattr(entry, "summary", ""),
                    published=published,
                    source=self.source,
                )
            )

        return articles
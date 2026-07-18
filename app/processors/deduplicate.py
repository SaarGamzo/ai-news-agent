from urllib.parse import urlparse, urlunparse

from app.models import NewsArticle


def _normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    clean = parsed._replace(query="", fragment="")
    return urlunparse(clean).rstrip("/")


def deduplicate_articles(articles: list[NewsArticle]) -> list[NewsArticle]:
    unique: dict[str, NewsArticle] = {}

    for article in articles:
        normalized_url = _normalize_url(article.url)
        title_key = article.title.strip().lower()
        key = f"{normalized_url}|{title_key}"

        if key not in unique:
            unique[key] = article

    return list(unique.values())

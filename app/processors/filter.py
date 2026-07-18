from app.models import NewsArticle
from datetime import datetime, timedelta


IMPORTANT_WORDS = [
    "model",
    "release",
    "introducing",
    "launch",
    "api",
    "agent",
    "benchmark",
    "research",
    "security",
    "open source",
    "workflow",
    "tool",
    "startup",
    "funding",
    "company",
    "automation",
    "inference",
    "reasoning",
    "multimodal",
]


def calculate_score(article: NewsArticle):
    text = f"{article.title} {article.summary}".lower()

    score = 0

    for word in IMPORTANT_WORDS:
        if word in text:
            score += 1

    article.score = score

    return article


def filter_articles(articles, minimum_score: int = 2):

    scored = [
        calculate_score(article)
        for article in articles
    ]

    return [
        article
        for article in scored
        if article.score >= minimum_score
    ]


def filter_recent_articles(
    articles: list[NewsArticle],
    max_age_days: int = 3,
) -> list[NewsArticle]:
    cutoff = datetime.now() - timedelta(days=max_age_days)
    return [
        article
        for article in articles
        if article.published >= cutoff
    ]
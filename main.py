import time
import os
from datetime import date
from pathlib import Path

from app.collectors.rss import RSSCollector
from app.collectors.html import HTMLCollector
from app.config import load_config
from app.processors.filter import filter_articles, filter_recent_articles
from app.processors.deduplicate import deduplicate_articles
from app.processors.summarize import HebrewSummarizer
from app.reporting.render import build_html_report, build_compact_email_report
from app.reporting.email_sender import send_html_email


def collect_articles(config: dict) -> list:
    all_articles = []

    for source in config["sources"]:
        collector = None

        if source["type"] == "rss":
            collector = RSSCollector(
                source["url"],
                source["name"],
            )

        elif source["type"] == "html":
            collector = HTMLCollector(
                source["url"],
                source["name"],
            )

        if collector is None:
            print(f"Skipping unsupported source type: {source}")
            continue

        try:
            articles = collector.collect()
        except Exception as exc:
            print(f"{source['name']}: failed to collect ({exc})")
            continue

        print(f"{source['name']}: collected {len(articles)} articles")
        all_articles.extend(articles)

    return all_articles


def save_report(html_report: str, output_dir: str) -> Path:
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    report_file = target_dir / f"ai_daily_report_{date.today().isoformat()}.html"
    report_file.write_text(html_report, encoding="utf-8")
    return report_file


def maybe_send_email(config: dict, html_report: str) -> None:
    email_cfg = config.get("email", {})

    # Local runs are primarily for debugging/report review. Send email only in CI
    # unless explicitly overridden.
    in_github_actions = bool(os.getenv("GITHUB_ACTIONS"))
    force_local_email = os.getenv("FORCE_LOCAL_EMAIL", "").lower() in {"1", "true", "yes"}
    if not in_github_actions and not force_local_email:
        print("Local run detected: skipping email send (set FORCE_LOCAL_EMAIL=true to override).")
        return

    if not email_cfg.get("enabled", False):
        print("Email delivery disabled by config.")
        return

    recipients = email_cfg.get("recipients", [])
    if not recipients:
        print("Email enabled, but recipients list is empty. Skipping send.")
        return

    required_fields = ["smtp_host", "sender"]
    missing_required = [field for field in required_fields if not email_cfg.get(field)]
    if missing_required:
        print(f"Email enabled, but missing required fields: {missing_required}. Skipping send.")
        return

    try:
        send_html_email(
            smtp_host=email_cfg["smtp_host"],
            smtp_port=int(email_cfg.get("smtp_port", 587)),
            sender=email_cfg["sender"],
            recipients=recipients,
            subject=email_cfg.get("subject", "AI Daily Report"),
            html_body=html_report,
            username=email_cfg.get("username", ""),
            password=email_cfg.get("password", ""),
            use_tls=bool(email_cfg.get("use_tls", True)),
        )
        print(f"Email sent to {len(recipients)} recipients.")
    except Exception as exc:
        print(f"Email send failed: {exc}")


def deduplicate_terms_across_report(articles: list) -> list:
    seen_terms: set[str] = set()

    for article in articles:
        unique_terms = {}
        for term, explanation in article.term_explanations.items():
            normalized = term.strip().lower()
            if normalized in seen_terms:
                continue
            unique_terms[term] = explanation
            seen_terms.add(normalized)
        article.term_explanations = unique_terms

    return articles


start_time = time.time()
config = load_config()

all_articles = collect_articles(config)
all_articles = deduplicate_articles(all_articles)

max_age_days = int(config.get("filter", {}).get("max_age_days", 3))
all_articles = filter_recent_articles(all_articles, max_age_days=max_age_days)

minimum_score = int(config.get("filter", {}).get("minimum_score", 2))
important_articles = filter_articles(all_articles, minimum_score=minimum_score)

max_articles = int(config.get("report", {}).get("max_articles", 25))
important_articles = sorted(
    important_articles,
    key=lambda article: (article.score, article.published),
    reverse=True,
)

if len(important_articles) < max_articles:
    relaxed_score = max(minimum_score - 1, 0)
    relaxed_candidates = sorted(
        filter_articles(all_articles, minimum_score=relaxed_score),
        key=lambda article: (article.score, article.published),
        reverse=True,
    )
    existing_urls = {article.url for article in important_articles}
    for candidate in relaxed_candidates:
        if candidate.url in existing_urls:
            continue
        important_articles.append(candidate)
        existing_urls.add(candidate.url)
        if len(important_articles) >= max_articles:
            break

important_articles = important_articles[:max_articles]

summarizer = HebrewSummarizer(config.get("llm", {}), minimum_score=minimum_score)
important_articles = summarizer.summarize_many(important_articles)
important_articles = deduplicate_terms_across_report(important_articles)

for article in important_articles:
    print(article.score, "|", article.source, "-", article.title)

html_report = build_html_report(date.today(), important_articles)
email_report = build_compact_email_report(date.today(), important_articles)
report_path = save_report(
    html_report=html_report,
    output_dir=config.get("report", {}).get("output_dir", "reports"),
)

print(f"Report saved: {report_path}")
maybe_send_email(config, email_report)

end_time = time.time()

print(
    f"\nExecution time: {end_time - start_time:.2f} seconds"
)

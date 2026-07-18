from datetime import date
from html import escape

from app.models import NewsArticle


CATEGORY_LABELS_HE = {
    "new_models": "מודלים חדשים",
    "new_tools": "כלים חדשים",
    "new_hacks": "טריקים ושיטות",
    "new_workflows": "וורקפלואים חדשים",
    "companies_ecosystem": "חברות ואקוסיסטם",
    "general": "כללי",
}


SOURCE_LABELS_HE = {
    "OpenAI": "אופן-איי-איי",
    "Anthropic": "אנתרופיק",
    "Hugging Face Blog": "בלוג האגינג פייס",
    "Google DeepMind Blog": "בלוג גוגל דיפמיינד",
    "Meta AI": "מטא איי-איי",
    "NVIDIA Developer - Generative AI": "אנבידיה - בינה יוצרת",
    "AWS Machine Learning Blog": "בלוג למידת המכונה של AWS",
    "Microsoft AI Blog": "בלוג ה-AI של מיקרוסופט",
    "Cohere Blog": "בלוג Cohere",
    "VentureBeat AI": "ונצ'רביט איי-איי",
}


def build_html_report(report_date: date, articles: list[NewsArticle]) -> str:
    rows = []
    for article in articles:
        category_he = CATEGORY_LABELS_HE.get(article.category, "כללי")
        source_he = article.hebrew_source or SOURCE_LABELS_HE.get(article.source, article.source)
        title_he = article.hebrew_title or article.title

        terms = ""
        if article.term_explanations:
            terms_items = "".join(
                f"<li><b>{escape(term)}</b>: {escape(explanation)}</li>"
                for term, explanation in article.term_explanations.items()
            )
            terms = f"<div><b>מונחים והסברים:</b><ul>{terms_items}</ul></div>"

        takeaway = ""
        if article.actionable_takeaway_he:
            takeaway = (
                "<p style='margin:8px 0 8px 0;'>"
                f"<b>מה לקחת מזה בפועל:</b> {escape(article.actionable_takeaway_he)}"
                "</p>"
            )

        row = (
            "<section style='border:1px solid #ddd;border-radius:8px;padding:14px;margin-bottom:14px;'>"
            f"<h3 style='margin:0 0 8px 0;'>{escape(title_he)}</h3>"
            f"<p style='margin:0 0 8px 0;'><b>מקור:</b> {escape(source_he)} | <b>קטגוריה:</b> {escape(category_he)}</p>"
            f"<p style='margin:0 0 8px 0;white-space:pre-line;'>{escape(article.hebrew_summary)}</p>"
            f"{takeaway}"
            f"{terms}"
            f"<p style='margin:10px 0 0 0;'><a href='{escape(article.url)}'>לכתבה המקורית</a></p>"
            "</section>"
        )
        rows.append(row)

    body = "\n".join(rows) if rows else "<p>לא נמצאו חדשות רלוונטיות להיום.</p>"

    return f"""
<!doctype html>
<html lang='he' dir='rtl'>
<head>
  <meta charset='utf-8' />
  <meta name='viewport' content='width=device-width, initial-scale=1' />
    <title>דוח יומי חדשות AI - {report_date.isoformat()}</title>
</head>
<body style='font-family: Arial, sans-serif; max-width: 900px; margin: 30px auto; padding: 0 16px;'>
  <h1 style='margin-bottom: 8px;'>דוח יומי: חדשות AI</h1>
  <p style='margin-top:0;color:#444;'>תאריך: {report_date.isoformat()}</p>
  {body}
</body>
</html>
""".strip()


def build_compact_email_report(report_date: date, articles: list[NewsArticle]) -> str:
        top = articles[:8]
        items = []

        for article in top:
                source_he = article.hebrew_source or SOURCE_LABELS_HE.get(article.source, article.source)
                title_he = article.hebrew_title or article.title
                summary_he = article.hebrew_summary.strip()
                if len(summary_he) > 240:
                        summary_he = f"{summary_he[:240].rstrip()}..."

                items.append(
                        "<li style='margin-bottom:12px;'>"
                        f"<b>{escape(title_he)}</b><br/>"
                        f"<span style='color:#555;'>מקור: {escape(source_he)}</span><br/>"
                        f"<span>{escape(summary_he)}</span><br/>"
                        f"<a href='{escape(article.url)}'>לכתבה המלאה</a>"
                        "</li>"
                )

        body = "".join(items) if items else "<p>לא נמצאו עדכונים רלוונטיים להיום.</p>"

        return f"""
<!doctype html>
<html lang='he' dir='rtl'>
<head>
    <meta charset='utf-8' />
    <meta name='viewport' content='width=device-width, initial-scale=1' />
    <title>תקציר בוקר AI - {report_date.isoformat()}</title>
</head>
<body style='font-family: Arial, sans-serif; max-width: 760px; margin: 24px auto; padding: 0 14px;'>
    <h2 style='margin-bottom:6px;'>תקציר בוקר AI</h2>
    <p style='margin-top:0;color:#555;'>תאריך: {report_date.isoformat()}</p>
    <ol style='padding-right:18px;'>
        {body}
    </ol>
    <p style='color:#666;font-size:13px;'>הדוח המלא נשמר בריפו תחת תיקיית reports.</p>
</body>
</html>
""".strip()

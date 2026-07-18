from datetime import date
from html import escape
from urllib.parse import urlparse

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
    top = articles[:15]
    items = []

    for article in top:
        source_he = article.hebrew_source or SOURCE_LABELS_HE.get(article.source, article.source)
        title_he = article.hebrew_title or article.title
        summary_he = article.hebrew_summary.strip()
        if len(summary_he) > 430:
            summary_he = f"{summary_he[:430].rstrip()}..."

        domain = urlparse(article.url).netloc.replace("www.", "")
        logo = f"https://www.google.com/s2/favicons?domain={escape(domain)}&sz=64"

        terms_html = ""
        if article.term_explanations:
            term_rows = "".join(
                f"<li style='margin-bottom:6px;'><b>{escape(term)}</b>: {escape(expl)}</li>"
                for term, expl in list(article.term_explanations.items())[:3]
            )
            terms_html = (
                "<div style='margin-top:10px;background:#f8fafc;border:1px solid #dbeafe;border-radius:10px;padding:10px;'>"
                "<div style='font-weight:700;color:#1e3a8a;margin-bottom:6px;'>מונחים מורכבים מהכתבה</div>"
                f"<ul style='margin:0;padding-right:18px;'>{term_rows}</ul>"
                "</div>"
            )

        items.append(
            "<li style='list-style:none;margin-bottom:14px;'>"
            "<div style='border:1px solid #dbe2ea;border-radius:14px;padding:14px;background:#ffffff;'>"
            "<div style='display:flex;align-items:center;gap:10px;margin-bottom:8px;'>"
            f"<img src='{logo}' alt='logo' width='24' height='24' style='border-radius:4px;' />"
            f"<span style='font-size:13px;color:#475569;'>מקור: {escape(source_he)}</span>"
            "</div>"
            f"<div style='font-size:17px;font-weight:700;color:#0f172a;margin-bottom:8px;'>{escape(title_he)}</div>"
            f"<div style='font-size:14px;line-height:1.6;color:#1f2937;'>{escape(summary_he)}</div>"
            f"{terms_html}"
            "<div style='margin-top:10px;'>"
            f"<a href='{escape(article.url)}' style='color:#2563eb;text-decoration:none;font-weight:600;'>לכתבה המלאה</a>"
            "</div>"
            "</div>"
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
<body style='font-family: Arial, sans-serif; max-width: 840px; margin: 24px auto; padding: 0 14px;background:#f3f6fb;'>
    <div style='background:linear-gradient(135deg,#0f172a,#1d4ed8);color:#fff;border-radius:16px;padding:18px 18px 14px 18px;margin-bottom:14px;'>
        <h2 style='margin:0 0 6px 0;'>תקציר יומי: חדשות AI</h2>
        <p style='margin:0;color:#dbeafe;'>תאריך: {report_date.isoformat()} | {len(top)} עדכונים מרכזיים</p>
    </div>
    <ol style='padding:0;margin:0;'>
        {body}
    </ol>
    <p style='color:#64748b;font-size:13px;margin-top:10px;'>הדוח המלא נשמר בריפו תחת תיקיית reports.</p>
</body>
</html>
""".strip()

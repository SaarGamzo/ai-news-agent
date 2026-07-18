import json
import os
from typing import Any

from bs4 import BeautifulSoup
from html import unescape

import requests

from app.models import NewsArticle


class HebrewSummarizer:
    def __init__(self, llm_config: dict[str, Any]):
        self.provider = llm_config.get("provider", "openai_compatible")
        self.api_key = (
            llm_config.get("api_key", "")
            or os.getenv("LLM_API_KEY", "")
            or os.getenv("GEMINI_API_KEY", "")
            or os.getenv("OPENAI_API_KEY", "")
        )
        self.base_url = llm_config.get("base_url", "https://api.openai.com/v1")
        self.model = llm_config.get("model", "gpt-4.1-mini")
        self.timeout = int(llm_config.get("timeout_seconds", 30))

    def summarize(self, article: NewsArticle) -> NewsArticle:
        article_context = self._build_article_context(article)

        if not self.api_key:
            return self._fallback_summary(article, article_context)

        try:
            payload = {
                "model": self.model,
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a senior AI analyst writing for technical readers in Hebrew. "
                            "Be precise, practical, and avoid hype. "
                            "Return strict JSON only."
                        ),
                    },
                    {
                        "role": "user",
                        "content": self._build_prompt(article, article_context),
                    },
                ],
            }

            response = requests.post(
                f"{self.base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()

            body = response.json()
            content = body["choices"][0]["message"]["content"]
            parsed = self._safe_json(content)

            article.hebrew_summary = parsed.get("summary_he", "")
            article.category = parsed.get("category", article.category)
            article.hebrew_title = parsed.get("title_he", "")
            article.hebrew_source = parsed.get("source_he", "")
            article.actionable_takeaway_he = parsed.get("actionable_takeaway_he", "")

            explanations = parsed.get("terms", [])
            article.term_explanations = {
                item.get("term", ""): item.get("explanation_he", "")
                for item in explanations
                if item.get("term") and item.get("explanation_he")
            }

            if not article.hebrew_summary:
                return self._fallback_summary(article, article_context)

            if not article.term_explanations:
                article.term_explanations = self._extract_context_terms(article, article_context)

            return article

        except Exception:
            return self._fallback_summary(article, article_context)

    def summarize_many(self, articles: list[NewsArticle]) -> list[NewsArticle]:
        return [self.summarize(article) for article in articles]

    def _build_prompt(self, article: NewsArticle, article_context: str) -> str:
        return (
            "כתוב סיכום אמיתי עם ערך לקורא טכני בעברית.\n"
            "מטרות: מה חדש, למה זה חשוב, למי זה רלוונטי, ומה המגבלות או הסיכון.\n"
            "אל תחזור על סיסמאות שיווקיות. כתוב נקודות מדויקות.\n\n"
            "כל הפלט חייב להיות בעברית.\n"
            "Return valid JSON with this exact schema:\n"
            "{\n"
            '  "title_he": "string",\n'
            '  "source_he": "string",\n'
            '  "category": "new_models|new_tools|new_hacks|new_workflows|companies_ecosystem|general",\n'
            '  "summary_he": "string",\n'
            '  "terms": [{"term": "string", "explanation_he": "string"}],\n'
            '  "actionable_takeaway_he": "string"\n'
            "}\n\n"
            f"Source: {article.source}\n"
            f"Title: {article.title}\n"
            f"URL: {article.url}\n"
            f"Snippet: {article.summary[:1200]}\n\n"
            f"Article Context:\n{article_context[:4500]}"
        )

    def _safe_json(self, raw_text: str) -> dict[str, Any]:
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]

        return json.loads(cleaned)

    def _build_article_context(self, article: NewsArticle) -> str:
        summary_text = self._clean_text(article.summary)
        if summary_text and len(summary_text) > 100:
            return summary_text

        try:
            response = requests.get(
                article.url,
                timeout=self.timeout,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()

            chunks = []
            for item in soup.find_all(["h1", "h2", "p", "li"]):
                text = self._clean_text(item.get_text(" ", strip=True))
                if len(text) >= 40:
                    chunks.append(text)

            return "\n".join(chunks[:40])
        except Exception:
            return summary_text

    def _clean_text(self, text: str) -> str:
        if not text:
            return ""
        cleaned = BeautifulSoup(unescape(text), "html.parser").get_text(" ", strip=True)
        return " ".join(cleaned.split())

    def _fallback_summary(self, article: NewsArticle, article_context: str) -> NewsArticle:
        article.hebrew_title = self._heuristic_title(article)
        article.hebrew_source = ""
        article.category = self._heuristic_category(article, article_context)
        article.hebrew_summary = self._heuristic_summary(article, article_context)
        article.actionable_takeaway_he = self._heuristic_takeaway(article, article_context)
        article.term_explanations = self._extract_context_terms(article, article_context)
        return article

    def _heuristic_title(self, article: NewsArticle) -> str:
        return f"עדכון: {article.source}"

    def _heuristic_category(self, article: NewsArticle, article_context: str) -> str:
        text = f"{article.title} {article.summary} {article_context}".lower()

        category_rules = {
            "new_models": ["model", "llm", "release", "reasoning", "checkpoint"],
            "new_tools": ["tool", "sdk", "api", "platform", "plugin"],
            "new_hacks": ["hack", "trick", "optimization", "quantization", "lora"],
            "new_workflows": ["workflow", "agent", "automation", "pipeline", "orchestration"],
            "companies_ecosystem": ["funding", "company", "startup", "partnership", "acquisition"],
        }

        for category, words in category_rules.items():
            if any(word in text for word in words):
                return category
        return "general"

    def _heuristic_summary(self, article: NewsArticle, article_context: str) -> str:
        category = self._heuristic_category(article, article_context)
        category_messages = {
            "new_models": "העדכון מתמקד ביכולות מודל חדשות, בביצועים ובשיפור איכות התשובות.",
            "new_tools": "העדכון מתמקד בכלי פיתוח או תשתית חדשים שמקלים על בנייה ושילוב של פתרונות AI.",
            "new_hacks": "העדכון מתמקד בשיטות אופטימיזציה ושיפורי יעילות להפעלה מהירה וזולה יותר.",
            "new_workflows": "העדכון מתמקד בתהליכי עבודה אוטומטיים מבוססי סוכנים ושילוב רכיבי מערכת.",
            "companies_ecosystem": "העדכון מתמקד בשינויים באקו-סיסטם: חברות, שיתופי פעולה ואימוץ ארגוני.",
            "general": "העדכון מציג שינוי מעשי בתחום הבינה המלאכותית עם השפעה פוטנציאלית על פיתוח מוצר.",
        }
        focus = category_messages.get(category, category_messages["general"])
        return (
            f"{focus} "
            "ברמה המעשית, מומלץ לבחון התאמה לצוות הפיתוח, השפעה על עלויות תפעול ומהירות הטמעה בפרודקשן."
        )

    def _heuristic_takeaway(self, article: NewsArticle, article_context: str) -> str:
        text = f"{article.title} {article.summary} {article_context}".lower()
        if "security" in text or "guardrail" in text:
            return "מומלץ לבדוק הגדרות הרשאות, הפרדת זהויות סוכנים ולוגים לבקרת סיכוני אבטחה."
        if "cost" in text or "latency" in text or "inference" in text:
            return "מומלץ לבצע בדיקת עלות-תועלת על עומסי inference ולמדוד latency לפני מעבר לפרודקשן."
        if "workflow" in text or "agent" in text or "automation" in text:
            return "מומלץ להתחיל בפיילוט קטן עם תהליך אחד מדיד ולבחון ROI לפני הרחבה ארגונית."
        return "מומלץ לבדוק התאמה ל-Use Case קיים ולבנות פיילוט קצר עם מדדי הצלחה ברורים."

    def _extract_context_terms(self, article: NewsArticle, article_context: str) -> dict[str, str]:
        glossary = [
            {
                "label": "אחזור משולב יצירה (RAG)",
                "triggers": ["rag", "retrieval-augmented", "retrieval augmented"],
                "explanation": "שיטה שמשלבת שליפת מידע חיצוני בזמן יצירת תשובה כדי לשפר דיוק ועדכניות.",
            },
            {
                "label": "כיוונון עדין (Fine-tuning)",
                "triggers": ["fine-tuning", "finetuning"],
                "explanation": "התאמת מודל קיים למשימה ספציפית באמצעות אימון נוסף על דאטה ממוקד.",
            },
            {
                "label": "אינפרנס (Inference)",
                "triggers": ["inference"],
                "explanation": "שלב ההרצה של המודל על קלט חדש כדי לקבל תוצאה.",
            },
            {
                "label": "רב-מודאלי (Multimodal)",
                "triggers": ["multimodal"],
                "explanation": "יכולת לעבד כמה סוגי מידע יחד, למשל טקסט, תמונה ואודיו.",
            },
            {
                "label": "בנצ'מרק (Benchmark)",
                "triggers": ["benchmark"],
                "explanation": "מבחן השוואתי למדידת ביצועים של מודלים או מערכות.",
            },
            {
                "label": "שהיה (Latency)",
                "triggers": ["latency"],
                "explanation": "זמן ההשהיה מרגע בקשה ועד קבלת תשובה.",
            },
            {
                "label": "חלון הקשר (Context Window)",
                "triggers": ["context window"],
                "explanation": "כמות הטקסט שהמודל יכול להתחשב בה בכל קריאה.",
            },
            {
                "label": "סוכן חכם (Agent)",
                "triggers": ["agent", "agentic"],
                "explanation": "מערכת שמבצעת משימות באופן אוטונומי חלקי בעזרת מודל שפה וכלים.",
            },
            {
                "label": "הסקה רב-שלבית (Reasoning)",
                "triggers": ["reasoning"],
                "explanation": "יכולת לבצע הסקה רב-שלבית לפתרון בעיות מורכבות.",
            },
            {
                "label": "הזרקת פרומפט (Prompt Injection)",
                "triggers": ["prompt injection"],
                "explanation": "ניסיון זדוני לגרום למודל להתעלם מהוראות מערכת או מדיניות.",
            },
            {
                "label": "מגיני בטיחות (Guardrails)",
                "triggers": ["guardrails"],
                "explanation": "מנגנוני בטיחות שמגבילים פעולות או פלט בעייתי של המודל.",
            },
            {
                "label": "זיקוק מודל (Distillation)",
                "triggers": ["distillation"],
                "explanation": "העברת ידע ממודל גדול למודל קטן כדי לשפר יעילות.",
            },
            {
                "label": "קוונטיזציה (Quantization)",
                "triggers": ["quantization"],
                "explanation": "הקטנת דיוק מספרי של משקלי מודל כדי לחסוך זיכרון וחישוב.",
            },
            {
                "label": "לורה (LoRA)",
                "triggers": ["lora"],
                "explanation": "שיטת כיוונון יעילה שמעדכנת מספר קטן של פרמטרים.",
            },
        ]

        haystack = f"{article.title} {article.summary} {article_context}".lower()
        matched = {}
        for item in glossary:
            if any(trigger in haystack for trigger in item["triggers"]):
                matched[item["label"]] = item["explanation"]
            if len(matched) >= 3:
                break
        return matched

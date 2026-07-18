import json
import os
import re
from typing import Any
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup
from html import unescape

import requests

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

from app.models import NewsArticle


class HebrewSummarizer:
    def __init__(self, llm_config: dict[str, Any]):
        # Priority: env vars > config > smart defaults
        self.api_key = llm_config.get("api_key", "") or os.getenv("LLM_API_KEY", "")
        provider_env = os.getenv("LLM_PROVIDER", "")

        # Smart provider selection:
        # 1. If explicit provider in env
        # 2. If GitHub Actions + API_KEY exists, use Groq
        # 3. Otherwise try Ollama locally (unlimited, no rate limits)
        if provider_env:
            self.provider = provider_env
        elif os.getenv("GITHUB_ACTIONS") == "true" and self.api_key:
            self.provider = "groq"  # Use Groq only on GitHub Actions
        else:
            self.provider = llm_config.get("provider", "ollama")  # Default to Ollama

        # Configure provider-specific settings
        if self.provider == "groq":
            self.base_url = "https://api.groq.com/openai/v1"
            self.model = "llama-3.1-8b-instant"
        elif self.provider == "openai_compatible":
            self.base_url = "https://api.openai.com/v1"
            self.model = "gpt-4-turbo"
        else:  # ollama
            self.base_url = "http://localhost:11434"
            self.model = "mistral"

        # Allow env overrides
        self.base_url = os.getenv("LLM_BASE_URL", self.base_url)
        self.model = os.getenv("LLM_MODEL", self.model)
        self.timeout = int(llm_config.get("timeout_seconds", 60))

    def summarize(self, article: NewsArticle) -> NewsArticle:
        article_context = self._build_article_context(article)

        # Priority order: Groq/OpenAI > Ollama > Fallback
        if self.provider in ("groq", "openai_compatible"):
            return self._summarize_with_openai_compatible(article, article_context)

        if self.provider == "ollama":
            return self._summarize_with_ollama(article, article_context)

        # Fallback if nothing works
        return self._fallback_summary(article, article_context)

    def summarize_many(self, articles: list[NewsArticle]) -> list[NewsArticle]:
        return [self.summarize(article) for article in articles]

    def _summarize_with_openai_compatible(
        self, article: NewsArticle, article_context: str
    ) -> NewsArticle:
        """Use OpenAI-compatible API: Groq, OpenAI, etc."""
        if not self.api_key:
            print("⚠️  No LLM_API_KEY found. Set it: export LLM_API_KEY='your-key'")
            return self._fallback_summary(article, article_context)

        try:
            provider_name = "Groq" if self.provider == "groq" else "OpenAI"
            print(f"📡 Using {provider_name} for summarization...")

            payload = {
                "model": self.model,
                "temperature": 0.2,
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

            # Only add response_format for providers that support it
            if self.provider != "groq":
                payload["response_format"] = {"type": "json_object"}

            response = requests.post(
                f"{self.base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout,
            )

            if not response.ok:
                error_msg = response.text
                if self.provider == "groq":
                    print(f"⚠️  Groq error ({response.status_code}): {error_msg}")
                    print("💡 Falling back to heuristics...")
                    return self._fallback_summary(article, article_context)
                raise Exception(f"API error: {error_msg}")

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
                article.term_explanations = self._extract_context_terms(
                    article, article_context
                )

            return article

        except Exception as e:
            print(f"⚠️  LLM API error: {e}")
            return self._fallback_summary(article, article_context)

    def _summarize_with_ollama(
        self, article: NewsArticle, article_context: str
    ) -> NewsArticle:
        """Use local Ollama model for summarization."""
        if not OLLAMA_AVAILABLE:
            print("⚠️  Ollama library not installed. Run: pip install ollama")
            return self._fallback_summary(article, article_context)

        try:
            print("📡 Using Ollama (local) for summarization...")
            prompt = self._build_prompt(article, article_context)
            response = ollama.generate(
                model=self.model,
                prompt=prompt,
                stream=False,
                options={
                    "temperature": 0.2,
                    "num_ctx": 4096,
                },
            )

            content = response.get("response", "")
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
                article.term_explanations = self._extract_context_terms(
                    article, article_context
                )

            return article

        except Exception as e:
            print(f"⚠️  Ollama error: {e}")
            print("💡 Make sure Ollama is running: `ollama serve` in another terminal")
            return self._fallback_summary(article, article_context)

    def _build_prompt(self, article: NewsArticle, article_context: str) -> str:
        return (
            "Write a real summary with value for a technical Hebrew reader.\n"
            "Goals: what's new, why it matters, who it's relevant to, and what are limitations or risks.\n"
            "Don't repeat marketing slogans. Write precise points.\n\n"
            "All output must be in Hebrew.\n"
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

    def _fallback_summary(
        self, article: NewsArticle, article_context: str
    ) -> NewsArticle:
        article.hebrew_title = self._heuristic_title(article)
        article.hebrew_source = ""
        article.category = self._heuristic_category(article, article_context)
        article.hebrew_summary = self._heuristic_summary(article, article_context)
        article.actionable_takeaway_he = self._heuristic_takeaway(article, article_context)
        article.term_explanations = self._extract_context_terms(article, article_context)
        return article

    def _heuristic_title(self, article: NewsArticle) -> str:
        cleaned = self._normalize_title(article.title)
        if self._looks_generic_title(cleaned, article.source):
            slug_title = self._title_from_url(article.url)
            if slug_title:
                return slug_title
        return cleaned or f"Update: {article.source}"

    def _normalize_title(self, title: str) -> str:
        text = (title or "").strip()
        text = re.sub(r"\s+", " ", text)
        text = re.sub(
            r"\s*[\-|:]\s*(OpenAI|Anthropic|Cohere|VentureBeat|NVIDIA|AWS|Microsoft).*$",
            "",
            text,
            flags=re.IGNORECASE,
        )
        return text.strip(" -|")

    def _looks_generic_title(self, title: str, source: str) -> bool:
        if not title:
            return True
        lower_title = title.lower()
        lower_source = (source or "").lower()
        generic_tokens = {
            "news",
            "blog",
            "home",
            "ai blog",
            "updates",
            "latest",
            "cohere",
            "venturebeat",
        }
        if lower_title in generic_tokens:
            return True
        if lower_source and lower_title == lower_source:
            return True
        return len(lower_title) < 12

    def _title_from_url(self, url: str) -> str:
        path = urlparse(url).path.strip("/")
        if not path:
            return "AI Daily Update"
        part = path.split("/")[-1]
        part = unquote(part).replace("-", " ").replace("_", " ").strip()
        part = re.sub(r"\s+", " ", part)
        if not part:
            return "AI Daily Update"
        return f"Update: {part[:120]}"

    def _heuristic_category(self, article: NewsArticle, article_context: str) -> str:
        text = f"{article.title} {article.summary} {article_context}".lower()

        category_rules = {
            "new_models": ["model", "llm", "release", "reasoning", "checkpoint"],
            "new_tools": ["tool", "sdk", "api", "platform", "plugin"],
            "new_hacks": ["hack", "trick", "optimization", "quantization", "lora"],
            "new_workflows": ["workflow", "agent", "automation", "pipeline", "orchestration"],
            "companies_ecosystem": [
                "funding",
                "company",
                "startup",
                "partnership",
                "acquisition",
            ],
        }

        for category, words in category_rules.items():
            if any(word in text for word in words):
                return category
        return "general"

    def _heuristic_summary(self, article: NewsArticle, article_context: str) -> str:
        category = self._heuristic_category(article, article_context)
        category_messages = {
            "new_models": "Update focuses on new model capabilities, performance improvements, and output quality.",
            "new_tools": "Update focuses on new development tools or infrastructure that make it easier to build and integrate AI solutions.",
            "new_hacks": "Update focuses on optimization techniques and efficiency improvements for faster and cheaper execution.",
            "new_workflows": "Update focuses on automated workflows using agents and system component integration.",
            "companies_ecosystem": "Update focuses on ecosystem changes: companies, partnerships, and organizational adoption.",
            "general": "Update presents practical change in AI domain with potential impact on product development.",
        }
        focus = category_messages.get(category, category_messages["general"])

        key_lines = self._extract_focus_lines(article, article_context)
        numeric_signals = self._extract_numeric_signals(article, article_context)

        details = " ".join(key_lines) if key_lines else (
            "Article presents operational details on implementation, performance and impact on development processes."
        )
        if numeric_signals:
            details = f"{details} Key figures: {numeric_signals}."

        return (
            f"{details} {focus} "
            "In practice, consider alignment with development team, impact on operational costs and production deployment speed."
        )

    def _heuristic_takeaway(self, article: NewsArticle, article_context: str) -> str:
        text = f"{article.title} {article.summary} {article_context}".lower()
        if "security" in text or "guardrail" in text:
            return "Recommend checking permission settings, agent identity separation and logging for security risk control."
        if "cost" in text or "latency" in text or "inference" in text:
            return "Recommend cost-benefit analysis on inference loads and latency measurement before production deployment."
        if "workflow" in text or "agent" in text or "automation" in text:
            return "Recommend starting with a small pilot using one measurable process and ROI assessment before enterprise expansion."
        return "Recommend checking fit with existing use cases and building short pilot with clear success metrics."

    def _extract_context_terms(
        self, article: NewsArticle, article_context: str
    ) -> dict[str, str]:
        glossary = [
            {
                "label": "RAG (Retrieval-Augmented Generation)",
                "triggers": ["rag", "retrieval-augmented", "retrieval augmented"],
                "explanation": "Technique combining external information retrieval during response generation to improve accuracy and timeliness.",
            },
            {
                "label": "Fine-tuning",
                "triggers": ["fine-tuning", "finetuning"],
                "explanation": "Adapting existing model to specific task through additional training on focused data.",
            },
            {
                "label": "Inference",
                "triggers": ["inference"],
                "explanation": "Model execution phase on new input to produce output.",
            },
            {
                "label": "Multimodal",
                "triggers": ["multimodal"],
                "explanation": "Ability to process multiple data types together: text, image, audio.",
            },
            {
                "label": "Benchmark",
                "triggers": ["benchmark"],
                "explanation": "Comparative test for measuring model or system performance.",
            },
            {
                "label": "Latency",
                "triggers": ["latency"],
                "explanation": "Time delay from request to response.",
            },
            {
                "label": "Context Window",
                "triggers": ["context window"],
                "explanation": "Amount of text the model can consider in each call.",
            },
            {
                "label": "Agent",
                "triggers": ["agent", "agentic"],
                "explanation": "System that performs tasks semi-autonomously using language model and tools.",
            },
            {
                "label": "Reasoning",
                "triggers": ["reasoning"],
                "explanation": "Ability to perform multi-step reasoning for complex problem solving.",
            },
            {
                "label": "Prompt Injection",
                "triggers": ["prompt injection"],
                "explanation": "Malicious attempt to make model ignore system instructions or policy.",
            },
            {
                "label": "Guardrails",
                "triggers": ["guardrails"],
                "explanation": "Safety mechanisms limiting problematic model actions or output.",
            },
            {
                "label": "Distillation",
                "triggers": ["distillation"],
                "explanation": "Transferring knowledge from larger to smaller model to improve efficiency.",
            },
            {
                "label": "Quantization",
                "triggers": ["quantization"],
                "explanation": "Reducing numeric precision of model weights to save memory and computation.",
            },
            {
                "label": "LoRA",
                "triggers": ["lora"],
                "explanation": "Efficient fine-tuning technique updating small number of parameters.",
            },
        ]

        haystack = f"{article.title} {article.summary} {article_context}".lower()
        matched = {}
        for item in glossary:
            if any(trigger in haystack for trigger in item["triggers"]):
                matched[item["label"]] = item["explanation"]
            if len(matched) >= 3:
                break

        if len(matched) < 3:
            acronyms = self._extract_acronyms(
                f"{article.title} {article.summary} {article_context}"
            )
            for term in acronyms:
                if term in matched:
                    continue
                matched[term] = "Technical term mentioned in article. Refer to official product documentation for context."
                if len(matched) >= 3:
                    break

        return matched

    def _extract_focus_lines(
        self, article: NewsArticle, article_context: str
    ) -> list[str]:
        raw = self._clean_text(f"{article.summary} {article_context}")
        if not raw:
            return []

        # Split by sentence and keep informative lines, skipping obvious boilerplate/navigation.
        candidates = re.split(r"(?<=[.!?])\s+", raw)
        blocked_tokens = [
            "cookie",
            "privacy",
            "terms",
            "subscribe",
            "menu",
            "sign in",
            "all rights reserved",
        ]

        selected = []
        for sentence in candidates:
            s = sentence.strip()
            if len(s) < 60 or len(s) > 260:
                continue
            lower = s.lower()
            if any(token in lower for token in blocked_tokens):
                continue
            selected.append(self._light_english_wrap(s))
            if len(selected) >= 2:
                break
        return selected

    def _extract_numeric_signals(self, article: NewsArticle, article_context: str) -> str:
        text = f"{article.title} {article.summary} {article_context}"
        matches = re.findall(
            r"\b\d+(?:\.\d+)?\s?(?:%|x|X|k|K|m|M|b|B|ms|s|sec|seconds|minutes|hours)?\b",
            text,
        )
        cleaned = []
        for m in matches:
            m2 = m.strip()
            if len(m2) <= 1:
                continue
            cleaned.append(m2)
            if len(cleaned) >= 4:
                break
        return ", ".join(cleaned)

    def _extract_acronyms(self, text: str) -> list[str]:
        candidates = re.findall(r"\b[A-Z]{2,8}\b", text)
        banned = {"AI", "LLM", "API", "AWS", "NVIDIA", "OPENAI"}
        results = []
        for item in candidates:
            if item in banned:
                continue
            if item not in results:
                results.append(item)
            if len(results) >= 3:
                break
        return results

    def _light_english_wrap(self, text: str) -> str:
        replacements = {
            "agent": "agent",
            "agents": "agents",
            "workflow": "workflow",
            "workflows": "workflows",
            "inference": "inference",
            "latency": "latency",
            "benchmark": "benchmark",
            "multimodal": "multimodal",
            "security": "security",
        }
        out = text
        for en, wrapped in replacements.items():
            out = re.sub(rf"\b{re.escape(en)}\b", wrapped, out, flags=re.IGNORECASE)
        return out


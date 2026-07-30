"""
RunMetrics — accumulate pipeline measurements and push to Prometheus Pushgateway.

HOW IT WORKS
------------
1. At the start of main.py we create a RunMetrics() instance.
2. Every stage in the pipeline records its numbers on that object
   (e.g. how many articles each source returned, how many tokens were spent).
3. At the very end of main.py we call metrics.push(), which serialises
   everything as Prometheus Gauge metrics and sends them to the Pushgateway
   in a single HTTP PUT request.
4. Prometheus scrapes the Pushgateway on its regular interval and stores
   each push as a new data point in its time-series database.
5. Grafana queries Prometheus and draws the graphs.

If PUSHGATEWAY_URL is not set the whole thing is a no-op, so the script
still works with no monitoring stack running.
"""

import os
from dataclasses import dataclass, field


@dataclass
class RunMetrics:
    # --- article pipeline ---
    articles_per_source: dict[str, int] = field(default_factory=dict)
    collection_errors_per_source: dict[str, int] = field(default_factory=dict)
    articles_after_dedup: int = 0
    articles_after_filter: int = 0
    articles_in_report: int = 0

    # --- LLM / token usage ---
    llm_prompt_tokens: int = 0
    llm_completion_tokens: int = 0
    llm_calls: int = 0       # real API calls
    llm_fallbacks: int = 0   # times we skipped the LLM and used heuristics

    # --- delivery ---
    email_sent: bool = False

    # --- overall run ---
    run_duration_seconds: float = 0.0
    run_success: bool = False

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def push(self, job: str = "ai_news_agent") -> None:
        """Push all accumulated metrics to the Prometheus Pushgateway.

        Reads the target URL from the PUSHGATEWAY_URL environment variable.
        Silently skips if the variable is absent or empty.
        """
        pushgateway_url = os.getenv("PUSHGATEWAY_URL", "").strip()
        if not pushgateway_url:
            print("PUSHGATEWAY_URL not set — skipping metrics push.")
            return

        try:
            from prometheus_client import CollectorRegistry, Gauge, push_to_gateway
        except ImportError:
            print("prometheus_client not installed — skipping metrics push.")
            return

        registry = CollectorRegistry()

        def _g(name: str, doc: str, label_names: list[str] | None = None) -> Gauge:
            return Gauge(name, doc, label_names or [], registry=registry)

        # Run-level
        _g("ai_news_agent_run_duration_seconds",
           "Total pipeline wall-clock time in seconds").set(self.run_duration_seconds)
        _g("ai_news_agent_run_success",
           "1 if the run completed without an uncaught exception").set(int(self.run_success))
        _g("ai_news_agent_email_sent",
           "1 if the report email was delivered successfully").set(int(self.email_sent))

        # Article pipeline
        _g("ai_news_agent_articles_after_dedup",
           "Articles remaining after deduplication").set(self.articles_after_dedup)
        _g("ai_news_agent_articles_after_filter",
           "Articles passing the relevance score filter").set(self.articles_after_filter)
        _g("ai_news_agent_articles_in_report",
           "Articles included in the final report").set(self.articles_in_report)

        # Per-source collection counts
        source_gauge = _g(
            "ai_news_agent_articles_collected",
            "Raw articles collected from each RSS/HTML source",
            ["source"],
        )
        for source, count in self.articles_per_source.items():
            source_gauge.labels(source=source).set(count)

        # Per-source collection errors
        error_gauge = _g(
            "ai_news_agent_collection_errors",
            "Number of collection failures per source",
            ["source"],
        )
        for source, count in self.collection_errors_per_source.items():
            error_gauge.labels(source=source).set(count)

        # LLM / token usage
        _g("ai_news_agent_llm_prompt_tokens",
           "Total prompt tokens sent to the LLM this run").set(self.llm_prompt_tokens)
        _g("ai_news_agent_llm_completion_tokens",
           "Total completion tokens received from the LLM this run").set(self.llm_completion_tokens)
        _g("ai_news_agent_llm_calls",
           "Number of real LLM API calls made").set(self.llm_calls)
        _g("ai_news_agent_llm_fallbacks",
           "Times heuristic fallback replaced a real LLM call").set(self.llm_fallbacks)

        try:
            push_to_gateway(pushgateway_url, job=job, registry=registry)
            print(f"Metrics pushed to Pushgateway at {pushgateway_url}")
        except Exception as exc:
            # Never crash the pipeline because of metrics
            print(f"Metrics push failed (non-fatal): {exc}")

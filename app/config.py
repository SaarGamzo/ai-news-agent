from pathlib import Path
import os

import yaml


def load_config(config_path: str = "config.yaml") -> dict:
    path = Path(config_path)
    with path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}

    config.setdefault("sources", [])
    config.setdefault("filter", {})
    config.setdefault("report", {})
    config.setdefault("llm", {})
    config.setdefault("email", {})

    llm = config["llm"]
    llm_api_key = os.getenv("LLM_API_KEY")
    if llm_api_key:
        llm["api_key"] = llm_api_key

    llm_model = os.getenv("LLM_MODEL")
    if llm_model:
        llm["model"] = llm_model

    llm_base_url = os.getenv("LLM_BASE_URL")
    if llm_base_url:
        llm["base_url"] = llm_base_url

    email = config["email"]
    if os.getenv("EMAIL_ENABLED"):
        email["enabled"] = os.getenv("EMAIL_ENABLED", "false").lower() in {"1", "true", "yes"}
    if os.getenv("SMTP_HOST"):
        email["smtp_host"] = os.getenv("SMTP_HOST")
    if os.getenv("SMTP_PORT"):
        email["smtp_port"] = int(os.getenv("SMTP_PORT", "587"))
    if os.getenv("SMTP_SENDER"):
        email["sender"] = os.getenv("SMTP_SENDER")
    if os.getenv("SMTP_USERNAME"):
        email["username"] = os.getenv("SMTP_USERNAME")
    if os.getenv("SMTP_PASSWORD"):
        email["password"] = os.getenv("SMTP_PASSWORD")
    if os.getenv("EMAIL_RECIPIENTS"):
        email["recipients"] = [
            item.strip()
            for item in os.getenv("EMAIL_RECIPIENTS", "").split(",")
            if item.strip()
        ]

    return config
# AI News Agent

Daily AI news collector and reporter.

The agent:
- Collects articles from 10 AI-focused sources.
- Scores and filters the most important updates.
- Summarizes each item in Hebrew.
- Explains only article-specific advanced terms in simple Hebrew.
- Builds an HTML report with links to original news.
- Sends a compact morning email digest.

## Quick Start

1. Create and activate virtualenv:

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Configure:
- Edit `config.yaml`.
- Optional: set `LLM_API_KEY` (Gemini). If quota is unavailable, the app still produces heuristic Hebrew summaries for free.
- Set email settings under `email` and enable sending.

Optional local setup with env file:
```bash
cp .env.example .env
# Fill values inside .env
set -a && source .env && set +a
```

4. Run:

```bash
python main.py
```

The report is saved under `reports/`.

## Notes

- If LLM API is unavailable (missing key/quota/network), the app generates free heuristic Hebrew summaries.
- For production use, keep secrets out of `config.yaml` and load from environment variables or a secret manager.
- Gemini (free-tier friendly) OpenAI-compatible endpoint:
	- `LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai`
	- `LLM_MODEL=gemini-2.0-flash`

## Daily 08:00 Automation (GitHub Actions)

Workflow file:
- `.github/workflows/daily-ai-news-report.yml`

Behavior:
- Triggered hourly by cron.
- Runs the report only at `08:00` in `Asia/Jerusalem` time (handles DST correctly).

Required repository secrets:
- `LLM_API_KEY` (optional, Gemini API key)
- `LLM_MODEL` (optional, for example `gemini-2.0-flash`)
- `LLM_BASE_URL` (optional, `https://generativelanguage.googleapis.com/v1beta/openai`)
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_SENDER`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `EMAIL_RECIPIENTS` (comma-separated, for example `saar.gamzo@intel.com`)

The workflow also commits generated report files under `reports/` back to the repository.
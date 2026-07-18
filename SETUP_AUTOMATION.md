# 🤖 Automated Daily AI News Generation

## How It Works

### 💻 **Local Terminal** (run manually)
- Uses **Ollama** (free, no API key required)
- Requires `ollama serve` running in separate terminal

### ☁️ **GitHub Actions** (automatic daily at 11:00 Israel time)
- Uses **Groq** (free tier, limited API key in Secrets)
- Runs automatically - no manual intervention needed

---

## Setup Guide

### 1️⃣ **Local Ollama Setup** (for manual runs)

```bash
# Download from https://ollama.ai
# After installation:
ollama pull mistral
ollama serve  # Keep running in separate terminal
```

In another terminal:
```bash
python main.py
```

---

### 2️⃣ **GitHub Actions with Groq** (for automation)

#### Get Groq API Key:
1. Visit https://console.groq.com
2. Sign up (free, no credit card required)
3. Copy your API key

#### Add to GitHub Secrets:
1. In repo: **Settings → Secrets and variables → Actions**
2. Click: **New repository secret**
3. Name: `GROQ_API_KEY`
4. Value: [Paste your API key]
5. Save

#### Verify Workflow runs:
1. In repo: **Actions**
2. Select: **Daily AI News Report**
3. Click: **Run workflow**

✅ Report will appear in `reports/` daily at 11:00 Israel time!

---

## FAQ

**Q: Is Groq free?**
- A: ✅ Yes! Free tier includes 30 requests/minute, sufficient for this use case.

**Q: Why am I seeing Ollama error?**
- A: Need to run `ollama serve` in separate terminal before `python main.py`.

**Q: How to change daily run time?**
- A: Edit [`.github/workflows/daily_news_report.yml`](.github/workflows/daily_news_report.yml#L8) - modify the `cron` expression.

**Q: Does the report auto-commit to GitHub?**
- A: ✅ Yes! After each run, report is automatically pushed to repo.

---

## Troubleshooting

### Workflow failures on GitHub?
```bash
# Check logs:
# Actions → Daily AI News Report → Latest run → Logs
```

### Ollama not responding?
```bash
# Verify Ollama is running:
curl http://localhost:11434/api/tags
```

### Groq rate limit exceeded?
- Limited to 30 req/minute on free tier
- Upgrade to paid plan for higher limits

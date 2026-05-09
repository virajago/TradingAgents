# AI Analyst Weekly

Hedge-fund-quality stock research, delivered weekly. Built on the [TradingAgents](https://arxiv.org/abs/2412.20138) multi-agent LLM framework.

**Stack:** FastAPI · Supabase · Cloud Run · Cloudflare Pages · Stripe · Resend · Loops.so

---

⚡ [Local Dev](#local-development-web-app) | 🚀 [Deploy to Production](#production-deployment) | 💻 [CLI](#installation-and-cli) | 📦 [Python Package](#tradingagents-package) | 🔬 [Framework](#tradingagents-framework)

---

## AI Analyst Weekly — SaaS Product

A production SaaS built on the TradingAgents engine. Delivers hedge-fund-quality stock research to retail investors via weekly email digests, on-demand analysis, and real-time red flag alerts.

**Pricing:** Credit packs — Starter (100 credits/$19), Pro (300 credits/$39), Unlimited ($79). 7-day free trial.

**Credit costs:** On-demand analysis = 10 credits · Weekly digest per ticker = 3 credits · Alert = 1 credit

---

## Local Development (Web App)

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) — fast Python package manager (`brew install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- [Supabase CLI](https://supabase.com/docs/guides/cli) (`brew install supabase/tap/supabase`)
- At least one LLM API key (Anthropic or Google recommended)

### 1. Clone and install

```bash
git clone https://github.com/virajago/TradingAgents.git
cd TradingAgents

# Create and activate virtual environment
uv venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Install core engine + SaaS dependencies
uv pip install .
uv pip install -r saas/requirements.txt
```

**Without uv** (standard pip):

```bash
python -m venv .venv
source .venv/bin/activate
pip install .
pip install -r saas/requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Minimum required for local dev:

```bash
# Supabase local (filled automatically after step 3)
SUPABASE_URL=http://localhost:54321
SUPABASE_ANON_KEY=<from supabase start output>
SUPABASE_SERVICE_ROLE_KEY=<from supabase start output>
SUPABASE_JWT_SECRET=<from supabase start output>
DATABASE_URL=postgresql://postgres:postgres@localhost:54322/postgres

# LLM — choose one or more
ANTHROPIC_API_KEY=sk-ant-...       # Claude — best for on-demand analysis
GOOGLE_API_KEY=AIza...             # Gemini — best for weekly batch (cheaper)

# Stripe test mode
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_STARTER=price_...
STRIPE_PRICE_PRO=price_...
STRIPE_PRICE_UNLIMITED=price_...

# Email
RESEND_API_KEY=re_...

# Internal cron auth
INTERNAL_API_SECRET=any-random-string-for-local-dev

ENVIRONMENT=development
```

### 3. Start Supabase locally

```bash
supabase start                        # Postgres + Auth on localhost:54321
supabase db push saas/db/schema.sql   # apply full schema + RLS policies
```

Copy the printed `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, and `SUPABASE_JWT_SECRET` into `.env`.

### 4. Start the API server

```bash
uvicorn saas.api.main:app --reload --port 8000
```

API live at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### 5. Open the web app

```bash
# Serve all pages locally
cd ~/.gstack/projects/virajago-TradingAgents/designs
python -m http.server 3000
# Open http://localhost:3000
```

Or open individual pages directly:

```bash
open ~/.gstack/projects/virajago-TradingAgents/designs/landing-page-20260509/finalized.html
open ~/.gstack/projects/virajago-TradingAgents/designs/dashboard-20260509/finalized.html
open ~/.gstack/projects/virajago-TradingAgents/designs/analysis-page-20260509/finalized.html
```

### 6. Test an analysis run

```bash
# Trigger on-demand analysis
curl -X POST http://localhost:8000/analyze \
  -H "Authorization: Bearer <supabase-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"ticker": "NVDA"}'

# Poll for status (Analyst Briefing Room)
curl http://localhost:8000/analyze/<task_id>/status \
  -H "Authorization: Bearer <supabase-jwt>"

# Trigger a batch run directly
curl -X POST http://localhost:8000/internal/batch/run \
  -H "x-internal-secret: any-random-string-for-local-dev"
```

### 7. Test Stripe webhooks locally

```bash
# Install Stripe CLI: brew install stripe/stripe-cli/stripe
stripe listen --forward-to localhost:8000/webhooks/stripe
# Copy the printed webhook secret to .env as STRIPE_WEBHOOK_SECRET
```

---

## Production Deployment

### Architecture

```
Cloudflare Pages   → Static HTML frontend (9 pages)
Cloudflare CDN     → SSL, DDoS, asset caching
Cloudflare AI GW   → LLM API proxy (caching + cost analytics)

Cloud Run          → FastAPI backend + async analysis workers
Cloud Scheduler    → Sunday 8pm ET batch trigger
                   → Every 5 min alert monitor
                   → Daily verdict settlement

Supabase           → Postgres + Auth + RLS + Supavisor connection pooling
Stripe             → Credit pack subscriptions (3 tiers, 7-day trial)
Resend             → Transactional email (digest, alerts, receipts)
Finnhub            → Real-time market event monitoring
Loops.so           → Lifecycle email sequences (trial nudges, onboarding)
```

### 1. Create Supabase project

1. Create a project at [supabase.com](https://supabase.com) in the **us-east-1** region
2. Apply the schema:

```bash
supabase db push saas/db/schema.sql \
  --db-url "postgresql://postgres:<password>@db.<ref>.supabase.co:5432/postgres"
```

3. Copy **URL**, **anon key**, **service role key**, **JWT secret**, and **database URL (Supavisor pooler)** from Project Settings → API.

### 2. Create Stripe products

```bash
# Starter — $19/month, 100 credits
stripe prices create --product-data[name]="Starter" \
  --unit-amount 1900 --currency usd --recurring[interval]=month

# Pro — $39/month, 300 credits
stripe prices create --product-data[name]="Pro" \
  --unit-amount 3900 --currency usd --recurring[interval]=month

# Unlimited — $79/month, 10,000 credits
stripe prices create --product-data[name]="Unlimited" \
  --unit-amount 7900 --currency usd --recurring[interval]=month
```

Enable 7-day free trials on each price in the Stripe dashboard.

### 3. Deploy to Cloud Run

**Option A — Cloud Build CI/CD (recommended):**

```bash
# Connect your repo in GCP Cloud Build → Triggers
# Every push to main auto-deploys via cloudbuild.yaml
gcloud builds submit --config cloudbuild.yaml
```

**Option B — Direct deploy:**

```bash
gcloud run deploy ai-analyst-weekly \
  --source . \
  --region us-east1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --min-instances 1 \
  --max-instances 10 \
  --concurrency 80
```

Set all environment variables on the service:

```bash
gcloud run services update ai-analyst-weekly --region us-east1 \
  --set-env-vars "ENVIRONMENT=production,\
SUPABASE_URL=https://<ref>.supabase.co,\
SUPABASE_ANON_KEY=...,\
SUPABASE_SERVICE_ROLE_KEY=...,\
SUPABASE_JWT_SECRET=...,\
DATABASE_URL=postgresql://postgres.<ref>:<pw>@aws-0-us-east-1.pooler.supabase.com:6543/postgres,\
ANTHROPIC_API_KEY=...,\
GOOGLE_API_KEY=...,\
STRIPE_SECRET_KEY=sk_live_...,\
STRIPE_WEBHOOK_SECRET=whsec_...,\
STRIPE_PRICE_STARTER=price_...,\
STRIPE_PRICE_PRO=price_...,\
STRIPE_PRICE_UNLIMITED=price_...,\
RESEND_API_KEY=re_...,\
RESEND_FROM_EMAIL=weekly@yourdomain.com,\
FINNHUB_API_KEY=...,\
LOOPS_API_KEY=...,\
INTERNAL_API_SECRET=<long-random-string>,\
MAX_CONCURRENT_ANALYSES=20"
```

### 4. Set up Cloud Scheduler

```bash
CLOUD_RUN_URL=https://ai-analyst-weekly-xxxx-ue.a.run.app
SECRET=<your-INTERNAL_API_SECRET>

# Weekly digest — Sunday 8pm ET (Monday 00:00 UTC)
gcloud scheduler jobs create http weekly-digest \
  --location us-east1 \
  --schedule "0 0 * * MON" \
  --uri "$CLOUD_RUN_URL/internal/batch/run" \
  --http-method POST \
  --headers "x-internal-secret=$SECRET"

# Alert monitor — every 5 minutes
gcloud scheduler jobs create http alert-monitor \
  --location us-east1 \
  --schedule "*/5 * * * *" \
  --uri "$CLOUD_RUN_URL/internal/alerts/check" \
  --http-method POST \
  --headers "x-internal-secret=$SECRET"

# Verdict settlement — daily at 10am UTC
gcloud scheduler jobs create http verdict-settler \
  --location us-east1 \
  --schedule "0 10 * * *" \
  --uri "$CLOUD_RUN_URL/internal/verdicts/settle" \
  --http-method POST \
  --headers "x-internal-secret=$SECRET"
```

### 5. Deploy frontend to Cloudflare Pages

```bash
npm install -g wrangler && wrangler login

wrangler pages deploy \
  ~/.gstack/projects/virajago-TradingAgents/designs \
  --project-name ai-analyst-weekly
```

Or connect your GitHub repo in the Cloudflare Pages dashboard.

### 6. Configure Stripe webhook

In Stripe Dashboard → Webhooks, add endpoint `https://<cloud-run-url>/webhooks/stripe` and select:
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.payment_succeeded`
- `invoice.payment_failed`

### 7. Email domain warming

**Start this immediately** — new domains need 4-6 weeks before bulk sends land reliably in primary inbox.

```bash
# Add your domain in Resend → configure SPF, DKIM, DMARC DNS records
# Send 5-10 test emails/day for 4 weeks before the first Sunday batch
```

### 8. Verify production

```bash
curl https://<cloud-run-url>/health
# → {"status": "ok"}

curl -X POST https://<cloud-run-url>/internal/batch/run \
  -H "x-internal-secret: <INTERNAL_API_SECRET>"
```

---

## Installation and CLI

### Installation

**With uv (recommended):**

```bash
git clone https://github.com/virajago/TradingAgents.git
cd TradingAgents

uv venv --python 3.13
source .venv/bin/activate   # Windows: .venv\Scripts\activate
uv pip install .
```

**With conda:**

```bash
git clone https://github.com/virajago/TradingAgents.git
cd TradingAgents

conda create -n tradingagents python=3.13
conda activate tradingagents
pip install .
```

### Docker

```bash
cp .env.example .env  # add your API keys
docker compose run --rm tradingagents

# With Ollama for local models:
docker compose --profile ollama run --rm tradingagents-ollama
```

### Required API keys

```bash
export OPENAI_API_KEY=...          # OpenAI (GPT)
export GOOGLE_API_KEY=...          # Google (Gemini)
export ANTHROPIC_API_KEY=...       # Anthropic (Claude)
export DEEPSEEK_API_KEY=...        # DeepSeek
export DASHSCOPE_API_KEY=...       # Qwen (Alibaba)
export ZHIPU_API_KEY=...           # GLM (Zhipu)
export ALPHA_VANTAGE_API_KEY=...   # Alpha Vantage (optional)
```

For enterprise providers (Azure OpenAI, AWS Bedrock), copy `.env.enterprise.example` to `.env.enterprise`.

### CLI Usage

```bash
tradingagents          # installed command
python -m cli.main     # run from source
```

<p align="center">
  <img src="assets/cli/cli_init.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

<p align="center">
  <img src="assets/cli/cli_news.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

<p align="center">
  <img src="assets/cli/cli_transaction.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

---

## TradingAgents Package

### Python Usage

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

# CLI / research usage
ta = TradingAgentsGraph(debug=True, config=DEFAULT_CONFIG.copy())
_, decision = ta.propagate("NVDA", "2026-01-15")
print(decision)

# SaaS / multi-user usage
ta = TradingAgentsGraph(
    config=DEFAULT_CONFIG.copy(),
    user_id="user_abc123",     # scopes checkpoints + memory log per user
    supabase_client=supabase,  # enables per-user Postgres memory log
)
_, decision = ta.propagate("NVDA", "2026-01-15")
```

Configure models and debate depth:

```python
config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "anthropic"       # openai, google, anthropic, deepseek, qwen, glm, ollama, azure
config["deep_think_llm"] = "claude-sonnet-4-6"
config["quick_think_llm"] = "gemini-2.5-flash"
config["max_debate_rounds"] = 2

ta = TradingAgentsGraph(config=config)
_, decision = ta.propagate("NVDA", "2026-01-15")
```

See `tradingagents/default_config.py` for all options.

### Persistence and Recovery

**Decision log** — always on. Each run appends to `~/.tradingagents/memory/trading_memory.md`. On the next run for the same ticker, TradingAgents fetches the realised return, generates a reflection, and injects past decisions into the Portfolio Manager prompt.

Override path: `TRADINGAGENTS_MEMORY_LOG_PATH`

In SaaS mode, the decision log is stored per-user in Supabase (`memory_log` table) instead of a shared file.

**Checkpoint resume** — opt-in via `--checkpoint`. Resumes from the last successful LangGraph node on crash or interruption.

```bash
tradingagents analyze --checkpoint        # enable
tradingagents analyze --clear-checkpoints # reset before run
```

```python
config["checkpoint_enabled"] = True
```

---

## TradingAgents Framework

TradingAgents is a multi-agent trading framework that mirrors the dynamics of real-world trading firms. Specialized LLM-powered agents — fundamental analysts, sentiment experts, technical analysts, researchers, trader, and risk management — collaboratively evaluate market conditions and debate trading decisions.

<p align="center">
  <img src="assets/schema.png" style="width: 100%; height: auto;">
</p>

> Designed for research purposes. Not intended as financial, investment, or trading advice. [Disclaimer](https://tauric.ai/disclaimer/)

### Analyst Team

- **Fundamentals Analyst** — evaluates company financials, intrinsic value, and red flags
- **Sentiment Analyst** — analyzes social media and public sentiment
- **News Analyst** — monitors global news and macroeconomic indicators
- **Technical Analyst** — detects trading patterns via MACD, RSI, and other indicators

<p align="center">
  <img src="assets/analyst.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

### Researcher Team

Bull and bear researchers critically assess analyst insights through structured debate, balancing potential gains against risks.

<p align="center">
  <img src="assets/researcher.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

### Trader + Risk + Portfolio Manager

The Trader synthesizes analyst and researcher reports into a trade proposal. The Risk Management team evaluates portfolio risk. The Portfolio Manager makes the final decision.

<p align="center">
  <img src="assets/risk.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

Built with LangGraph. Supports: OpenAI, Google, Anthropic, xAI, DeepSeek, Qwen, GLM, OpenRouter, Ollama, Azure OpenAI.

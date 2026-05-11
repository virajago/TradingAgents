# Conviction

Hedge-fund-quality stock research, delivered weekly. Built on the TradingAgents multi-agent LLM framework.

**Stack:** FastAPI · Supabase · Stripe · Resend · Loops.so · LiteLLM

---

⚡ [Local Dev](#local-development) | 💻 [CLI](#installation-and-cli) | 📦 [Python Package](#tradingagents-package) | 🔬 [Framework](#tradingagents-framework)

---

## Conviction — SaaS Product

A production SaaS built on the TradingAgents engine. Delivers hedge-fund-quality stock research to retail investors via weekly email digests, on-demand analysis, and real-time red flag alerts.

**Pricing:** Credit packs — Starter (100 credits/$19), Pro (300 credits/$39), Unlimited ($79). 7-day free trial.

**Credit costs:** On-demand analysis = 10 credits · Weekly digest per ticker = 3 credits · Alert = 1 credit

**Architecture:**
```
Single container (Dockerfile)
  ├── FastAPI backend   — all API routes (/auth, /analyze, /watchlist, ...)
  ├── Frontend          — static HTML served at / (index.html, dashboard.html, ...)
  └── Workers           — async analysis pipeline, batch scheduler, alert monitor

Supabase              — Postgres + Auth + RLS
Stripe                — credit pack subscriptions (3 tiers, 7-day trial)
Resend                — transactional email (digest, alerts)
Loops.so              — lifecycle email sequences
Finnhub               — real-time market event monitoring
LiteLLM               — provider-agnostic LLM routing (Claude, Gemini, GPT-4o, DeepSeek)
```

**Pipeline:** 8 AI agents run in 3 phases. Phase 1 (4 analysts) runs in parallel, Phase 2 (bull+bear researchers) runs in parallel, Phase 3 (research manager → trader → portfolio manager) runs sequentially. Total analysis time: ~90 seconds.

---

## Local Development

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) — fast Python package manager (`brew install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- [Supabase CLI](https://supabase.com/docs/guides/cli) (`brew install supabase/tap/supabase`)
- At least one LLM API key (Anthropic or Google recommended)

### 1. Clone and install

```bash
git clone https://github.com/virajago/conviction.git
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

# LLM — Phase 1 analysts (fast + cheap)
GOOGLE_API_KEY=AIza...             # Gemini 2.5 Flash

# LLM — Phase 2+3 synthesis (quality reasoning)
ANTHROPIC_API_KEY=sk-ant-...       # Claude Sonnet

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

### 4. Start the server

One command starts everything — API + frontend:

```bash
uvicorn saas.api.main:app --reload --port 8000
```

- Web app: `http://localhost:8000` (landing page)
- Sign in: `http://localhost:8000/signin`
- Dashboard: `http://localhost:8000/dashboard`
- API docs: `http://localhost:8000/docs`

### 5. Test an analysis run

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

### 6. Test Stripe webhooks locally

```bash
# Install Stripe CLI: brew install stripe/stripe-cli/stripe
stripe listen --forward-to localhost:8000/webhooks/stripe
# Copy the printed webhook secret to .env as STRIPE_WEBHOOK_SECRET
```

---

## Production Deployment

**Platform:** Google Cloud Run + Supabase

The app deploys as a **single container** that serves both the frontend (static HTML) and the backend (FastAPI). One URL, one service, one deploy command.

```
Cloud Run        → single container: frontend + API + async workers
Cloud Scheduler  → 3 cron jobs triggering /internal/* endpoints ($0.30/mo)
Supabase         → Postgres + Auth + RLS (free tier covers ~35 users)
```

**Free tier:** Cloud Run free tier (2M requests + 360k vCPU-seconds/month) covers ~35 users at zero compute cost. Only Cloud Scheduler has a cost: $0.10/job × 3 jobs = **$0.30/month**.

### Prerequisites

- [gcloud CLI](https://cloud.google.com/sdk/docs/install) installed and authenticated
- GCP project created with billing enabled
- Supabase project created at [supabase.com](https://supabase.com) (us-east-1 region)
- Stripe products created (see Stripe setup below)

### 1. Configure environment

```bash
cp .env.production.example .env.production
# Fill in all values — see comments in the file
```

Required values: Supabase URL/keys, Anthropic + Google API keys, Stripe keys + price IDs, Resend API key, `INTERNAL_API_SECRET` (generate with `openssl rand -hex 32`).

### 2. Set GCP project

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

### 3. Deploy

```bash
./deploy.sh
```

This single script:
1. Enables required GCP APIs (Cloud Run, Cloud Build, Cloud Scheduler)
2. Applies the Supabase schema (`saas/db/schema.sql`)
3. Builds and pushes the Docker image via Cloud Build
4. Deploys to Cloud Run with all environment variables
5. Creates the 3 Cloud Scheduler cron jobs
6. Runs a health check and prints the live URL

Re-running `./deploy.sh` is safe — all steps are idempotent.

### 4. Stripe webhook (manual, one-time)

After the first deploy, go to [Stripe Dashboard → Webhooks](https://dashboard.stripe.com/webhooks):

1. Add endpoint: `https://<your-cloud-run-url>/webhooks/stripe`
2. Select events: `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_succeeded`, `invoice.payment_failed`
3. Copy the signing secret → add to `.env.production` as `STRIPE_WEBHOOK_SECRET`
4. Re-run `./deploy.sh` to update the Cloud Run env var

### 5. Stripe products (one-time setup)

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

Enable 7-day free trials on each price in the Stripe dashboard. Copy the 3 price IDs to `.env.production`.

### Email domain warming

**Start this immediately** — new domains need 4-6 weeks before bulk sends land reliably in primary inbox. Add your domain in Resend, configure SPF/DKIM/DMARC DNS records, and send 5-10 test emails per day for 4 weeks before the first Sunday batch.

### CI/CD (automatic deploys)

Connect your GitHub repo in [GCP Cloud Build → Triggers](https://console.cloud.google.com/cloud-build/triggers). Select the repo, branch `main`, and trigger file `cloudbuild.yaml`. Every push to `main` will automatically build and deploy.

### Useful commands

```bash
# View live logs
gcloud run logs tail conviction --region=us-east1

# Check service status
gcloud run services describe conviction --region=us-east1

# Trigger batch manually
curl -X POST https://<your-url>/internal/batch/run \
  -H "x-internal-secret: $INTERNAL_API_SECRET"

# Health check
curl https://<your-url>/health
```

---

## Installation and CLI

### Installation

**With uv (recommended):**

```bash
git clone https://github.com/virajago/conviction.git
cd TradingAgents

uv venv --python 3.11
source .venv/bin/activate   # Windows: .venv\Scripts\activate
uv pip install .
```

**With conda:**

```bash
git clone https://github.com/virajago/conviction.git
cd TradingAgents

conda create -n tradingagents python=3.11
conda activate tradingagents
pip install .
```

### Required API keys

```bash
export ANTHROPIC_API_KEY=...       # Anthropic (Claude)
export GOOGLE_API_KEY=...          # Google (Gemini)
export OPENAI_API_KEY=...          # OpenAI (GPT)
export DEEPSEEK_API_KEY=...        # DeepSeek
export DASHSCOPE_API_KEY=...       # Qwen — International (dashscope-intl.aliyuncs.com)
export DASHSCOPE_CN_API_KEY=...    # Qwen — China (dashscope.aliyuncs.com)
export ZHIPU_API_KEY=...           # GLM via Z.AI (international)
export ZHIPU_CN_API_KEY=...        # GLM via BigModel (China, open.bigmodel.cn)
export MINIMAX_API_KEY=...         # MiniMax — Global (api.minimax.io, M2.x, 204K ctx)
export MINIMAX_CN_API_KEY=...      # MiniMax — China (api.minimaxi.com, M2.x, 204K ctx)
export OPENROUTER_API_KEY=...      # OpenRouter
export ALPHA_VANTAGE_API_KEY=...   # Alpha Vantage (optional)
```

For enterprise providers (Azure OpenAI), copy `.env.enterprise.example` to `.env.enterprise`.

For local models, configure Ollama with `llm_provider: "ollama"`. The default endpoint is `http://localhost:11434/v1`; set `OLLAMA_BASE_URL` to point at a remote `ollama-serve`. Pull models with `ollama pull <name>`, and pick "Custom model ID" in the CLI for any model not listed by default.

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

---

## TradingAgents Package

### Implementation Details

We built TradingAgents with LangGraph to ensure flexibility and modularity. The framework supports multiple LLM providers: OpenAI, Google, Anthropic, xAI, DeepSeek, Qwen (Alibaba DashScope, international and China endpoints), GLM (Zhipu), MiniMax (global + China), OpenRouter, Ollama for local models, and Azure OpenAI for enterprise.


### Python Usage

```python
import asyncio
from tradingagents.pipeline.runner import run_analysis

# Run a full 8-agent analysis
state = asyncio.run(run_analysis(
    ticker="NVDA",
    trade_date="2026-01-15",
    analyst_provider="google",
    analyst_model="gemini-2.5-flash",       # Phase 1: fast + cheap
    synthesis_provider="anthropic",
    synthesis_model="claude-sonnet-4-6",    # Phase 2+3: quality reasoning
))

print(state.final_decision)
print(state.fundamentals_report)
print(state.bull_case)
```

With portfolio context (personalises analysis to user's actual holdings):

```python
state = asyncio.run(run_analysis(
    ticker="NVDA",
    trade_date="2026-01-15",
    portfolio_context={
        "NVDA": {"shares": 200, "avg_cost_usd": 118.00}
    },
))
```

With per-agent progress callback (powers the Analyst Briefing Room UI):

```python
async def on_agent_complete(agent_name: str, state):
    print(f"{agent_name} complete — {state.agent_summaries.get(agent_name, '')}")

state = await run_analysis(
    ticker="NVDA",
    trade_date="2026-01-15",
    on_agent_complete=on_agent_complete,
)
```

Select specific analysts (default: all four):

```python
state = asyncio.run(run_analysis(
    ticker="NVDA",
    trade_date="2026-01-15",
    selected_analysts=["fundamentals", "news"],  # skip market + social
))
```

### Pipeline phases

```
Phase 1 (parallel ~30s):   Fundamental · Market · News · Sentiment analysts
Phase 2 (parallel ~30s):   Bull Researcher · Bear Researcher
Phase 3 (sequential ~60s): Research Manager → Trader → Portfolio Manager

Total: ~90-120 seconds
```

### Persistence

**Decision log** — always on. Each run appends the decision to `~/.tradingagents/memory/trading_memory.md`. On the next run for the same ticker, past decisions are injected into the Portfolio Manager prompt as context.

Override path: `TRADINGAGENTS_MEMORY_LOG_PATH`

In SaaS mode, the decision log is stored per-user in Supabase (`memory_log` table) — no shared file, no cross-user contamination.

**Checkpoint resume** — the pipeline saves state to Supabase (SaaS) or a local JSON file (CLI) after each agent completes. If a run is interrupted, the next attempt resumes from the last completed agent instead of starting over.

---

## TradingAgents Framework

TradingAgents is a multi-agent trading framework that mirrors the dynamics of real-world trading firms. Specialized LLM-powered agents collaborate and debate to produce structured investment analysis.

<p align="center">
  <img src="assets/schema.png" style="width: 100%; height: auto;">
</p>

> Designed for research purposes. Not intended as financial, investment, or trading advice. [Disclaimer](https://tauric.ai/disclaimer/)

### Agent pipeline

- **Fundamental Analyst** — evaluates financials, intrinsic value, red flags
- **Sentiment Analyst** — analyzes social media and public sentiment
- **News Analyst** — monitors global news and macroeconomic indicators
- **Technical Analyst** — detects trading patterns via MACD, RSI, Bollinger Bands

<p align="center">
  <img src="assets/analyst.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

- **Bull Researcher + Bear Researcher** — structured debate using all analyst reports

<p align="center">
  <img src="assets/researcher.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

- **Research Manager** — synthesises debate into investment plan
- **Trader** — translates plan into a transaction proposal
- **Portfolio Manager** — final decision with rating (Buy / Overweight / Hold / Underweight / Sell)

<p align="center">
  <img src="assets/risk.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

Built with asyncio + LiteLLM. Supports: OpenAI, Google, Anthropic, DeepSeek, Qwen, GLM, OpenRouter, Ollama, Azure OpenAI.

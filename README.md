# AI Analyst Weekly

Hedge-fund-quality stock research, delivered weekly. Built on the TradingAgents multi-agent LLM framework.

**Stack:** FastAPI · Supabase · Stripe · Resend · Loops.so · LiteLLM

---

⚡ [Local Dev](#local-development) | 💻 [CLI](#installation-and-cli) | 📦 [Python Package](#tradingagents-package) | 🔬 [Framework](#tradingagents-framework)

---

## AI Analyst Weekly — SaaS Product

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

The app ships as a **single Docker container** (`Dockerfile`) serving both the frontend and API. Deployment platform is not yet decided — the container is platform-agnostic and works on Cloud Run, Railway, Fly.io, Render, or any container host.

### What the container needs

**Environment variables** (set in your platform's dashboard or secrets manager):

```bash
# Supabase
SUPABASE_URL=https://<ref>.supabase.co
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
SUPABASE_JWT_SECRET=...
DATABASE_URL=postgresql://postgres.<ref>:<pw>@aws-0-us-east-1.pooler.supabase.com:6543/postgres

# LLM
ANTHROPIC_API_KEY=...
GOOGLE_API_KEY=...

# Stripe
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_STARTER=price_...
STRIPE_PRICE_PRO=price_...
STRIPE_PRICE_UNLIMITED=price_...

# Email + alerts
RESEND_API_KEY=re_...
RESEND_FROM_EMAIL=weekly@yourdomain.com
FINNHUB_API_KEY=...
LOOPS_API_KEY=...

# Security
INTERNAL_API_SECRET=<long-random-string>

# Model config (defaults shown)
ANALYST_PROVIDER=google
ANALYST_MODEL=gemini-2.5-flash
SYNTHESIS_PROVIDER=anthropic
SYNTHESIS_MODEL=claude-sonnet-4-6

ENVIRONMENT=production
```

### Cron jobs

Three scheduled HTTP POST calls to `/internal/*` endpoints. Any cron service works — Cloud Scheduler, GitHub Actions, cron-job.org, or your platform's native scheduler:

| Job | Schedule | Endpoint |
|---|---|---|
| Weekly digest | Sunday 8pm ET (`0 0 * * MON` UTC) | `POST /internal/batch/run` |
| Alert monitor | Every 5 minutes | `POST /internal/alerts/check` |
| Verdict settlement | Daily 10am UTC | `POST /internal/verdicts/settle` |

All protected by `x-internal-secret` header matching `INTERNAL_API_SECRET`.

### Supabase setup

```bash
# Apply schema to your Supabase project
supabase db push saas/db/schema.sql \
  --db-url "postgresql://postgres:<password>@db.<ref>.supabase.co:5432/postgres"
```

### Stripe setup

```bash
# Create 3 products with 7-day free trials
stripe prices create --product-data[name]="Starter" \
  --unit-amount 1900 --currency usd --recurring[interval]=month

stripe prices create --product-data[name]="Pro" \
  --unit-amount 3900 --currency usd --recurring[interval]=month

stripe prices create --product-data[name]="Unlimited" \
  --unit-amount 7900 --currency usd --recurring[interval]=month
```

Enable 7-day free trials on each price in the Stripe dashboard. Add a webhook endpoint pointing at `https://your-app-url/webhooks/stripe` for: `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_succeeded`, `invoice.payment_failed`.

### Email domain warming

**Start this before launch** — new domains need 4-6 weeks before bulk sends land reliably in primary inbox. Configure SPF, DKIM, and DMARC DNS records in Resend, then send 5-10 test emails per day for 4 weeks.

### Verify deployment

```bash
curl https://your-app-url/health
# → {"status": "ok"}
```

---

## Installation and CLI

### Installation

**With uv (recommended):**

```bash
git clone https://github.com/virajago/TradingAgents.git
cd TradingAgents

uv venv --python 3.11
source .venv/bin/activate   # Windows: .venv\Scripts\activate
uv pip install .
```

**With conda:**

```bash
git clone https://github.com/virajago/TradingAgents.git
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
export DASHSCOPE_API_KEY=...       # Qwen (Alibaba)
export ZHIPU_API_KEY=...           # GLM (Zhipu)
export ALPHA_VANTAGE_API_KEY=...   # Alpha Vantage (optional)
```

For enterprise providers (Azure OpenAI), copy `.env.enterprise.example` to `.env.enterprise`.

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

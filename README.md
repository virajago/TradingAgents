<p align="center">
  <img src="assets/TauricResearch.png" style="width: 60%; height: auto;">
</p>

<div align="center" style="line-height: 1;">
  <a href="https://arxiv.org/abs/2412.20138" target="_blank"><img alt="arXiv" src="https://img.shields.io/badge/arXiv-2412.20138-B31B1B?logo=arxiv"/></a>
  <a href="https://discord.com/invite/hk9PGKShPK" target="_blank"><img alt="Discord" src="https://img.shields.io/badge/Discord-TradingResearch-7289da?logo=discord&logoColor=white&color=7289da"/></a>
  <a href="./assets/wechat.png" target="_blank"><img alt="WeChat" src="https://img.shields.io/badge/WeChat-TauricResearch-brightgreen?logo=wechat&logoColor=white"/></a>
  <a href="https://x.com/TauricResearch" target="_blank"><img alt="X Follow" src="https://img.shields.io/badge/X-TauricResearch-white?logo=x&logoColor=white"/></a>
  <br>
  <a href="https://github.com/TauricResearch/" target="_blank"><img alt="Community" src="https://img.shields.io/badge/Join_GitHub_Community-TauricResearch-14C290?logo=discourse"/></a>
</div>

<div align="center">
  <!-- Keep these links. Translations will automatically update with the README. -->
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=de">Deutsch</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=es">Español</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=fr">français</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=ja">日本語</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=ko">한국어</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=pt">Português</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=ru">Русский</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=zh">中文</a>
</div>

---

# TradingAgents: Multi-Agents LLM Financial Trading Framework

## News
- [2026-04] **TradingAgents v0.2.4** released with structured-output agents (Research Manager, Trader, Portfolio Manager), LangGraph checkpoint resume, persistent decision log, DeepSeek/Qwen/GLM/Azure provider support, Docker, and a Windows UTF-8 encoding fix. See [CHANGELOG.md](CHANGELOG.md) for the full list.
- [2026-03] **TradingAgents v0.2.3** released with multi-language support, GPT-5.4 family models, unified model catalog, backtesting date fidelity, and proxy support.
- [2026-03] **TradingAgents v0.2.2** released with GPT-5.4/Gemini 3.1/Claude 4.6 model coverage, five-tier rating scale, OpenAI Responses API, Anthropic effort control, and cross-platform stability.
- [2026-02] **TradingAgents v0.2.0** released with multi-provider LLM support (GPT-5.x, Gemini 3.x, Claude 4.x, Grok 4.x) and improved system architecture.
- [2026-01] **Trading-R1** [Technical Report](https://arxiv.org/abs/2509.11420) released, with [Terminal](https://github.com/TauricResearch/Trading-R1) expected to land soon.

<div align="center">
<a href="https://www.star-history.com/#TauricResearch/TradingAgents&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=TauricResearch/TradingAgents&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=TauricResearch/TradingAgents&type=Date" />
   <img alt="TradingAgents Star History" src="https://api.star-history.com/svg?repos=TauricResearch/TradingAgents&type=Date" style="width: 80%; height: auto;" />
 </picture>
</a>
</div>

> 🎉 **TradingAgents** officially released! We have received numerous inquiries about the work, and we would like to express our thanks for the enthusiasm in our community.
>
> So we decided to fully open-source the framework. Looking forward to building impactful projects with you!

<div align="center">

🚀 [TradingAgents](#tradingagents-framework) | 🌐 [SaaS Product](#ai-analyst-weekly--saas-product) | ⚡ [CLI](#installation-and-cli) | 🎬 [Demo](https://www.youtube.com/watch?v=90gr5lwjIho) | 📦 [Package Usage](#tradingagents-package) | 🤝 [Contributing](#contributing) | 📄 [Citation](#citation)

</div>

## TradingAgents Framework

TradingAgents is a multi-agent trading framework that mirrors the dynamics of real-world trading firms. By deploying specialized LLM-powered agents: from fundamental analysts, sentiment experts, and technical analysts, to trader, risk management team, the platform collaboratively evaluates market conditions and informs trading decisions. Moreover, these agents engage in dynamic discussions to pinpoint the optimal strategy.

<p align="center">
  <img src="assets/schema.png" style="width: 100%; height: auto;">
</p>

> TradingAgents framework is designed for research purposes. Trading performance may vary based on many factors, including the chosen backbone language models, model temperature, trading periods, the quality of data, and other non-deterministic factors. [It is not intended as financial, investment, or trading advice.](https://tauric.ai/disclaimer/)

Our framework decomposes complex trading tasks into specialized roles. This ensures the system achieves a robust, scalable approach to market analysis and decision-making.

### Analyst Team
- Fundamentals Analyst: Evaluates company financials and performance metrics, identifying intrinsic values and potential red flags.
- Sentiment Analyst: Analyzes social media and public sentiment using sentiment scoring algorithms to gauge short-term market mood.
- News Analyst: Monitors global news and macroeconomic indicators, interpreting the impact of events on market conditions.
- Technical Analyst: Utilizes technical indicators (like MACD and RSI) to detect trading patterns and forecast price movements.

<p align="center">
  <img src="assets/analyst.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

### Researcher Team
- Comprises both bullish and bearish researchers who critically assess the insights provided by the Analyst Team. Through structured debates, they balance potential gains against inherent risks.

<p align="center">
  <img src="assets/researcher.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

### Trader Agent
- Composes reports from the analysts and researchers to make informed trading decisions. It determines the timing and magnitude of trades based on comprehensive market insights.

<p align="center">
  <img src="assets/trader.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

### Risk Management and Portfolio Manager
- Continuously evaluates portfolio risk by assessing market volatility, liquidity, and other risk factors. The risk management team evaluates and adjusts trading strategies, providing assessment reports to the Portfolio Manager for final decision.
- The Portfolio Manager approves/rejects the transaction proposal. If approved, the order will be sent to the simulated exchange and executed.

<p align="center">
  <img src="assets/risk.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

## AI Analyst Weekly — SaaS Product

This repository also contains **AI Analyst Weekly**, a production SaaS built on the TradingAgents engine. It delivers hedge-fund-quality stock research to retail investors via weekly email digests, on-demand analysis, and real-time red flag alerts.

**Stack:** FastAPI · Supabase (Postgres + Auth) · Cloud Run · Cloudflare Pages · Stripe · Resend · Loops.so

Jump to: [Local dev (web app)](#local-development-web-app) | [Deploy to production](#production-deployment) | [CLI usage](#installation-and-cli)

---

## Local Development (Web App)

### Prerequisites

- Python 3.11+
- [Supabase CLI](https://supabase.com/docs/guides/cli) (`brew install supabase/tap/supabase`)
- API keys: at minimum one LLM provider (Anthropic or Google recommended)

### 1. Clone and install

```bash
git clone https://github.com/virajago/TradingAgents.git
cd TradingAgents

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install .                      # core TradingAgents engine
pip install -r saas/requirements.txt  # SaaS dependencies
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` — minimum required for local dev:

```bash
# Supabase local (filled in automatically after step 3)
SUPABASE_URL=http://localhost:54321
SUPABASE_ANON_KEY=<from supabase start output>
SUPABASE_SERVICE_ROLE_KEY=<from supabase start output>
SUPABASE_JWT_SECRET=<from supabase start output>
DATABASE_URL=postgresql://postgres:postgres@localhost:54322/postgres

# One LLM provider (choose one)
ANTHROPIC_API_KEY=sk-ant-...       # Claude — best for on-demand analysis
GOOGLE_API_KEY=AIza...             # Gemini — best for weekly batch (cheaper)

# Stripe test mode
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_STARTER=price_...
STRIPE_PRICE_PRO=price_...
STRIPE_PRICE_UNLIMITED=price_...

# Resend (use test mode locally)
RESEND_API_KEY=re_...

# Internal cron protection
INTERNAL_API_SECRET=any-random-string-for-local-dev

ENVIRONMENT=development
```

### 3. Start Supabase locally

```bash
supabase start                     # starts Postgres + Auth on localhost:54321
supabase db push saas/db/schema.sql  # apply schema + RLS policies
```

The `supabase start` output prints your local `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, and `SUPABASE_JWT_SECRET`. Copy them into `.env`.

### 4. Start the API server

```bash
uvicorn saas.api.main:app --reload --port 8000
```

API is now live at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### 5. Open the web app

The frontend is static HTML. Open any page directly in your browser:

```bash
open ~/.gstack/projects/virajago-TradingAgents/designs/landing-page-20260509/finalized.html
open ~/.gstack/projects/virajago-TradingAgents/designs/dashboard-20260509/finalized.html
open ~/.gstack/projects/virajago-TradingAgents/designs/analysis-page-20260509/finalized.html
```

Or serve all pages locally:

```bash
cd ~/.gstack/projects/virajago-TradingAgents/designs
python -m http.server 3000
# then open http://localhost:3000
```

### 6. Test an analysis run

```bash
# Trigger an on-demand analysis via the API
curl -X POST http://localhost:8000/analyze \
  -H "Authorization: Bearer <your-supabase-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"ticker": "NVDA"}'

# Poll for status
curl http://localhost:8000/analyze/<task_id>/status \
  -H "Authorization: Bearer <your-supabase-jwt>"
```

Or run a batch analysis directly:

```bash
curl -X POST http://localhost:8000/internal/batch/run \
  -H "x-internal-secret: any-random-string-for-local-dev"
```

### 7. Test Stripe webhooks locally

```bash
# Install Stripe CLI
brew install stripe/stripe-cli/stripe

stripe listen --forward-to localhost:8000/webhooks/stripe
# Stripe CLI prints a webhook secret — add it to .env as STRIPE_WEBHOOK_SECRET
```

---

## Production Deployment

### Architecture

```
Cloudflare Pages   → Static HTML frontend (9 pages)
Cloudflare CDN     → SSL, DDoS, asset caching
Cloudflare AI GW   → LLM API proxy (caching + analytics)

Cloud Run          → FastAPI backend + workers
Cloud Scheduler    → Sunday 8pm ET batch + daily verdict settlement
                   → Every 5 min alert monitor

Supabase           → Postgres + Auth + RLS + connection pooling
Stripe             → Billing (credit pack subscriptions)
Resend             → Email delivery (digest + alerts)
Finnhub            → Real-time market event monitoring
Loops.so           → Lifecycle email sequences
```

### 1. Create a Supabase project

1. Go to [supabase.com](https://supabase.com) and create a new project in **us-east-1** (AWS region, closest to Cloud Run `us-east1`)
2. In the SQL Editor, run the full schema:

```bash
# Copy and paste the contents of saas/db/schema.sql into Supabase SQL Editor
# Or use the Supabase CLI against your remote project:
supabase db push saas/db/schema.sql --db-url "postgresql://postgres:<password>@db.<project-ref>.supabase.co:5432/postgres"
```

3. Copy your project's **URL**, **anon key**, **service role key**, **JWT secret**, and **database URL (pooler/Supavisor)** from Project Settings → API.

### 2. Create Stripe products

In the Stripe dashboard (or CLI), create three products:

```bash
stripe products create --name "Starter" --description "100 credits/month"
stripe prices create --product <starter-id> --unit-amount 1900 --currency usd --recurring-interval month

stripe products create --name "Pro" --description "300 credits/month"
stripe prices create --product <pro-id> --unit-amount 3900 --currency usd --recurring-interval month

stripe products create --name "Unlimited" --description "Unlimited credits/month"
stripe prices create --product <unlimited-id> --unit-amount 7900 --currency usd --recurring-interval month
```

Copy the three `price_...` IDs. Enable 7-day free trials in the Stripe dashboard per price.

### 3. Configure Cloud Run environment

Set all secrets in GCP Secret Manager (recommended) or as Cloud Run environment variables:

```bash
gcloud run services update ai-analyst-weekly \
  --region us-east1 \
  --set-env-vars "ENVIRONMENT=production" \
  --set-env-vars "SUPABASE_URL=https://<ref>.supabase.co" \
  --set-env-vars "SUPABASE_ANON_KEY=..." \
  --set-env-vars "SUPABASE_SERVICE_ROLE_KEY=..." \
  --set-env-vars "SUPABASE_JWT_SECRET=..." \
  --set-env-vars "DATABASE_URL=postgresql://postgres.<ref>:<password>@aws-0-us-east-1.pooler.supabase.com:6543/postgres" \
  --set-env-vars "ANTHROPIC_API_KEY=..." \
  --set-env-vars "GOOGLE_API_KEY=..." \
  --set-env-vars "STRIPE_SECRET_KEY=sk_live_..." \
  --set-env-vars "STRIPE_WEBHOOK_SECRET=whsec_..." \
  --set-env-vars "STRIPE_PRICE_STARTER=price_..." \
  --set-env-vars "STRIPE_PRICE_PRO=price_..." \
  --set-env-vars "STRIPE_PRICE_UNLIMITED=price_..." \
  --set-env-vars "RESEND_API_KEY=re_..." \
  --set-env-vars "RESEND_FROM_EMAIL=weekly@yourdomain.com" \
  --set-env-vars "FINNHUB_API_KEY=..." \
  --set-env-vars "LOOPS_API_KEY=..." \
  --set-env-vars "INTERNAL_API_SECRET=<long-random-string>" \
  --set-env-vars "MAX_CONCURRENT_ANALYSES=20"
```

### 4. Deploy to Cloud Run

**Option A — Cloud Build (CI/CD, recommended):**

```bash
# One-time: connect your repo in GCP Cloud Build → Triggers
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

After deploy, copy the Cloud Run service URL (`https://ai-analyst-weekly-xxxx-ue.a.run.app`).

### 5. Set up Cloud Scheduler jobs

```bash
# Sunday 8pm ET weekly digest
gcloud scheduler jobs create http weekly-digest \
  --location us-east1 \
  --schedule "0 0 * * MON" \
  --uri "https://<cloud-run-url>/internal/batch/run" \
  --http-method POST \
  --headers "x-internal-secret=<INTERNAL_API_SECRET>"

# Every 5 minutes — alert monitor
gcloud scheduler jobs create http alert-monitor \
  --location us-east1 \
  --schedule "*/5 * * * *" \
  --uri "https://<cloud-run-url>/internal/alerts/check" \
  --http-method POST \
  --headers "x-internal-secret=<INTERNAL_API_SECRET>"

# Daily verdict settlement
gcloud scheduler jobs create http verdict-settler \
  --location us-east1 \
  --schedule "0 10 * * *" \
  --uri "https://<cloud-run-url>/internal/verdicts/settle" \
  --http-method POST \
  --headers "x-internal-secret=<INTERNAL_API_SECRET>"
```

### 6. Deploy the frontend to Cloudflare Pages

```bash
# Install Wrangler
npm install -g wrangler
wrangler login

# Deploy the HTML pages
wrangler pages deploy ~/.gstack/projects/virajago-TradingAgents/designs \
  --project-name ai-analyst-weekly
```

Or connect your GitHub repo in the Cloudflare Pages dashboard and set the build output directory to the designs folder.

### 7. Configure Stripe webhook

In Stripe Dashboard → Webhooks, add endpoint:
```
https://<cloud-run-url>/webhooks/stripe
```

Select events:
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.payment_succeeded`
- `invoice.payment_failed`

Copy the webhook signing secret into `STRIPE_WEBHOOK_SECRET`.

### 8. Configure Cloudflare AI Gateway (optional, recommended)

1. In Cloudflare Dashboard → AI Gateway, create a gateway named `ai-analyst-weekly`
2. Copy the gateway URL: `https://gateway.ai.cloudflare.com/v1/<account-id>/ai-analyst-weekly`
3. Set `CF_AI_GATEWAY_URL` in Cloud Run environment variables
4. Update `saas/config.py` to route LLM calls through the gateway URL

### Email domain warming

**Start this immediately** — bulk sending from a new domain requires 4-6 weeks of warming before reliable inbox delivery.

```bash
# Add your domain to Resend and configure DNS records:
# SPF:   TXT @ "v=spf1 include:amazonses.com ~all"
# DKIM:  provided by Resend during domain setup
# DMARC: TXT _dmarc "v=DMARC1; p=none; rua=mailto:dmarc@yourdomain.com"

# Send 5-10 test emails/day for 4 weeks before the first batch send
```

### Verify production deployment

```bash
# Health check
curl https://<cloud-run-url>/health

# Trigger a test batch (sends emails to all active subscribers)
curl -X POST https://<cloud-run-url>/internal/batch/run \
  -H "x-internal-secret: <INTERNAL_API_SECRET>"
```

---

## Installation and CLI

### Installation

Clone TradingAgents:
```bash
git clone https://github.com/TauricResearch/TradingAgents.git
cd TradingAgents
```

Create a virtual environment in any of your favorite environment managers:
```bash
conda create -n tradingagents python=3.13
conda activate tradingagents
```

Install the package and its dependencies:
```bash
pip install .
```

### Docker

Alternatively, run with Docker:
```bash
cp .env.example .env  # add your API keys
docker compose run --rm tradingagents
```

For local models with Ollama:
```bash
docker compose --profile ollama run --rm tradingagents-ollama
```

### Required APIs

TradingAgents supports multiple LLM providers. Set the API key for your chosen provider:

```bash
export OPENAI_API_KEY=...          # OpenAI (GPT)
export GOOGLE_API_KEY=...          # Google (Gemini)
export ANTHROPIC_API_KEY=...       # Anthropic (Claude)
export XAI_API_KEY=...             # xAI (Grok)
export DEEPSEEK_API_KEY=...        # DeepSeek
export DASHSCOPE_API_KEY=...       # Qwen (Alibaba DashScope)
export ZHIPU_API_KEY=...           # GLM (Zhipu)
export OPENROUTER_API_KEY=...      # OpenRouter
export ALPHA_VANTAGE_API_KEY=...   # Alpha Vantage
```

For enterprise providers (e.g. Azure OpenAI, AWS Bedrock), copy `.env.enterprise.example` to `.env.enterprise` and fill in your credentials.

For local models, configure Ollama with `llm_provider: "ollama"` in your config.

Alternatively, copy `.env.example` to `.env` and fill in your keys:
```bash
cp .env.example .env
```

### CLI Usage

Launch the interactive CLI:
```bash
tradingagents          # installed command
python -m cli.main     # alternative: run directly from source
```
You will see a screen where you can select your desired tickers, analysis date, LLM provider, research depth, and more.

<p align="center">
  <img src="assets/cli/cli_init.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

An interface will appear showing results as they load, letting you track the agent's progress as it runs.

<p align="center">
  <img src="assets/cli/cli_news.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

<p align="center">
  <img src="assets/cli/cli_transaction.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

## TradingAgents Package

### Implementation Details

We built TradingAgents with LangGraph to ensure flexibility and modularity. The framework supports multiple LLM providers: OpenAI, Google, Anthropic, xAI, DeepSeek, Qwen (Alibaba DashScope), GLM (Zhipu), OpenRouter, Ollama for local models, and Azure OpenAI for enterprise.

### Python Usage

To use TradingAgents inside your code, you can import the `tradingagents` module and initialize a `TradingAgentsGraph()` object. The `.propagate()` function will return a decision. You can run `main.py`, here's also a quick example:

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

# CLI / research usage
ta = TradingAgentsGraph(debug=True, config=DEFAULT_CONFIG.copy())
_, decision = ta.propagate("NVDA", "2026-01-15")
print(decision)

# SaaS / multi-user usage (pass user_id for isolated checkpoints and memory)
ta = TradingAgentsGraph(
    config=DEFAULT_CONFIG.copy(),
    user_id="user_abc123",          # scopes checkpoints and memory log per user
    supabase_client=supabase,       # enables per-user Postgres memory log
)
_, decision = ta.propagate("NVDA", "2026-01-15")
```

You can also adjust the default configuration to set your own choice of LLMs, debate rounds, etc.

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"        # openai, google, anthropic, xai, deepseek, qwen, glm, openrouter, ollama, azure
config["deep_think_llm"] = "gpt-5.4"     # Model for complex reasoning
config["quick_think_llm"] = "gpt-5.4-mini" # Model for quick tasks
config["max_debate_rounds"] = 2

ta = TradingAgentsGraph(debug=True, config=config)
_, decision = ta.propagate("NVDA", "2026-01-15")
print(decision)
```

See `tradingagents/default_config.py` for all configuration options.

## Persistence and Recovery

TradingAgents persists two kinds of state across runs.

### Decision log

The decision log is always on. Each completed run appends its decision to `~/.tradingagents/memory/trading_memory.md`. On the next run for the same ticker, TradingAgents fetches the realised return (raw and alpha vs SPY), generates a one-paragraph reflection, and injects the most recent same-ticker decisions plus recent cross-ticker lessons into the Portfolio Manager prompt, so each analysis carries forward what worked and what didn't.

Override the path with `TRADINGAGENTS_MEMORY_LOG_PATH`.

### Checkpoint resume

Checkpoint resume is opt-in via `--checkpoint`. When enabled, LangGraph saves state after each node so a crashed or interrupted run resumes from the last successful step instead of starting over. On a resume run you will see `Resuming from step N for <TICKER> on <date>` in the logs; on a new run you will see `Starting fresh`. Checkpoints are cleared automatically on successful completion.

Per-ticker SQLite databases live at `~/.tradingagents/cache/checkpoints/<TICKER>.db` (override the base with `TRADINGAGENTS_CACHE_DIR`). Use `--clear-checkpoints` to reset all of them before a run.

```bash
tradingagents analyze --checkpoint           # enable for this run
tradingagents analyze --clear-checkpoints    # reset before running
```

```python
config = DEFAULT_CONFIG.copy()
config["checkpoint_enabled"] = True
ta = TradingAgentsGraph(config=config)
_, decision = ta.propagate("NVDA", "2026-01-15")
```

## Contributing

We welcome contributions from the community! Whether it's fixing a bug, improving documentation, or suggesting a new feature, your input helps make this project better. If you are interested in this line of research, please consider joining our open-source financial AI research community [Tauric Research](https://tauric.ai/).

Past contributions, including code, design feedback, and bug reports, are credited per release in [`CHANGELOG.md`](CHANGELOG.md).

## Citation

Please reference our work if you find *TradingAgents* provides you with some help :)

```
@misc{xiao2025tradingagentsmultiagentsllmfinancial,
      title={TradingAgents: Multi-Agents LLM Financial Trading Framework}, 
      author={Yijia Xiao and Edward Sun and Di Luo and Wei Wang},
      year={2025},
      eprint={2412.20138},
      archivePrefix={arXiv},
      primaryClass={q-fin.TR},
      url={https://arxiv.org/abs/2412.20138}, 
}
```

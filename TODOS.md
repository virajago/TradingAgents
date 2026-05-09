# TODOS — AI Analyst SaaS on TradingAgents

Generated from /plan-eng-review on 2026-05-04. P0 items block Phase 1A launch.

## P0 — Must complete before Phase 1A table creation

### [P0] Supabase RLS policy design doc
**What:** Design and document all Row-Level Security policies before creating user/portfolio/verdicts/journal tables.
**Why:** A mistake in RLS means User A can read User B's portfolio — data breach, not a bug.
**Context:** Supabase uses PostgreSQL RLS. The service-role key (used by background batch workers) bypasses RLS; this bypass must be explicit, documented, and audited. Design policies for: users, watchlists, portfolios, verdicts, journal_entries tables. Each policy must specify: who can SELECT, INSERT, UPDATE, DELETE, and what the filter condition is.
**Effort:** S (human ~half day / CC ~20 min)
**Depends on:** Supabase project created

---

## P1 — Must complete before Phase 1A goes live

### [P1] Verdict settlement schema design spike
**What:** Define the verdict logging schema and settlement logic before first analysis is logged.
**Why:** If 6 months of verdicts are logged with the wrong schema, the data can't answer "was this bullish call correct vs. the market?"
**Context:** Decisions to make: (1) Baseline — absolute (stock price %) or relative to S&P 500? (2) Time horizons — 30 days, 90 days, both? (3) Correctness threshold — +2% counts as confirming a Buy? Or +5%? (4) Schema fields: verdict (enum), ticker, analysis_date, target_price_at_analysis, price_30d, price_90d, spx_30d, spx_90d, confirmed_30d (bool), confirmed_90d (bool). Recommend: store both absolute and SPX-relative, let the display layer compute correctness.
**Effort:** S (human ~2 hours / CC ~15 min)
**Depends on:** Supabase project created

### [P1] Sunday batch pipeline LLM failure handling spec
**What:** Define retry logic and stub format for ticker analyses that fail in the Sunday batch.
**Why:** At 1,000 runs/Sunday, LLM API failures (timeouts, rate limits, content filters) will happen weekly. Without explicit handling, users get silent incomplete emails.
**Context:** Recommended approach: retry once after 60s backoff; if still failing, include a stub section in the email: "NVDA — Analysis unavailable this week due to a data service issue. We'll include it next Sunday." Per-ticker timeout: 8 minutes (allows 5-min analysis + buffer). Failed ticker count logged per batch run. If >20% of tickers fail for a user, send a separate notification email.
**Effort:** S (human ~half day / CC ~30 min)
**Depends on:** Phase 1A batch pipeline design

### [P1] DeepSeek cost measurement spike
**What:** Run full TradingAgents multi-agent pipeline on 10 diverse tickers using DeepSeek; measure cost per run and output quality.
**Why:** The plan targets <$1/user/week on DeepSeek. This has not been measured. If cost is $3+, pricing must be $59+ to maintain viable margins.
**Context:** Run DeepSeek-V3 via the existing provider support. Measure: input tokens, output tokens, cost per run, total cost for 10 tickers. Then have 3 target users rate output quality blind vs GPT-4o. If quality gap is significant, use GPT-4o for weekly runs (price at $59+) or DeepSeek only for alert analysis (shorter, less complex).
**Effort:** S (human ~2 hours)
**Depends on:** Phase 0.5 hardening complete (clean per-request config)

---

## P2 — Important but not blocking launch

### [P2] yfinance reliability fallback
**What:** Add Alpha Vantage or Finnhub as a fallback data source when yfinance fails.
**Why:** yfinance has no SLA and breaks without warning when Yahoo changes their response format. A Sunday yfinance outage means the entire batch fails.
**Context:** yfinance is already embedded in `tradingagents/dataflows/y_finance.py`. The existing `data_vendors` config already supports switching to `alpha_vantage`. For Phase 1B when Finnhub is added for alerts, use Finnhub as the primary stock data API and demote yfinance to fallback. Implement circuit breaker: if yfinance fails 3 consecutive tickers, switch to fallback for the rest of the batch.
**Effort:** M (human ~1 week / CC ~1 hour)
**Depends on:** Finnhub paid tier setup (Phase 1B)

### [P2] Finnhub event monitoring design spike
**What:** Define the architecture for real-time market event detection before Phase 1B implementation.
**Why:** "Finnhub webhooks" is listed as the alert mechanism but Finnhub's webhook product has reliability limitations. The spike will determine whether to use webhooks, polling, or a streaming API.
**Context:** Decide: (1) Webhook vs. polling interval (60s? 5min?) (2) Deduplication — if NVDA drops 5% then 6%, only one alert fires. (3) Event taxonomy — exactly which Finnhub event types trigger alerts for each category (earnings: `earnings`, price move: compute from quote polling, news: `news`). (4) Alert rate limiting per user per ticker per day. Write a 1-page design doc before starting Phase 1B alert implementation.
**Effort:** S (human ~half day)
**Depends on:** Finnhub paid tier account created

### [P2] Stripe webhook idempotency
**What:** Add idempotency handling to Stripe webhook processing so duplicate deliveries don't cause double-processing.
**Why:** Stripe retries webhooks for up to 72 hours on delivery failure. Without idempotency, a subscription.deleted event delivered twice would cancel a user's account twice (or cause other double-processing bugs).
**Context:** Standard pattern: store processed webhook event IDs in a `stripe_events` table with a unique constraint on `event_id`. Before processing any webhook, check if `event_id` already exists; if so, return 200 without processing. Stripe sends the same `event_id` on retries.
**Effort:** S (human ~2 hours / CC ~15 min)
**Depends on:** Phase 1A Stripe integration

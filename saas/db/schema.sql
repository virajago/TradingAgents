-- AI Analyst Weekly — Supabase Postgres schema
-- Apply this in the Supabase SQL editor or via psql.
-- All tables live in the public schema; auth.users is managed by Supabase.

-- ============================================================
-- Extensions
-- ============================================================

create extension if not exists "uuid-ossp";


-- ============================================================
-- Tables
-- ============================================================

-- Profiles: extends Supabase auth.users (1-to-1)
create table public.profiles (
    id                      uuid references auth.users(id) on delete cascade primary key,
    email                   text not null,
    stripe_customer_id      text,
    stripe_subscription_id  text,
    subscription_status     text not null default 'inactive'
        check (subscription_status in ('active', 'inactive', 'past_due', 'canceled')),
    plan_name               text not null default 'starter'
        check (plan_name in ('starter', 'pro', 'unlimited')),
    created_at              timestamptz not null default now(),
    updated_at              timestamptz not null default now()
);

-- Watchlist: tickers queued for weekly Sunday analysis
create table public.watchlist_items (
    id          uuid not null default uuid_generate_v4() primary key,
    user_id     uuid not null references public.profiles(id) on delete cascade,
    ticker      text not null check (ticker ~ '^[A-Z0-9]{1,8}$'),
    added_at    timestamptz not null default now(),
    unique (user_id, ticker)
);

-- Portfolio holdings: user's actual positions for portfolio-aware analysis
create table public.portfolio_holdings (
    id              uuid not null default uuid_generate_v4() primary key,
    user_id         uuid not null references public.profiles(id) on delete cascade,
    ticker          text not null check (ticker ~ '^[A-Z0-9]{1,8}$'),
    shares          integer not null check (shares > 0),
    avg_cost_usd    numeric(10, 2) not null check (avg_cost_usd > 0),
    added_at        timestamptz not null default now(),
    updated_at      timestamptz not null default now(),
    unique (user_id, ticker)
);

-- Analyses: on-demand + weekly batch + alert-triggered runs
create table public.analyses (
    id              uuid not null default uuid_generate_v4() primary key,
    user_id         uuid not null references public.profiles(id) on delete cascade,
    ticker          text not null,
    trade_date      date not null,
    source          text not null check (source in ('on_demand', 'weekly_batch', 'alert')),
    status          text not null default 'queued'
        check (status in ('queued', 'running', 'complete', 'error')),
    verdict         text check (verdict in ('BULLISH', 'NEUTRAL', 'BEARISH')),
    conviction      text check (conviction in ('High', 'Moderate', 'Low')),
    conviction_pct  integer check (conviction_pct between 0 and 100),
    summary_text    text,
    full_result     jsonb,
    error_message   text,
    created_at      timestamptz not null default now(),
    completed_at    timestamptz
);

-- Verdicts: track-record subset with settlement tracking
create table public.verdicts (
    id                      uuid not null default uuid_generate_v4() primary key,
    analysis_id             uuid not null references public.analyses(id) on delete cascade,
    user_id                 uuid not null references public.profiles(id) on delete cascade,
    ticker                  text not null,
    verdict_date            date not null,
    verdict                 text not null check (verdict in ('BULLISH', 'NEUTRAL', 'BEARISH')),
    price_at_verdict        numeric(10, 2),
    -- Settlement fields (populated by verdict_settlement cron)
    price_30d               numeric(10, 2),
    price_90d               numeric(10, 2),
    spx_price_at_verdict    numeric(10, 2),
    spx_price_30d           numeric(10, 2),
    spx_price_90d           numeric(10, 2),
    settled_30d             boolean not null default false,
    settled_90d             boolean not null default false,
    created_at              timestamptz not null default now()
);

-- Daily on-demand rate limiting
create table public.daily_analysis_counts (
    user_id     uuid not null references public.profiles(id) on delete cascade,
    date        date not null default current_date,
    count       integer not null default 0,
    primary key (user_id, date)
);

-- Decision journal
create table public.journal_entries (
    id              uuid not null default uuid_generate_v4() primary key,
    user_id         uuid not null references public.profiles(id) on delete cascade,
    analysis_id     uuid references public.analyses(id) on delete set null,
    ticker          text not null,
    entry_date      date not null default current_date,
    action          text not null check (action in ('buy', 'sell', 'hold', 'wait', 'skip')),
    thesis          text,
    -- Outcome tracking (populated later by settlement cron)
    price_at_entry  numeric(10, 2),
    price_30d       numeric(10, 2),
    price_90d       numeric(10, 2),
    created_at      timestamptz not null default now()
);

-- Stripe webhook idempotency guard
create table public.stripe_events (
    event_id        text primary key,
    processed_at    timestamptz not null default now()
);

-- Credit balance per user (single row per user, never deleted)
create table public.user_credits (
    user_id         uuid references public.profiles(id) on delete cascade primary key,
    balance         integer not null default 0 check (balance >= 0),
    lifetime_earned integer not null default 0,
    updated_at      timestamptz default now()
);

-- Credit transaction log (append-only audit trail)
create table public.credit_transactions (
    id              uuid default uuid_generate_v4() primary key,
    user_id         uuid references public.profiles(id) on delete cascade not null,
    -- positive = earned (trial grant, renewal); negative = spent (analysis, alert)
    amount          integer not null,
    action          text not null,
        -- 'trial_grant' | 'subscription_renewal' | 'on_demand_analysis'
        -- | 'weekly_digest' | 'alert' | 'refund'
    reference_id    text,       -- analysis_id, stripe_invoice_id, etc.
    balance_after   integer not null,
    created_at      timestamptz default now()
);


-- ============================================================
-- Indexes
-- ============================================================

create index idx_watchlist_user           on public.watchlist_items (user_id);
create index idx_portfolio_user           on public.portfolio_holdings (user_id);
create index idx_analyses_user_date       on public.analyses (user_id, created_at desc);
create index idx_analyses_status          on public.analyses (status)
    where status in ('queued', 'running');
create index idx_verdicts_user            on public.verdicts (user_id, verdict_date desc);
create index idx_verdicts_unsettled       on public.verdicts (verdict_date)
    where settled_30d = false or settled_90d = false;
create index idx_journal_user             on public.journal_entries (user_id, entry_date desc);
create index idx_daily_counts_user_date   on public.daily_analysis_counts (user_id, date);
create index idx_credit_transactions_user on public.credit_transactions (user_id, created_at desc);


-- ============================================================
-- Row Level Security
-- ============================================================

alter table public.profiles              enable row level security;
alter table public.watchlist_items       enable row level security;
alter table public.portfolio_holdings    enable row level security;
alter table public.analyses              enable row level security;
alter table public.verdicts              enable row level security;
alter table public.daily_analysis_counts enable row level security;
alter table public.journal_entries       enable row level security;
alter table public.stripe_events         enable row level security;
alter table public.user_credits          enable row level security;
alter table public.credit_transactions   enable row level security;

-- Users can only see their own rows.
-- The service role (used by background workers) bypasses RLS automatically.

create policy "users_own_profile" on public.profiles
    for all using (auth.uid() = id);

create policy "users_own_watchlist" on public.watchlist_items
    for all using (auth.uid() = user_id);

create policy "users_own_portfolio" on public.portfolio_holdings
    for all using (auth.uid() = user_id);

create policy "users_own_analyses" on public.analyses
    for all using (auth.uid() = user_id);

create policy "users_own_verdicts" on public.verdicts
    for all using (auth.uid() = user_id);

create policy "users_own_daily_counts" on public.daily_analysis_counts
    for all using (auth.uid() = user_id);

create policy "users_own_journal" on public.journal_entries
    for all using (auth.uid() = user_id);

-- stripe_events is service-role-only; no user should query it directly.
create policy "no_user_access_stripe_events" on public.stripe_events
    for all using (false);

create policy "users_own_credits" on public.user_credits
    for all using (auth.uid() = user_id);

create policy "users_own_transactions" on public.credit_transactions
    for all using (auth.uid() = user_id);


-- ============================================================
-- Functions & Triggers
-- ============================================================

-- Auto-create profile row when a new Supabase user signs up
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    insert into public.profiles (id, email)
    values (new.id, new.email);
    return new;
end;
$$;

create trigger on_auth_user_created
    after insert on auth.users
    for each row
    execute procedure public.handle_new_user();

-- Atomic rate-limit counter increment (used by the API to avoid race conditions)
create or replace function public.increment_daily_count(
    p_user_id   uuid,
    p_date      date
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
    insert into public.daily_analysis_counts (user_id, date, count)
    values (p_user_id, p_date, 1)
    on conflict (user_id, date)
    do update set count = public.daily_analysis_counts.count + 1;
end;
$$;

-- Keep profiles.updated_at current automatically
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

create trigger profiles_updated_at
    before update on public.profiles
    for each row
    execute procedure public.set_updated_at();

create trigger portfolio_updated_at
    before update on public.portfolio_holdings
    for each row
    execute procedure public.set_updated_at();


-- ============================================================
-- Credit functions
-- ============================================================

-- Atomically deduct credits and log the transaction.
-- Returns the new balance, or -1 if the user has no credit record or
-- insufficient funds. The caller should treat -1 as a 402 condition.
create or replace function public.deduct_credits(
    p_user_id       uuid,
    p_amount        integer,
    p_action        text,
    p_reference_id  text default null
) returns integer as $$
declare
    v_balance       integer;
    v_new_balance   integer;
begin
    -- Lock the row for this user to prevent concurrent over-draws
    select balance into v_balance
    from public.user_credits
    where user_id = p_user_id
    for update;

    if v_balance is null then
        return -1;  -- user has no credit record
    end if;

    if v_balance < p_amount then
        return -1;  -- insufficient credits
    end if;

    v_new_balance := v_balance - p_amount;

    update public.user_credits
    set balance = v_new_balance, updated_at = now()
    where user_id = p_user_id;

    insert into public.credit_transactions
        (user_id, amount, action, reference_id, balance_after)
    values
        (p_user_id, -p_amount, p_action, p_reference_id, v_new_balance);

    return v_new_balance;
end;
$$ language plpgsql security definer;

-- Grant credits (used by the Stripe webhook handler for renewals and trials).
-- Upserts the user_credits row so it is safe to call before the row exists.
create or replace function public.grant_credits(
    p_user_id       uuid,
    p_amount        integer,
    p_action        text,
    p_reference_id  text default null
) returns integer as $$
declare
    v_new_balance   integer;
begin
    insert into public.user_credits (user_id, balance, lifetime_earned)
    values (p_user_id, p_amount, p_amount)
    on conflict (user_id) do update
    set
        balance         = user_credits.balance + p_amount,
        lifetime_earned = user_credits.lifetime_earned + p_amount,
        updated_at      = now()
    returning balance into v_new_balance;

    insert into public.credit_transactions
        (user_id, amount, action, reference_id, balance_after)
    values
        (p_user_id, p_amount, p_action, p_reference_id, v_new_balance);

    return v_new_balance;
end;
$$ language plpgsql security definer;

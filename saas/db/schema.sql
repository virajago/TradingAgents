-- Supabase Postgres schema for TradingAgents SaaS
-- All tables use RLS; service-role key bypasses policies in worker contexts.

create extension if not exists "uuid-ossp";

-- Profiles (mirrors auth.users)
create table public.profiles (
    id uuid references auth.users(id) on delete cascade primary key,
    email text,
    created_at timestamptz default now()
);

alter table public.profiles enable row level security;
create policy "users_own_profile" on public.profiles
    for all using (auth.uid() = id);

-- Portfolio holdings
create table public.portfolio_holdings (
    id uuid default uuid_generate_v4() primary key,
    user_id uuid references public.profiles(id) on delete cascade not null,
    ticker text not null,
    shares integer not null check (shares > 0),
    avg_cost_usd numeric(12, 2) not null check (avg_cost_usd > 0),
    added_at timestamptz default now(),
    unique(user_id, ticker)
);

create index idx_portfolio_holdings_user on public.portfolio_holdings(user_id);

alter table public.portfolio_holdings enable row level security;
create policy "users_own_holdings" on public.portfolio_holdings
    for all using (auth.uid() = user_id);

-- Memory log (per-user, replaces shared file for SaaS use)
create table public.memory_log (
    id uuid default uuid_generate_v4() primary key,
    user_id uuid references public.profiles(id) on delete cascade not null,
    ticker text not null,
    trade_date date not null,
    rating text,
    status text not null default 'pending' check (status in ('pending', 'resolved')),
    decision_text text not null,
    reflection_text text,
    created_at timestamptz default now(),
    resolved_at timestamptz,
    unique(user_id, ticker, trade_date)
);

create index idx_memory_log_user on public.memory_log(user_id, created_at desc);

alter table public.memory_log enable row level security;
create policy "users_own_memory_log" on public.memory_log
    for all using (auth.uid() = user_id);

-- Analysis checkpoints (pipeline crash recovery)
-- Stores mid-pipeline state so Cloud Run can resume a crashed analysis
-- from the last completed phase rather than starting over.
-- Service-role key bypasses RLS — only the analysis worker reads/writes this.
create table public.analysis_checkpoints (
    task_id    text primary key,
    user_id    uuid references public.profiles(id) on delete cascade not null,
    ticker     text not null,
    state      jsonb not null,
    phase      integer not null default 0,  -- number of completed agents
    updated_at timestamptz default now()
);

create index idx_checkpoints_user on public.analysis_checkpoints(user_id);

-- No user RLS — service-role only (analysis worker uses service-role key)
-- Users never read checkpoints directly; results come via the analyses table.

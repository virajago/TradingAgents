# Integration Tests

These tests require a real local Supabase instance.

## Setup
```bash
# Start Supabase locally
supabase start

# Apply the schema
supabase db push saas/db/schema.sql --db-url "postgresql://postgres:postgres@localhost:54322/postgres"

# Copy the printed keys to environment
export SUPABASE_URL=http://localhost:54321
export SUPABASE_ANON_KEY=<printed anon key>
export SUPABASE_SERVICE_ROLE_KEY=<printed service role key>

# Run RLS tests
INTEGRATION_RUN=1 pytest tests/integration/ -v
```

## What these test
- Supabase RLS policies: users can only read/write their own data
- Service role bypasses RLS (needed for batch scheduler)
- Critical: a broken RLS policy means User A can read User B's portfolio

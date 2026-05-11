// Runtime configuration — injected at deploy time or overridden per-environment.
// In production (single container): API_URL is empty — all fetch() calls are relative.
// In local dev: override these by setting window.* before this script loads,
//   or just run the FastAPI server on localhost:8000 and open frontend/ directly.
//
// Production environment variables (set in .env.production or your deploy platform):
//   APP_URL=https://your-app.run.app   (used by the API for Stripe portal return URLs)

window.SUPABASE_URL = window.SUPABASE_URL || '';
window.SUPABASE_ANON_KEY = window.SUPABASE_ANON_KEY || '';
window.API_URL = window.API_URL || '';   // empty = same origin (production)

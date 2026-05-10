#!/usr/bin/env bash
# deploy.sh — provision and deploy AI Analyst Weekly on GCP + Supabase
#
# Run once to set everything up. Safe to re-run — all steps are idempotent.
# Usage: ./deploy.sh
#
# Prerequisites:
#   gcloud CLI installed and authenticated (gcloud auth login)
#   Supabase project already created at supabase.com
#   Stripe products created with trial-enabled prices
#   .env.production file with all required secrets (see README)

set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
APP_NAME="ai-analyst-weekly"
REGION="us-east1"
ENV_FILE="${1:-.env.production}"    # pass a different file as first arg if needed

# ── Colours ───────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $*"; }
info() { echo -e "${YELLOW}→${NC} $*"; }
fail() { echo -e "${RED}✗${NC} $*"; exit 1; }

# ── Preflight ─────────────────────────────────────────────────────────────────
echo ""
echo "AI Analyst Weekly — GCP deployment"
echo "==================================="
echo ""

command -v gcloud >/dev/null || fail "gcloud CLI not found. Install: https://cloud.google.com/sdk/docs/install"
[ -f "$ENV_FILE" ] || fail "Environment file '$ENV_FILE' not found. Copy .env.example and fill in values."

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
[ -n "$PROJECT_ID" ] || fail "No GCP project set. Run: gcloud config set project YOUR_PROJECT_ID"
ok "GCP project: $PROJECT_ID"

# ── Load env vars from file ───────────────────────────────────────────────────
info "Loading environment from $ENV_FILE"
# Export non-comment, non-empty lines
set -a
# shellcheck disable=SC1090
source <(grep -v '^#' "$ENV_FILE" | grep -v '^[[:space:]]*$')
set +a

# Validate required vars
REQUIRED=(
  SUPABASE_URL SUPABASE_ANON_KEY SUPABASE_SERVICE_ROLE_KEY
  SUPABASE_JWT_SECRET DATABASE_URL
  ANTHROPIC_API_KEY GOOGLE_API_KEY
  STRIPE_SECRET_KEY STRIPE_WEBHOOK_SECRET
  STRIPE_PRICE_STARTER STRIPE_PRICE_PRO STRIPE_PRICE_UNLIMITED
  RESEND_API_KEY RESEND_FROM_EMAIL
  INTERNAL_API_SECRET
)
for var in "${REQUIRED[@]}"; do
  [ -n "${!var:-}" ] || fail "Missing required variable: $var"
done
ok "All required environment variables present"

# ── Enable GCP APIs ───────────────────────────────────────────────────────────
info "Enabling required GCP APIs (this can take a minute on first run)..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  cloudscheduler.googleapis.com \
  containerregistry.googleapis.com \
  --quiet
ok "GCP APIs enabled"

# ── Apply Supabase schema ─────────────────────────────────────────────────────
info "Applying Supabase schema..."
if command -v supabase >/dev/null; then
  # Extract host from DATABASE_URL for direct push
  supabase db push saas/db/schema.sql \
    --db-url "$DATABASE_URL" 2>/dev/null \
    && ok "Supabase schema applied" \
    || echo "  (schema push skipped — may already be applied or supabase CLI not configured)"
else
  echo "  supabase CLI not found — apply schema manually:"
  echo "  supabase db push saas/db/schema.sql --db-url \"\$DATABASE_URL\""
fi

# ── Build and push Docker image ───────────────────────────────────────────────
info "Building and pushing Docker image..."
IMAGE="gcr.io/$PROJECT_ID/$APP_NAME:latest"
gcloud builds submit \
  --tag "$IMAGE" \
  --quiet
ok "Image pushed: $IMAGE"

# ── Deploy to Cloud Run ───────────────────────────────────────────────────────
info "Deploying to Cloud Run ($REGION)..."

# Build the --set-env-vars string from loaded env vars
ENV_VARS="ENVIRONMENT=production"
ENV_VARS+=",SUPABASE_URL=$SUPABASE_URL"
ENV_VARS+=",SUPABASE_ANON_KEY=$SUPABASE_ANON_KEY"
ENV_VARS+=",SUPABASE_SERVICE_ROLE_KEY=$SUPABASE_SERVICE_ROLE_KEY"
ENV_VARS+=",SUPABASE_JWT_SECRET=$SUPABASE_JWT_SECRET"
ENV_VARS+=",DATABASE_URL=$DATABASE_URL"
ENV_VARS+=",ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY"
ENV_VARS+=",GOOGLE_API_KEY=$GOOGLE_API_KEY"
ENV_VARS+=",STRIPE_SECRET_KEY=$STRIPE_SECRET_KEY"
ENV_VARS+=",STRIPE_WEBHOOK_SECRET=$STRIPE_WEBHOOK_SECRET"
ENV_VARS+=",STRIPE_PRICE_STARTER=$STRIPE_PRICE_STARTER"
ENV_VARS+=",STRIPE_PRICE_PRO=$STRIPE_PRICE_PRO"
ENV_VARS+=",STRIPE_PRICE_UNLIMITED=$STRIPE_PRICE_UNLIMITED"
ENV_VARS+=",RESEND_API_KEY=$RESEND_API_KEY"
ENV_VARS+=",RESEND_FROM_EMAIL=$RESEND_FROM_EMAIL"
ENV_VARS+=",INTERNAL_API_SECRET=$INTERNAL_API_SECRET"
ENV_VARS+=",ANALYST_PROVIDER=${ANALYST_PROVIDER:-google}"
ENV_VARS+=",ANALYST_MODEL=${ANALYST_MODEL:-gemini-2.5-flash}"
ENV_VARS+=",SYNTHESIS_PROVIDER=${SYNTHESIS_PROVIDER:-anthropic}"
ENV_VARS+=",SYNTHESIS_MODEL=${SYNTHESIS_MODEL:-claude-sonnet-4-6}"
ENV_VARS+=",MAX_CONCURRENT_ANALYSES=${MAX_CONCURRENT_ANALYSES:-20}"

# Optional vars
[ -n "${FINNHUB_API_KEY:-}" ]  && ENV_VARS+=",FINNHUB_API_KEY=$FINNHUB_API_KEY"
[ -n "${LOOPS_API_KEY:-}" ]    && ENV_VARS+=",LOOPS_API_KEY=$LOOPS_API_KEY"
[ -n "${DEEPSEEK_API_KEY:-}" ] && ENV_VARS+=",DEEPSEEK_API_KEY=$DEEPSEEK_API_KEY"

gcloud run deploy "$APP_NAME" \
  --image="$IMAGE" \
  --region="$REGION" \
  --platform=managed \
  --allow-unauthenticated \
  --memory=2Gi \
  --cpu=2 \
  --concurrency=80 \
  --min-instances=0 \
  --max-instances=10 \
  --timeout=600 \
  --set-env-vars="$ENV_VARS" \
  --quiet

SERVICE_URL=$(gcloud run services describe "$APP_NAME" \
  --region="$REGION" \
  --format="value(status.url)")
ok "Deployed: $SERVICE_URL"

# ── Cloud Scheduler cron jobs ─────────────────────────────────────────────────
info "Setting up Cloud Scheduler cron jobs..."

SCHEDULER_SA="cloudscheduler@$PROJECT_ID.iam.gserviceaccount.com"

create_or_update_job() {
  local name=$1 schedule=$2 uri=$3
  if gcloud scheduler jobs describe "$name" --location="$REGION" &>/dev/null; then
    gcloud scheduler jobs update http "$name" \
      --location="$REGION" \
      --schedule="$schedule" \
      --uri="$uri" \
      --http-method=POST \
      --headers="x-internal-secret=$INTERNAL_API_SECRET" \
      --quiet
    ok "Updated cron job: $name"
  else
    gcloud scheduler jobs create http "$name" \
      --location="$REGION" \
      --schedule="$schedule" \
      --uri="$uri" \
      --http-method=POST \
      --headers="x-internal-secret=$INTERNAL_API_SECRET" \
      --time-zone="UTC" \
      --quiet
    ok "Created cron job: $name"
  fi
}

# Sunday 8pm ET = Monday 00:00 UTC
create_or_update_job "weekly-digest"   "0 0 * * MON"  "$SERVICE_URL/internal/batch/run"
# Alert monitor every 5 minutes
create_or_update_job "alert-monitor"   "*/5 * * * *"  "$SERVICE_URL/internal/alerts/check"
# Verdict settlement daily 10am UTC
create_or_update_job "verdict-settler" "0 10 * * *"   "$SERVICE_URL/internal/verdicts/settle"

# ── Stripe webhook ────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
info "Manual step required: configure Stripe webhook"
echo ""
echo "  1. Go to: https://dashboard.stripe.com/webhooks"
echo "  2. Add endpoint: $SERVICE_URL/webhooks/stripe"
echo "  3. Select events:"
echo "       customer.subscription.created"
echo "       customer.subscription.updated"
echo "       customer.subscription.deleted"
echo "       invoice.payment_succeeded"
echo "       invoice.payment_failed"
echo "  4. Copy the signing secret → set STRIPE_WEBHOOK_SECRET in $ENV_FILE"
echo "  5. Re-run this script to update the Cloud Run env vars"
echo ""

# ── Health check ──────────────────────────────────────────────────────────────
info "Verifying deployment..."
sleep 3
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$SERVICE_URL/health")
if [ "$HTTP_STATUS" = "200" ]; then
  ok "Health check passed ($SERVICE_URL/health → 200)"
else
  echo "  Health check returned $HTTP_STATUS — check Cloud Run logs:"
  echo "  gcloud run logs tail $APP_NAME --region=$REGION"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "${GREEN}Deployment complete!${NC}"
echo ""
echo "  App URL:     $SERVICE_URL"
echo "  Landing:     $SERVICE_URL/"
echo "  Sign up:     $SERVICE_URL/signup"
echo "  API docs:    $SERVICE_URL/docs  (development mode only)"
echo "  Health:      $SERVICE_URL/health"
echo ""
echo "  View logs:   gcloud run logs tail $APP_NAME --region=$REGION"
echo "  Redeploy:    ./deploy.sh"
echo ""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from saas.api.routes import analyze, credits, watchlist, portfolio, journal, verdicts, webhooks, internal
from saas.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: nothing needed (Supabase client is per-request)
    yield
    # shutdown: nothing needed


app = FastAPI(
    title="AI Analyst Weekly API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.environment == "development" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://aianalystweekly.com", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze.router, prefix="/analyze", tags=["analysis"])
app.include_router(credits.router, prefix="/credits", tags=["credits"])
app.include_router(watchlist.router, prefix="/watchlist", tags=["watchlist"])
app.include_router(portfolio.router, prefix="/portfolio", tags=["portfolio"])
app.include_router(journal.router, prefix="/journal", tags=["journal"])
app.include_router(verdicts.router, prefix="/verdicts", tags=["verdicts"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
app.include_router(internal.router, prefix="/internal", tags=["internal"])


@app.get("/health")
async def health():
    return {"status": "ok"}

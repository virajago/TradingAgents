from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from saas.api.routes import analyze, auth, credits, watchlist, portfolio, journal, verdicts, webhooks, internal
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
    allow_origins=[
        "https://aianalystweekly.com",
        "http://localhost:3000",
        "http://localhost:8080",
        "null",  # file:// origin when opening HTML directly in browser
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
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


# Static files — must be mounted LAST so API routes take priority.
# Serves frontend/ at the root: / → index.html, /dashboard → dashboard.html, etc.
_frontend_dir = Path(__file__).parent.parent.parent / "frontend"
if _frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")

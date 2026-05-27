"""
backend/main.py

FastAPI application factory.

Security notes:
- CORS is restricted to localhost origins only — this app is not a public API.
- The uvicorn bind address is read from config (defaults to 127.0.0.1).
- All table creation happens at startup so the app is self-bootstrapping.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.db.database import engine
from backend.models.models import Account, Institution, SyncState, Transaction  # noqa: F401 — ensure models are registered
from backend.db.database import Base
from backend.routes import (
    accounts_router,
    analytics_router,
    plaid_router,
    transactions_router,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create all DB tables on startup (idempotent)."""
    logger.info("Creating database tables if they don't exist…")
    Base.metadata.create_all(bind=engine)
    logger.info("Database ready.")
    yield
    logger.info("Shutting down.")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Finance Dashboard API",
        description="Local-first personal finance backend",
        version="0.1.0",
        lifespan=lifespan,
        # Disable docs in a future production hardening pass; keep for dev.
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── CORS ─────────────────────────────────────────────────────────────────
    # Allow only localhost origins so the API cannot be called from external sites.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            f"http://{settings.backend_host}:{settings.backend_port}",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(plaid_router)
    app.include_router(transactions_router)
    app.include_router(accounts_router)
    app.include_router(analytics_router)

    @app.get("/health")
    def health():
        return {"status": "ok", "version": "0.1.0"}

    return app


app = create_app()


# ── Development entry point ───────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "backend.main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=True,
        log_level="info",
    )

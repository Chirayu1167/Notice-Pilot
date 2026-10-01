from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app import database
from app.api import agent, demo, documents, notices, reconciliation, returns, review

import time


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    yield


async def timing_middleware(request: Request, call_next):
    """Demo observability: server-side duration on every response header."""
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
    response.headers["X-Process-Time-Ms"] = str(elapsed_ms)
    return response


app = FastAPI(title="NoticePilot GST API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(timing_middleware)


app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(notices.router, prefix="/api/notices", tags=["notices"])
app.include_router(returns.router, prefix="/api/notices", tags=["returns"])
app.include_router(reconciliation.router, prefix="/api/reconciliation", tags=["reconciliation"])
app.include_router(agent.router, prefix="/api", tags=["agent"])
app.include_router(review.router, prefix="/api", tags=["review"])
app.include_router(demo.router, prefix="/api", tags=["demo"])


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/status")
def status():
    """Safe application status: health, database, agent provider, rules, version."""
    from app import config
    from app.agent.provider import provider_status
    from app.parsers import gst_rules

    db_ok = True
    try:
        database.init_db()
    except Exception:
        db_ok = False
    provider = provider_status()
    return {
        "backend": "ok",
        "database": "ok" if db_ok else "error",
        "storage": config.STORAGE_DIR is not None,
        "agent": {
            "available": provider.get("available", False),
            "provider": provider.get("provider"),
            "model": provider.get("model"),
        },
        "ruleVersion": gst_rules.RULE_VERSION,
        "appVersion": "1.0.0",
    }

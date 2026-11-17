import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.database import Base, SessionLocal, engine
from app.routers import classify, settings as settings_router, trust
from app.seed import seed_categories

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Feed Filter API",
    description=(
        "Embedding + LLM-backed classification service for the Feed Filter "
        "browser extension."
    ),
    version="0.1.0",
)

# Extension calls come from a chrome-extension:// origin (or a background
# service worker). Wide open here for local dev / demo purposes — lock this
# down to your actual extension ID before shipping publicly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(classify.router)
app.include_router(trust.router)
app.include_router(settings_router.router)


@app.on_event("startup")
def on_startup():
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    Base.metadata.create_all(bind=engine)

    # Lightweight migration for the focus_score column added after the
    # initial schema — safe to re-run, no-op if the column already exists.
    with engine.connect() as conn:
        conn.execute(
            text(
                "ALTER TABLE classification_cache "
                "ADD COLUMN IF NOT EXISTS focus_score FLOAT DEFAULT 0.5"
            )
        )
        conn.commit()

    db = SessionLocal()
    try:
        seed_categories(db)
    finally:
        db.close()

    logger.info("Startup complete")


@app.get("/health")
def health():
    return {"status": "ok"}

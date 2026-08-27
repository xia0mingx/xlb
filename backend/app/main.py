"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, meta, products, quiz
from app.config import get_settings
from app.db import Base, engine

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # create_all is a convenience for local SQLite; Alembic owns the schema in
    # any real deployment.
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    scheduler = None
    if settings.enable_scheduler:
        from app.jobs.scheduler import start_scheduler

        scheduler = start_scheduler()
        logger.info("price refresh scheduler started")

    yield

    if scheduler is not None:
        scheduler.shutdown(wait=False)
    await engine.dispose()


app = FastAPI(
    title="xlb",
    description="Skincare price comparison, ingredient analysis and recommendations",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router)
app.include_router(quiz.router)
app.include_router(chat.router)
app.include_router(meta.router)


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok", "version": app.version}

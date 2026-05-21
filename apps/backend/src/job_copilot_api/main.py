"""FastAPI app entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import ai, applications, cv, forms, health, jd, personas, profiles
from .services.db import init_db

logging.basicConfig(level=settings.log_level)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Job Copilot API",
    version="0.1.0",
    description="Backend for the Job Copilot Chrome extension.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    # Allow any Chrome extension origin (ID differs between dev and prod builds)
    # plus localhost for curl/Swagger during local development.
    allow_origin_regex=r"^(chrome-extension://[a-z]{32}|http://localhost(:\d+)?)$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(cv.router, prefix="/api/v1/cv", tags=["cv"])
app.include_router(profiles.router, prefix="/api/v1/profiles", tags=["profiles"])
app.include_router(forms.router, prefix="/api/v1/forms", tags=["forms"])
app.include_router(applications.router, prefix="/api/v1/applications", tags=["applications"])
app.include_router(personas.router, prefix="/api/v1/personas", tags=["personas"])
app.include_router(jd.router, prefix="/api/v1/jd", tags=["jd"])
app.include_router(ai.router, prefix="/api/v1/ai", tags=["ai"])

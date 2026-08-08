from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.auth import auth_router
from src.api.routes import router
from src.config import get_settings
from src.models.db import Base
from src.services.database import get_async_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    print(f"Starting {settings.app_name} in {settings.app_env} mode")
    engine = get_async_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    print("Shutting down...")


app = FastAPI(
    title="AI Semantic Layer Agent",
    description="AI Agent xây dựng Semantic Layer & định nghĩa chỉ số thống nhất cho doanh nghiệp.",
    version="1.0.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(router, prefix="/api/v1")
app.include_router(auth_router)
app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.app_env}

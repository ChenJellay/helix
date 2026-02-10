"""Helix FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from helix.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    # Startup: initialize connections
    from helix.db.session import init_db
    from helix.rag.vector import get_chroma_client
    from helix.rag.graph import get_neo4j_driver
    from helix.tasks.workers import start_scheduler

    await init_db()
    get_chroma_client()
    get_neo4j_driver()
    start_scheduler()

    yield

    # Shutdown: close connections
    from helix.db.session import close_db
    from helix.rag.graph import close_neo4j_driver
    from helix.tasks.workers import stop_scheduler

    stop_scheduler()
    close_neo4j_driver()
    await close_db()


app = FastAPI(
    title="Helix",
    description="AI-Native Technical Program Management Platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
from helix.api.routes import projects, documents, webhooks, launch, analysis  # noqa: E402

app.include_router(projects.router, prefix="/api", tags=["Projects"])
app.include_router(documents.router, prefix="/api", tags=["Documents"])
app.include_router(webhooks.router, prefix="/api", tags=["Webhooks"])
app.include_router(launch.router, prefix="/api", tags=["Launch"])
app.include_router(analysis.router, prefix="/api", tags=["Analysis"])


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "0.1.0", "env": settings.helix_env}

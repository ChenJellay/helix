"""Helix FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from helix.config import settings

# ── Logging ───────────────────────────────────────────────────────────────────
# Ensure helix.* loggers are visible in container output.
logging.basicConfig(
    level=logging.DEBUG if settings.helix_debug else logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
)
# Quiet down noisy third-party loggers
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("chromadb").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)


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
from helix.api.routes import projects, documents, launch, analysis  # noqa: E402
from helix.api.routes import local_check, workspace  # noqa: E402

app.include_router(projects.router, prefix="/api", tags=["Projects"])
app.include_router(documents.router, prefix="/api", tags=["Documents"])
app.include_router(local_check.router, prefix="/api", tags=["Local Check"])
app.include_router(launch.router, prefix="/api", tags=["Launch"])
app.include_router(analysis.router, prefix="/api", tags=["Analysis"])
app.include_router(workspace.router, prefix="/api", tags=["Workspace"])

# Cloud-only routes — only registered when HELIX_MODE=cloud
if settings.helix_mode == "cloud":
    from helix.api.routes import webhooks  # noqa: E402
    app.include_router(webhooks.router, prefix="/api", tags=["Webhooks"])


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "0.1.0", "env": settings.helix_env}

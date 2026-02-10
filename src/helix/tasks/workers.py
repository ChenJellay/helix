"""Background workers using APScheduler.

Runs periodic tasks:
- Gap analysis for all active launched projects (daily)
- Repo map re-indexing for linked repositories (hourly)
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def start_scheduler() -> None:
    """Start the background task scheduler."""
    global _scheduler
    if _scheduler is not None:
        return

    _scheduler = AsyncIOScheduler()

    # Gap analysis: run daily at 6 AM UTC
    _scheduler.add_job(
        run_gap_analysis_for_all,
        "cron",
        hour=6,
        minute=0,
        id="gap_analysis_daily",
        replace_existing=True,
    )

    # Repo re-indexing: run every 4 hours
    _scheduler.add_job(
        run_repo_reindex,
        "interval",
        hours=4,
        id="repo_reindex",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("Background scheduler started")


def stop_scheduler() -> None:
    """Stop the background task scheduler."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Background scheduler stopped")


async def run_gap_analysis_for_all() -> None:
    """Run gap analysis for all launched projects with metric targets."""
    from helix.db.session import async_session_factory
    from helix.models.db import Project, MetricTarget
    from helix.agents.gap_analyzer import GapAnalyzerAgent

    logger.info("Starting scheduled gap analysis for all launched projects")

    async with async_session_factory() as session:
        # Find all launched projects with metric targets
        result = await session.execute(
            select(Project)
            .where(Project.status == "launched")
            .join(MetricTarget, MetricTarget.project_id == Project.id)
            .distinct()
        )
        projects = result.scalars().all()

        agent = GapAnalyzerAgent()
        for project in projects:
            try:
                await agent.analyze_gaps(
                    project_id=str(project.id),
                    session=session,
                )
                await session.commit()
                logger.info("Gap analysis completed for project %s", project.name)
            except Exception:
                logger.exception("Gap analysis failed for project %s", project.name)
                await session.rollback()


async def run_repo_reindex() -> None:
    """Re-index repository maps for all projects with linked GitHub repos."""
    from helix.db.session import async_session_factory
    from helix.models.db import Project
    from helix.integrations.github import GitHubClient
    from helix.llm import get_llm
    from helix.rag.vector import add_repo_map

    logger.info("Starting scheduled repo re-indexing")

    async with async_session_factory() as session:
        result = await session.execute(
            select(Project).where(Project.github_repo.isnot(None))
        )
        projects = result.scalars().all()

        github = GitHubClient()
        llm = get_llm()

        for project in projects:
            repo = project.github_repo
            if not repo:
                continue

            try:
                # Fetch file tree
                tree = await github.get_repo_tree(repo)
                file_paths = [
                    f["path"] for f in tree
                    if f.get("type") == "blob" and not f["path"].startswith(".")
                ]
                file_tree = "\n".join(file_paths[:200])  # Limit for context window

                # Generate signatures (simplified - just file listing)
                signatures = "\n".join(
                    f"- {p}" for p in file_paths
                    if p.endswith((".py", ".ts", ".js", ".go", ".java", ".rs"))
                )[:3000]

                # Embed and store
                combined = f"Repo: {repo}\n{file_tree}\n{signatures}"
                embeddings = await llm.embed([combined])
                await add_repo_map(repo, file_tree, signatures, embeddings[0])

                logger.info("Re-indexed repo map for %s", repo)
            except Exception:
                logger.exception("Failed to re-index repo %s", repo)

"""Seed database with sample data for demo purposes.

Usage: python -m helix.seed
"""

import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from helix.db.session import async_session_factory, init_db
from helix.models.db import HistoricalEvent, MetricTarget, Project, Document


SEED_DIR = Path(__file__).parent.parent.parent / "seed"


async def seed_historical_events() -> int:
    """Load historical events from seed/sample_risk_history.json."""
    json_path = SEED_DIR / "sample_risk_history.json"
    if not json_path.exists():
        print(f"  Seed file not found: {json_path}")
        return 0

    with open(json_path) as f:
        events_data = json.load(f)

    async with async_session_factory() as session:
        # Check if already seeded
        result = await session.execute(select(HistoricalEvent).limit(1))
        if result.scalar_one_or_none():
            print("  Historical events already seeded, skipping.")
            return 0

        count = 0
        for event in events_data:
            he = HistoricalEvent(
                event_type=event["event_type"],
                team=event["team"],
                duration_days=event["duration_days"],
                outcome=event["outcome"],
                description=event.get("description", ""),
                tags=event.get("tags", []),
            )
            session.add(he)
            count += 1

        await session.commit()
        return count


async def seed_sample_project() -> str | None:
    """Create a sample project with the sample PRD."""
    prd_path = SEED_DIR / "sample_prd.md"
    if not prd_path.exists():
        print(f"  Seed file not found: {prd_path}")
        return None

    prd_content = prd_path.read_text()

    async with async_session_factory() as session:
        # Check if already seeded
        result = await session.execute(
            select(Project).where(Project.name == "Location Recommendations")
        )
        if result.scalar_one_or_none():
            print("  Sample project already exists, skipping.")
            return None

        project = Project(
            name="Location Recommendations",
            description="User location-based restaurant recommendations feature",
            github_repo="helix-team/location-recs",
            status="active",
        )
        session.add(project)
        await session.flush()

        doc = Document(
            project_id=project.id,
            title="User Location-Based Recommendations PRD",
            doc_type="prd",
            content=prd_content,
            indexed="pending",
        )
        session.add(doc)

        # Add metric targets from the PRD
        targets = [
            MetricTarget(
                project_id=project.id,
                metric_name="user_engagement",
                target_value="20",
                unit="percent_increase",
            ),
            MetricTarget(
                project_id=project.id,
                metric_name="recommendation_latency_p50",
                target_value="560",
                unit="ms",
            ),
            MetricTarget(
                project_id=project.id,
                metric_name="user_adoption",
                target_value="75",
                unit="percent",
            ),
            MetricTarget(
                project_id=project.id,
                metric_name="error_rate",
                target_value="0.1",
                unit="percent",
            ),
        ]
        for t in targets:
            session.add(t)

        await session.commit()
        print(f"  Created project: {project.name} (ID: {project.id})")
        return str(project.id)


async def main():
    """Run all seed operations."""
    print("Initializing database connection...")
    await init_db()

    print("Seeding historical events...")
    count = await seed_historical_events()
    print(f"  Loaded {count} historical events.")

    print("Seeding sample project...")
    project_id = await seed_sample_project()
    if project_id:
        print(f"  Sample project ID: {project_id}")

    print("Done! Seed data loaded successfully.")


if __name__ == "__main__":
    asyncio.run(main())

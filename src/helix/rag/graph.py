"""Neo4j knowledge graph operations."""

from __future__ import annotations

import logging
from typing import Any

from neo4j import AsyncGraphDatabase, AsyncDriver

from helix.config import settings

logger = logging.getLogger(__name__)

_driver: AsyncDriver | None = None


def get_neo4j_driver() -> AsyncDriver:
    """Get or create the singleton Neo4j async driver."""
    global _driver
    if _driver is None:
        _driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        logger.info("Connected to Neo4j at %s", settings.neo4j_uri)
    return _driver


def close_neo4j_driver() -> None:
    """Close the Neo4j driver."""
    global _driver
    if _driver is not None:
        # Note: in sync context; for async shutdown use await _driver.close()
        _driver = None
        logger.info("Neo4j driver closed")


async def ensure_indexes() -> None:
    """Create graph indexes if they don't exist."""
    driver = get_neo4j_driver()
    async with driver.session() as session:
        await session.run(
            "CREATE INDEX IF NOT EXISTS FOR (p:Project) ON (p.id)"
        )
        await session.run(
            "CREATE INDEX IF NOT EXISTS FOR (d:Document) ON (d.id)"
        )
        await session.run(
            "CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.name)"
        )
    logger.info("Neo4j indexes ensured")


async def add_project_node(project_id: str, name: str) -> None:
    """Create or update a Project node in the graph."""
    driver = get_neo4j_driver()
    async with driver.session() as session:
        await session.run(
            "MERGE (p:Project {id: $id}) SET p.name = $name",
            id=project_id,
            name=name,
        )


async def add_document_node(
    doc_id: str, project_id: str, title: str, doc_type: str
) -> None:
    """Create a Document node and link it to its Project."""
    driver = get_neo4j_driver()
    async with driver.session() as session:
        await session.run(
            """
            MERGE (d:Document {id: $doc_id})
            SET d.title = $title, d.doc_type = $doc_type
            WITH d
            MATCH (p:Project {id: $project_id})
            MERGE (p)-[:HAS_DOC]->(d)
            """,
            doc_id=doc_id,
            project_id=project_id,
            title=title,
            doc_type=doc_type,
        )


async def add_entity(
    entity_name: str, entity_type: str, doc_id: str
) -> None:
    """Create an Entity node and link it to a Document."""
    driver = get_neo4j_driver()
    async with driver.session() as session:
        await session.run(
            """
            MERGE (e:Entity {name: $name})
            SET e.type = $type
            WITH e
            MATCH (d:Document {id: $doc_id})
            MERGE (d)-[:MENTIONS]->(e)
            """,
            name=entity_name,
            type=entity_type,
            doc_id=doc_id,
        )


async def add_dependency(
    source_project_id: str, target_entity: str, dep_type: str, description: str
) -> None:
    """Create a dependency edge from a Project to an Entity."""
    driver = get_neo4j_driver()
    async with driver.session() as session:
        await session.run(
            """
            MATCH (p:Project {id: $project_id})
            MERGE (e:Entity {name: $entity})
            MERGE (p)-[r:DEPENDS_ON]->(e)
            SET r.type = $dep_type, r.description = $description
            """,
            project_id=source_project_id,
            entity=target_entity,
            dep_type=dep_type,
            description=description,
        )


async def get_project_graph(project_id: str) -> dict[str, Any]:
    """Retrieve the full knowledge subgraph for a project."""
    driver = get_neo4j_driver()
    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (p:Project {id: $project_id})
            OPTIONAL MATCH (p)-[:HAS_DOC]->(d:Document)
            OPTIONAL MATCH (d)-[:MENTIONS]->(e:Entity)
            OPTIONAL MATCH (p)-[dep:DEPENDS_ON]->(dep_entity:Entity)
            RETURN p, collect(DISTINCT d) as docs,
                   collect(DISTINCT e) as entities,
                   collect(DISTINCT {entity: dep_entity, rel: dep}) as dependencies
            """,
            project_id=project_id,
        )
        record = await result.single()
        if not record:
            return {"project": None, "documents": [], "entities": [], "dependencies": []}

        return {
            "project": dict(record["p"]) if record["p"] else None,
            "documents": [dict(d) for d in record["docs"] if d],
            "entities": [dict(e) for e in record["entities"] if e],
            "dependencies": [
                {
                    "entity": dict(dep["entity"]) if dep["entity"] else None,
                    "rel": dict(dep["rel"]) if dep["rel"] else None,
                }
                for dep in record["dependencies"]
                if dep.get("entity")
            ],
        }


async def get_entity_context(entity_name: str) -> list[dict[str, Any]]:
    """Get all projects and documents that mention a given entity."""
    driver = get_neo4j_driver()
    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (e:Entity {name: $name})<-[:MENTIONS]-(d:Document)<-[:HAS_DOC]-(p:Project)
            RETURN p.id as project_id, p.name as project_name,
                   d.id as doc_id, d.title as doc_title
            """,
            name=entity_name,
        )
        records = [record.data() async for record in result]
        return records

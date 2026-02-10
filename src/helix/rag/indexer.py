"""Document indexer - chunking, embedding, and multi-store ingestion."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

from helix.config import settings
from helix.llm import get_llm
from helix.rag import vector, graph

logger = logging.getLogger(__name__)

# Chunking config — uses smaller chunks on SLMs for more precise retrieval
_profile = settings.active_slm_profile
CHUNK_SIZE = _profile.get("chunk_token_limit", 512) * 4  # tokens → chars approx
CHUNK_OVERLAP = max(16, CHUNK_SIZE // 8)

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    length_function=len,
    separators=["\n\n", "\n", ". ", " ", ""],
)


async def index_document(
    doc_id: str,
    project_id: str,
    title: str,
    doc_type: str,
    content: str,
) -> dict[str, Any]:
    """Index a document into both vector store and knowledge graph.

    Pipeline:
    1. Chunk the text
    2. Generate embeddings via the LLM layer
    3. Store chunks + embeddings in ChromaDB
    4. Extract entities via LLM
    5. Store entities and relationships in Neo4j

    Returns:
        Summary of indexing results.
    """
    llm = get_llm()

    # 1. Chunk the document
    chunks = text_splitter.split_text(content)
    logger.info("Split document %s into %d chunks", doc_id, len(chunks))

    # 2. Generate embeddings
    embeddings = await llm.embed(chunks)

    # 3. Store in ChromaDB
    metadatas = [
        {
            "project_id": project_id,
            "doc_id": doc_id,
            "doc_type": doc_type,
            "title": title,
            "chunk_index": i,
        }
        for i in range(len(chunks))
    ]
    await vector.add_documents(
        doc_id=doc_id,
        chunks=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    # 4. Create graph nodes
    await graph.add_document_node(
        doc_id=doc_id,
        project_id=project_id,
        title=title,
        doc_type=doc_type,
    )

    # 5. Extract entities via LLM
    entities = await _extract_entities(content, doc_id)

    return {
        "doc_id": doc_id,
        "chunks": len(chunks),
        "entities": len(entities),
    }


async def _extract_entities(content: str, doc_id: str) -> list[dict[str, str]]:
    """Use the LLM to extract named entities from document content.

    Extracts team names, APIs, technologies, and other key terms,
    then stores them in the Neo4j graph.
    """
    llm = get_llm()

    # Truncate for entity extraction — shorter on SLMs
    max_excerpt = 2000 if settings.is_slm else 4000
    excerpt = content[:max_excerpt] if len(content) > max_excerpt else content

    messages = [
        {
            "role": "system",
            "content": (
                "Extract named entities from the text. "
                "Focus on: team names, API names, technologies, services, "
                "compliance requirements, key concepts. "
                "Return JSON: {\"entities\": [{\"name\": \"...\", \"type\": \"team|api|technology|service|compliance|concept\"}]}"
            ),
        },
        {"role": "user", "content": excerpt},
    ]

    # Use constrained JSON mode for SLMs (router handles provider translation)
    extra: dict[str, Any] = {}
    if settings.is_slm and settings.active_slm_profile.get("use_constrained_json"):
        extra["format"] = "json"

    try:
        response = await llm.complete(
            messages, temperature=0.0, max_tokens=1024, **extra
        )
        data = _parse_json_response(response.content)
        entities = data.get("entities", [])
    except Exception:
        logger.warning("Entity extraction failed for doc %s, using regex fallback", doc_id)
        entities = _regex_entity_fallback(content)

    # Store in graph
    for entity in entities:
        name = entity.get("name", "").strip()
        etype = entity.get("type", "concept")
        if name:
            await graph.add_entity(name, etype, doc_id)

    return entities


def _parse_json_response(text: str) -> dict:
    """Parse a JSON response from the LLM, handling markdown code fences."""
    # Strip markdown code fences if present
    cleaned = re.sub(r"```(?:json)?\s*", "", text)
    cleaned = cleaned.strip().rstrip("`")
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM JSON response")
        return {}


def _regex_entity_fallback(content: str) -> list[dict[str, str]]:
    """Simple regex-based entity extraction as fallback."""
    entities = []
    # Look for capitalized multi-word terms (likely team/service names)
    pattern = r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b"
    # Common articles/prepositions that shouldn't start an entity name
    skip_prefixes = {"The ", "This ", "That ", "These ", "Those ", "When ", "Where ",
                     "With ", "From ", "About ", "After ", "Before "}
    matches = set(re.findall(pattern, content))
    seen: set[str] = set()
    for match in list(matches)[:30]:  # Process more to account for dedup
        name = match
        for prefix in skip_prefixes:
            if name.startswith(prefix):
                name = name[len(prefix):]
                break
        if name and name not in seen:
            seen.add(name)
            entities.append({"name": name, "type": "concept"})
        if len(entities) >= 20:  # Cap at 20
            break
    return entities

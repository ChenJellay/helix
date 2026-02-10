"""ChromaDB vector store operations."""

from __future__ import annotations

import logging
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from helix.config import settings

logger = logging.getLogger(__name__)

_chroma_client: chromadb.HttpClient | None = None

COLLECTION_DOCUMENTS = "helix_documents"
COLLECTION_REPO_MAPS = "helix_repo_maps"


def get_chroma_client() -> chromadb.HttpClient:
    """Get or create the singleton ChromaDB client."""
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        logger.info("Connected to ChromaDB at %s:%s", settings.chroma_host, settings.chroma_port)
    return _chroma_client


def get_collection(name: str = COLLECTION_DOCUMENTS) -> chromadb.Collection:
    """Get or create a ChromaDB collection."""
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


async def add_documents(
    doc_id: str,
    chunks: list[str],
    embeddings: list[list[float]],
    metadatas: list[dict[str, Any]],
    collection_name: str = COLLECTION_DOCUMENTS,
) -> None:
    """Add document chunks to the vector store.

    Args:
        doc_id: Base document ID (chunks get suffixed with _0, _1, etc.)
        chunks: List of text chunks.
        embeddings: Corresponding embedding vectors.
        metadatas: Metadata dict per chunk.
        collection_name: Target collection name.
    """
    collection = get_collection(collection_name)
    ids = [f"{doc_id}_{i}" for i in range(len(chunks))]

    collection.add(
        ids=ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
    )
    logger.info("Added %d chunks for doc %s to collection %s", len(chunks), doc_id, collection_name)


async def query_similar(
    query_embedding: list[float],
    n_results: int = 5,
    where: dict | None = None,
    collection_name: str = COLLECTION_DOCUMENTS,
) -> dict[str, Any]:
    """Query the vector store for similar documents.

    Args:
        query_embedding: The query vector.
        n_results: Number of results to return.
        where: Optional metadata filter.
        collection_name: Collection to search.

    Returns:
        ChromaDB query results dict.
    """
    collection = get_collection(collection_name)
    kwargs: dict[str, Any] = {
        "query_embeddings": [query_embedding],
        "n_results": n_results,
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where

    results = collection.query(**kwargs)
    return results


async def add_repo_map(
    repo_url: str,
    file_tree: str,
    signatures: str,
    embedding: list[float],
) -> None:
    """Store a repository map summary in the vector store."""
    collection = get_collection(COLLECTION_REPO_MAPS)
    doc_content = f"Repository: {repo_url}\n\nFile Tree:\n{file_tree}\n\nSignatures:\n{signatures}"

    collection.upsert(
        ids=[repo_url],
        documents=[doc_content],
        embeddings=[embedding],
        metadatas=[{"repo_url": repo_url, "type": "repo_map"}],
    )
    logger.info("Stored repo map for %s", repo_url)


async def get_repo_map(repo_url: str) -> str | None:
    """Retrieve the repo map for a given repository."""
    collection = get_collection(COLLECTION_REPO_MAPS)
    try:
        result = collection.get(ids=[repo_url], include=["documents"])
        if result["documents"]:
            return result["documents"][0]
    except Exception:
        logger.warning("Repo map not found for %s", repo_url)
    return None

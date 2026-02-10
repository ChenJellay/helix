"""Hybrid retriever - combines vector search and graph traversal."""

from __future__ import annotations

import logging
from typing import Any

from helix.config import settings
from helix.llm import get_llm
from helix.rag import vector, graph

logger = logging.getLogger(__name__)


async def retrieve_similar_documents(
    query: str,
    project_id: str | None = None,
    doc_type: str | None = None,
    n_results: int = 5,
) -> list[dict[str, Any]]:
    """Semantic search for documents similar to the query.

    Args:
        query: Natural language query.
        project_id: Optional filter by project.
        doc_type: Optional filter by document type.
        n_results: Number of results.

    Returns:
        List of matching document chunks with metadata.
    """
    llm = get_llm()

    # Embed the query
    query_embeddings = await llm.embed([query])
    query_embedding = query_embeddings[0]

    # Build metadata filter
    where: dict | None = None
    if project_id or doc_type:
        conditions = {}
        if project_id:
            conditions["project_id"] = project_id
        if doc_type:
            conditions["doc_type"] = doc_type
        where = conditions if len(conditions) == 1 else {"$and": [
            {k: v} for k, v in conditions.items()
        ]}

    # Query vector store
    results = await vector.query_similar(
        query_embedding=query_embedding,
        n_results=n_results,
        where=where,
    )

    # Format results
    documents = []
    if results.get("documents") and results["documents"][0]:
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i] if results.get("metadatas") else {}
            distance = results["distances"][0][i] if results.get("distances") else 0
            documents.append({
                "content": doc,
                "metadata": meta,
                "similarity": 1 - distance,  # Convert distance to similarity
            })

    return documents


async def retrieve_with_graph_context(
    query: str,
    project_id: str,
    n_results: int = 5,
) -> dict[str, Any]:
    """Hybrid retrieval: vector search + graph context enrichment.

    1. Run semantic search for relevant document chunks
    2. Fetch the project's knowledge graph for structural context
    3. Combine both for a richer context

    Args:
        query: Natural language query.
        project_id: The project to search within.
        n_results: Number of vector results.

    Returns:
        Combined context with vector results and graph data.
    """
    # Parallel retrieval of vector and graph data
    vector_results = await retrieve_similar_documents(
        query=query, project_id=project_id, n_results=n_results
    )

    graph_context = await graph.get_project_graph(project_id)

    return {
        "vector_results": vector_results,
        "graph_context": graph_context,
    }


async def retrieve_design_doc(project_id: str) -> str | None:
    """Retrieve the most relevant design document for a project.

    Looks for technical_design type documents first, then falls back
    to any document in the project.  Retrieves fewer chunks on SLMs.
    """
    top_k = settings.active_slm_profile.get("retrieval_top_k", 5)

    results = await retrieve_similar_documents(
        query="technical design architecture specification",
        project_id=project_id,
        doc_type="technical_design",
        n_results=top_k,
    )

    if not results:
        # Fallback: try any document type
        results = await retrieve_similar_documents(
            query="design specification requirements",
            project_id=project_id,
            n_results=top_k,
        )

    if results:
        return "\n\n---\n\n".join(r["content"] for r in results)

    return None


async def retrieve_repo_context(repo_url: str) -> str | None:
    """Retrieve the repo map for context injection."""
    return await vector.get_repo_map(repo_url)

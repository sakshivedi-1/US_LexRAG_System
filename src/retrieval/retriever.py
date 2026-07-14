"""
Main retrieval context function combining hybrid search, citation graph expansion,
and query classification into a single unified output.
"""
import os
import json
import logging

from src.retrieval.hybrid_search import hybrid_search
from src.retrieval.citation_graph import load_graph, graph_expand, GRAPH_PATH
from src.retrieval.query_classifier import classify_query

logger = logging.getLogger(__name__)

_citation_graph = None
_chunk_lookup = None  # doc_id -> list of chunks
PROCESSED_DIR = "data/processed"


def _get_citation_graph():
    global _citation_graph
    if _citation_graph is None:
        if os.path.exists(GRAPH_PATH):
            _citation_graph = load_graph()
        else:
            logger.warning("Citation graph not found. Graph expansion disabled.")
            _citation_graph = None
    return _citation_graph


def _get_chunk_lookup():
    global _chunk_lookup
    if _chunk_lookup is None:
        _chunk_lookup = {}
        for filename in os.listdir(PROCESSED_DIR):
            if not filename.endswith(".json"):
                continue
            filepath = os.path.join(PROCESSED_DIR, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                doc = json.load(f)
            _chunk_lookup[doc["doc_id"]] = {
                "title": doc["title"],
                "doc_type": doc["doc_type"],
                "chunks": doc["chunks"]
            }
    return _chunk_lookup


def retrieve_context(query: str, top_k: int = 8) -> dict:
    """
    Combined retrieval function:
    1. Classify the query.
    2. Run hybrid search (RRF of vector + keyword).
    3. Expand with 1-hop citation graph neighbors.
    4. Return deduplicated context with query type label.

    Returns:
        {
            "query_type": str,
            "chunks": [{ chunk_id, doc_id, doc_title, page_number, text, rrf_score }],
        }
    """
    query_type = classify_query(query)

    # Step 1: Hybrid retrieval
    hybrid_results = hybrid_search(query, top_k=top_k)

    # Step 2: Citation graph expansion (1 hop)
    graph = _get_citation_graph()
    chunk_lookup = _get_chunk_lookup()

    retrieved_doc_ids = list({r["doc_id"] for r in hybrid_results})
    expanded_doc_ids = []

    if graph is not None:
        expanded_doc_ids = graph_expand(retrieved_doc_ids, graph, hops=1)
        # Only keep newly discovered docs (not already in hybrid results)
        new_doc_ids = [d for d in expanded_doc_ids if d not in retrieved_doc_ids]

        for doc_id in new_doc_ids:
            if doc_id in chunk_lookup:
                doc_info = chunk_lookup[doc_id]
                # Add up to 2 chunks from each expanded doc
                for chunk in doc_info["chunks"][:2]:
                    hybrid_results.append({
                        "chunk_id": chunk["chunk_id"],
                        "doc_id": doc_id,
                        "page_number": chunk.get("page_number", 1),
                        "text": chunk["text"],
                        "rrf_score": 0.0,  # No RRF score for graph-expanded chunks
                        "source": "graph_expansion"
                    })

    # Step 3: Deduplicate by chunk_id and enrich with doc title
    seen = set()
    final_chunks = []
    for item in hybrid_results:
        cid = item["chunk_id"]
        if cid in seen:
            continue
        seen.add(cid)

        doc_id = item["doc_id"]
        doc_title = chunk_lookup.get(doc_id, {}).get("title", doc_id)
        item["doc_title"] = doc_title
        final_chunks.append(item)

    return {
        "query_type": query_type,
        "chunks": final_chunks[:top_k + 4],  # Allow a few extra for graph-expanded
    }

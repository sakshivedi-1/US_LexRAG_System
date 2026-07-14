"""
Hybrid Search using Reciprocal Rank Fusion (RRF).
Combines ChromaDB vector search and BM25 keyword search results.
"""
from src.indexing.search import vector_search, keyword_search


def reciprocal_rank_fusion(rankings: list[list[dict]], k: int = 60) -> list[dict]:
    """
    Implements Reciprocal Rank Fusion (RRF).
    rankings: a list of ranked result lists, each item a dict with 'chunk_id'.
    k: smoothing constant (default 60 per the original paper).
    Returns a merged list sorted by fused score, deduplicated by chunk_id.
    """
    scores = {}
    chunk_data = {}

    for ranked_list in rankings:
        for rank, item in enumerate(ranked_list, start=1):
            cid = item["chunk_id"]
            if cid not in scores:
                scores[cid] = 0.0
                chunk_data[cid] = item
            scores[cid] += 1.0 / (k + rank)

    fused = []
    for cid, rrf_score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
        result = dict(chunk_data[cid])
        result["rrf_score"] = rrf_score
        fused.append(result)

    return fused


def hybrid_search(query: str, top_k: int = 8, rrf_k: int = 60) -> list[dict]:
    """
    Fuses vector search and keyword search results using RRF.
    Returns top_k deduplicated results sorted by fused RRF score.
    """
    vector_results = vector_search(query, top_k=top_k)
    keyword_results = keyword_search(query, top_k=top_k)

    fused = reciprocal_rank_fusion([vector_results, keyword_results], k=rrf_k)
    return fused[:top_k]

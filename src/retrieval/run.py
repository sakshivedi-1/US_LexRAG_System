"""
CLI for Phase 3 — builds the citation graph and tests retrieve_context.
Usage: python -m src.retrieval.run
"""
import logging
import json
from src.retrieval.citation_graph import build_citation_graph, save_graph
from src.retrieval.retriever import retrieve_context
from src.retrieval.query_classifier import classify_query

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

TEST_QUERIES = [
    "What are the tax filing deadlines for 2026?",
    "How should section 7463 of the Internal Revenue Code be interpreted for small tax cases?",
    "Compare how the court interpreted deductions in tax cases vs the IRC code provisions.",
    "What is the best recipe for pasta?",
    "What does 26 U.S.C. § 501 say about exempt organizations?",
    "How does the SECURE Act relate to IRS Notice 2026-29?",
    "What is the penalty for late tax filing?",
    "Explain the significance of the appellant's argument in the High Court case.",
    "What does the Point of View document say about deferred compensation?",
    "Is cryptocurrency treated as property under the tax code?",
]


def main():
    # 1. Build and save the citation graph
    logger.info("Building citation graph from processed documents...")
    G = build_citation_graph()
    save_graph(G)
    logger.info(f"Citation graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges.")

    # Show some edge examples
    edges_shown = 0
    for src, tgt, data in G.edges(data=True):
        if edges_shown >= 5:
            break
        if not tgt.startswith("cited::"):
            continue
        logger.info(f"  Graph edge: [{src}] --CITES--> [{data.get('citation_text', tgt)}]")
        edges_shown += 1

    # 2. Test query classifier on 10 sample queries
    print("\n=== Query Classifier Test ===")
    for q in TEST_QUERIES:
        label = classify_query(q)
        print(f"  [{label:15s}] {q}")

    # 3. Test retrieve_context on 3 real queries
    test_retrieval_queries = [
        "What is the tax rate for corporate income?",
        "How does the court define appellant rights?",
        "Compare the IRS notice provisions with the relevant IRC sections.",
    ]

    print("\n=== Retrieval Context Test ===")
    for q in test_retrieval_queries:
        print(f"\n--- Query: '{q}' ---")
        result = retrieve_context(q, top_k=5)
        print(f"  Query Type: {result['query_type']}")
        print(f"  Retrieved {len(result['chunks'])} chunks:")
        for chunk in result["chunks"][:3]:
            src = chunk.get("source", "hybrid")
            score = chunk.get("rrf_score", 0.0)
            print(f"    [{src}] Doc: {chunk['doc_title']} | Page: {chunk['page_number']} | RRF: {score:.4f}")
            print(f"    Snippet: {chunk['text'][:120].strip()}")
            print()


if __name__ == "__main__":
    main()

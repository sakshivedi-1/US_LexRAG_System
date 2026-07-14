"""
Citation Graph using NetworkX.
Builds a directed graph from citation relationships extracted in Phase 2.
Supports 1-hop graph expansion from a set of retrieved doc_ids.
"""
import os
import json
import pickle
import networkx as nx

GRAPH_PATH = "data/citation_graph.pkl"


def build_citation_graph(processed_dir: str = "data/processed") -> nx.DiGraph:
    """
    Constructs a directed citation graph from processed JSON chunks.
    Edge: source_doc -> cited_doc for each citation found in a chunk.
    Node attributes: doc_id, doc_type, title.
    """
    G = nx.DiGraph()

    for filename in os.listdir(processed_dir):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(processed_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            doc = json.load(f)

        doc_id = doc["doc_id"]
        G.add_node(doc_id, doc_type=doc.get("doc_type", ""), title=doc.get("title", ""))

        for chunk in doc.get("chunks", []):
            for citation in chunk.get("citations", []):
                # Use citation string as a synthetic target node ID
                target_id = f"cited::{citation}"
                if not G.has_node(target_id):
                    G.add_node(target_id, doc_type="external", title=citation)
                if not G.has_edge(doc_id, target_id):
                    G.add_edge(doc_id, target_id, citation_text=citation)

    return G


def save_graph(G: nx.DiGraph, path: str = GRAPH_PATH):
    with open(path, "wb") as f:
        pickle.dump(G, f)


def load_graph(path: str = GRAPH_PATH) -> nx.DiGraph:
    with open(path, "rb") as f:
        return pickle.load(f)


def graph_expand(doc_ids: list[str], G: nx.DiGraph, hops: int = 1) -> list[str]:
    """
    Given a list of doc_ids, returns a deduplicated list of neighboring doc_ids
    within `hops` edges (both successors and predecessors for bidirectionality).
    Excludes external cited nodes (those starting with 'cited::').
    """
    neighbors = set(doc_ids)

    for _ in range(hops):
        current = set(neighbors)
        for node in current:
            if node in G:
                for succ in G.successors(node):
                    if not succ.startswith("cited::"):
                        neighbors.add(succ)
                for pred in G.predecessors(node):
                    if not pred.startswith("cited::"):
                        neighbors.add(pred)

    # Return only actual doc IDs (not external citation placeholders)
    return [n for n in neighbors if not n.startswith("cited::")]

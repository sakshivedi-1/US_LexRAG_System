import pickle
import chromadb
from rank_bm25 import BM25Okapi
from src.indexing.indexer import CHROMA_PATH, BM25_PATH, sentence_transformer_ef, tokenize

_chroma_client = None
_chroma_collection = None
_bm25_data = None

def _get_chroma_collection():
    global _chroma_client, _chroma_collection
    if _chroma_collection is None:
        _chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
        _chroma_collection = _chroma_client.get_collection(
            name="legal_chunks",
            embedding_function=sentence_transformer_ef
        )
    return _chroma_collection

def _get_bm25_data():
    global _bm25_data
    if _bm25_data is None:
        with open(BM25_PATH, "rb") as f:
            _bm25_data = pickle.load(f)
    return _bm25_data

def vector_search(query: str, top_k: int = 5) -> list[dict]:
    """
    Returns: {chunk_id, doc_id, page_number, text, score}
    """
    collection = _get_chroma_collection()
    results = collection.query(
        query_texts=[query],
        n_results=top_k
    )
    
    out = []
    if results['ids'] and results['ids'][0]:
        for i in range(len(results['ids'][0])):
            distance = results['distances'][0][i] if 'distances' in results and results['distances'] else 0
            # Convert L2 distance to similarity score
            score = 1.0 / (1.0 + distance)
            
            metadata = results['metadatas'][0][i]
            out.append({
                "chunk_id": results['ids'][0][i],
                "doc_id": metadata["doc_id"],
                "page_number": metadata.get("page_number", 1),
                "text": results['documents'][0][i],
                "score": score
            })
    return out

def keyword_search(query: str, top_k: int = 5) -> list[dict]:
    """
    Returns: {chunk_id, doc_id, page_number, text, score}
    """
    data = _get_bm25_data()
    bm25 = data["bm25"]
    chunks = data["chunks"]
    
    tokenized_query = tokenize(query)
    scores = bm25.get_scores(tokenized_query)
    
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
    
    out = []
    for i in top_indices:
        if scores[i] > 0:
            chunk = chunks[i]
            out.append({
                "chunk_id": chunk["chunk_id"],
                "doc_id": chunk["doc_id"],
                "page_number": chunk.get("page_number", 1),
                "text": chunk["text"],
                "score": float(scores[i])
            })
            
    return out

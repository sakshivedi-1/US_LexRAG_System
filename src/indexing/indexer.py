import os
import pickle
import chromadb
from chromadb.utils import embedding_functions
from rank_bm25 import BM25Okapi

CHROMA_PATH = "data/chroma_db"
BM25_PATH = "data/bm25_index.pkl"

sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

def build_vector_index(chunks):
    """
    Builds a persistent ChromaDB collection.
    """
    os.makedirs(os.path.dirname(CHROMA_PATH), exist_ok=True)
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    
    try:
        client.delete_collection(name="legal_chunks")
    except Exception:
        pass
        
    collection = client.create_collection(
        name="legal_chunks",
        embedding_function=sentence_transformer_ef
    )
    
    ids = []
    documents = []
    metadatas = []
    
    for chunk in chunks:
        ids.append(chunk["chunk_id"])
        documents.append(chunk["text"])
        metadatas.append({
            "doc_id": chunk["doc_id"],
            "doc_type": chunk["doc_type"],
            "page_number": chunk.get("page_number", 1),
            "section_id": str(chunk.get("section_id", "")),
            "citations": ", ".join(chunk.get("citations", []))
        })
        
    batch_size = 500
    for i in range(0, len(ids), batch_size):
        collection.add(
            ids=ids[i:i+batch_size],
            documents=documents[i:i+batch_size],
            metadatas=metadatas[i:i+batch_size]
        )
    print(f"Vector index built with {len(ids)} chunks.")

def tokenize(text):
    return text.lower().split()

def build_keyword_index(chunks):
    """
    Builds a BM25 index and persists it to disk.
    """
    tokenized_corpus = [tokenize(chunk["text"]) for chunk in chunks]
    bm25 = BM25Okapi(tokenized_corpus)
    
    index_data = {
        "bm25": bm25,
        "chunks": chunks
    }
    
    with open(BM25_PATH, "wb") as f:
        pickle.dump(index_data, f)
        
    print(f"Keyword index built with {len(chunks)} chunks.")

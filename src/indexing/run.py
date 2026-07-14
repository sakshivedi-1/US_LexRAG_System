import os
import json
import logging
from src.indexing.citation_extractor import extract_citations
from src.indexing.indexer import build_vector_index, build_keyword_index
from src.indexing.search import vector_search, keyword_search

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, default="data/processed", help="Directory containing processed JSONs")
    args = parser.parse_args()
    
    logger.info("Starting Phase 2: Citation Extraction & Hybrid Indexing...")
    
    all_chunks = []
    
    # 1. Load chunks and extract citations
    for filename in os.listdir(args.input):
        if not filename.endswith(".json"):
            continue
            
        filepath = os.path.join(args.input, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        for chunk in data["chunks"]:
            # Keep doc-level info in chunk for flat indexing
            chunk["doc_id"] = data["doc_id"]
            chunk["doc_type"] = data["doc_type"]
            chunk["doc_title"] = data["title"]
            
            # Extract citations deterministically
            citations = extract_citations(chunk["text"])
            chunk["citations"] = citations
            
            all_chunks.append(chunk)
            
    logger.info(f"Loaded {len(all_chunks)} total chunks. Extracted citations.")
    
    # 2. Build Vector Index
    logger.info("Building persistent ChromaDB vector index...")
    build_vector_index(all_chunks)
    
    # 3. Build Keyword Index
    logger.info("Building BM25 keyword index...")
    build_keyword_index(all_chunks)
    
    logger.info("Indexing complete! Running sanity check queries...")
    
    # 4. Sanity Checks
    queries = [
        "tax changes in 2026",
        "appellant against High Court",
        "definitions in the sample act"
    ]
    
    for q in queries:
        print(f"\n--- Query: '{q}' ---")
        
        print(">> Vector Search Results:")
        v_res = vector_search(q, top_k=2)
        for r in v_res:
            print(f"  Doc: {r['doc_id']} | Page: {r['page_number']} | Score: {r['score']:.4f}")
            print(f"  Snippet: {r['text'][:100].strip()}...\n")
            
        print(">> Keyword Search Results:")
        k_res = keyword_search(q, top_k=2)
        for r in k_res:
            print(f"  Doc: {r['doc_id']} | Page: {r['page_number']} | Score: {r['score']:.4f}")
            print(f"  Snippet: {r['text'][:100].strip()}...\n")

if __name__ == "__main__":
    main()

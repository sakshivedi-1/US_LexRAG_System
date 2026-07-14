# LexRAG System

LexRAG is a high-precision Retrieval-Augmented Generation (RAG) system designed specifically for the US Tax & Legal domain. It allows legal professionals to ask natural-language questions and receive precise, summarized answers backed by verifiable, exact citations (document name + page number).

This repository contains the complete source code, evaluation metrics, and configuration files to deploy the system.

## Live Deployment Links
- Frontend UI (Vercel): [Insert Vercel URL Here]
- Backend API (Render): [Insert Render URL Here]

## System Architecture

LexRAG is built on a multi-stage pipeline designed for structural accuracy and hallucination prevention.

### Pipeline Flow

1. Phase 1: Ingestion
   PyMuPDF -> Structural Chunking -> JSON (data/processed/)
   Applies document-type-aware boundaries (Section, Paragraph, or Header boundaries).

2. Phase 2: Indexing
   Citation Extractor (regex+spaCy)
   ChromaDB (Persistent local vector store using all-MiniLM-L6-v2)
   BM25Okapi (Pickled to disk for keyword search)

3. Phase 3: Retrieval
   query -> [Classify] -> factual / interpretive / multi_hop / out_of_scope
   VectorSearch (ChromaDB) + KeywordSearch (BM25)
   Reciprocal Rank Fusion (RRF Fusion)
   NetworkX Citation Graph (1-hop graph expansion)
   -> retrieve_context()

4. Phase 4: Generation
   context -> [Format] -> Claude/Gemini Prompt
   PASS 1: LLM generates {answer, citations[]}
   PASS 2: Programmatic verification against retrieved chunks
   Verified Citations (kept) vs Flagged Hallucinations (stripped from output)
   -> FastAPI: POST /ask, POST /summarize

5. Phase 5: UI & Deployment
   Next.js (Vercel) frontend wired to FastAPI backend (Render).

### Design Decisions

Embedded-Index, No Docker
ChromaDB is configured as a persistent local client. BM25 runs fully in-process and is pickled to disk. This eliminates all external server dependencies (no Elasticsearch, no Qdrant, no Docker) making deployment significantly simpler.

Structural Chunking
Each document type uses a different chunking strategy. Acts use Section/Article boundaries, Judgments use paragraph markers, and POVs use header detection. This preserves semantic coherence.

Two-Pass Citation Verification
To solve hallucinations, Pass 1 generates an answer with a structured citation list. Pass 2 checks every (doc_name, page_number) pair against the actual retrieved chunks. Any citation not found is flagged and stripped.

Reciprocal Rank Fusion (RRF)
Combines vector scores and BM25 keyword scores without requiring score normalization.

Citation Graph (NetworkX)
Builds a directed graph of citation relationships. Graph expansion fetches 1-hop neighbors of retrieved documents, surfacing additional relevant context.

## Project Deliverables

All required assignment deliverables are included in this repository:
1. Overall Approach & Architecture: Detailed above.
2. Prompts Used: See PROMPTS.md for the exact system prompts and instructions used for the generation models.
3. Golden Set: See eval/golden_set.csv for the evaluation dataset containing 100 domain-specific queries and expected answers used to benchmark system accuracy.
4. Source Code: The complete modular codebase is located in src/ (Python backend) and ui/ (Next.js frontend).
5. Deployed UI: Links provided at the top of this document.

## Local Development Setup

1. Clone & Install Dependencies
```bash
git clone https://github.com/sakshivedi-1/US_LexRAG_System.git
cd US_LexRAG_System
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Environment Variables
Create a .env file in the root directory (do not commit this file). Refer to .env.example for the required keys.

3. Run the Backend
```bash
uvicorn src.generation.api:app --reload --port 8000
```
The API will be available at http://localhost:8000

4. Run the Frontend
```bash
cd ui
npm install
npm run dev
```
The Next.js UI will be available at http://localhost:3000

## Security Note
This repository strictly utilizes .gitignore to prevent any sensitive credentials, .env files, or API keys from being committed. Always use environment variables for keys.

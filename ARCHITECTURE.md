# LexRAG — Architecture Document

## System Overview

LexRAG is a high-precision Retrieval-Augmented Generation (RAG) system designed for US Tax & Legal domain research. It allows legal professionals to ask natural-language questions and receive precise, summarized answers with exact, verifiable citations (document name + page number).

```
PDF Documents (data/raw/)
        │
        ▼
┌─────────────────────┐
│   Phase 1: Ingestion│  PyMuPDF → Structural Chunking → JSON (data/processed/)
│   src/ingestion/    │  doc_type-aware: Section/¶/Header boundaries
└────────┬────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│              Phase 2: Indexing                       │
│  ┌──────────────┐   ┌──────────────────────────────┐│
│  │ Citation      │   │ ChromaDB (bge-base-en-v1.5)  ││
│  │ Extractor    │   │ Persistent local vector store ││
│  │ regex+spaCy  │   ├──────────────────────────────┤│
│  └──────────────┘   │ BM25Okapi (rank_bm25)         ││
│                     │ Pickled to disk               ││
│                     └──────────────────────────────┘│
└────────┬────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│           Phase 3: Retrieval                        │
│  query → [Classify] → factual/interpretive/         │
│           multi_hop/out_of_scope                    │
│                │                                    │
│     ┌──────────┴──────────┐                        │
│     ▼                     ▼                        │
│  VectorSearch          KeywordSearch               │
│  (ChromaDB)            (BM25)                      │
│     └──────────┬──────────┘                        │
│                ▼                                    │
│           RRF Fusion                               │
│                │                                    │
│                ▼                                    │
│      NetworkX Citation Graph                       │
│      (1-hop graph expansion)                       │
│                │                                    │
│                ▼                                    │
│         retrieve_context()                          │
└────────┬────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│           Phase 4: Generation                       │
│                                                     │
│  context → [Format] → Claude Prompt                │
│                │                                    │
│         PASS 1: Claude generates                   │
│         {answer, citations[]}                      │
│                │                                    │
│         PASS 2: Programmatic verification          │
│         ┌──────┴─────────────┐                    │
│         ▼                    ▼                     │
│   Verified Citations    Flagged (Hallucinated)    │
│   (in retrieved ctx)    (stripped from output)    │
│                                                     │
│   → FastAPI: POST /ask, POST /summarize            │
└────────┬────────────────────────────────────────────┘
         │
         ▼
┌─────────────────┐    ┌──────────────────────────────┐
│ Phase 5: Eval   │    │ Phase 6: UI & Deployment      │
│ eval/run.py     │    │ Next.js (Vercel)               │
│ golden_set.csv  │    │ FastAPI backend (Render)       │
│ Recall@5/10/MRR │    │ ← wired via NEXT_PUBLIC_API_URL│
│ Citation Acc.   │    └──────────────────────────────┘
│ LLM Judge       │
└─────────────────┘
```

## Design Decisions

### Embedded-Index, No Docker

**ChromaDB** is configured as a persistent local client (`chromadb.PersistentClient(path="data/chroma_db")`).  
**BM25** (`rank_bm25`) runs fully in-process and is pickled to `data/bm25_index.pkl`.

This eliminates all external server dependencies — no Elasticsearch, no Qdrant, no Docker — making local development, CI, and serverless deployment significantly simpler.

### Structural Chunking (Not Fixed Token Windows)

Each document type uses a different chunking strategy:
- **Acts**: `Section N` / `Article N` regex boundaries
- **Judgments**: `¶ N` / `[N]` paragraph markers
- **POV / Tax**: Header detection (all-caps or Title Case short lines)

This preserves semantic coherence within legal sections, avoiding mid-sentence or mid-clause splits that degrade retrieval quality.

### Two-Pass Citation Verification

The hallucination problem in legal RAG is critical — a wrong case citation can mislead a legal professional.

Our solution:
1. **Pass 1**: Claude generates an answer + structured `citations[]` list.
2. **Pass 2**: Every `(doc_name, page_number)` pair is checked against the **actual retrieved chunks**. Any citation not found is flagged and stripped, not silently displayed.

This creates an audit trail — users can see both verified and flagged citations, allowing full transparency.

### Reciprocal Rank Fusion (RRF)

RRF (Cormack et al., 2009) is a parameter-light fusion method that combines results from multiple ranked lists without requiring score normalization. We use `k=60` (the original paper's recommendation), combining `bge-base-en-v1.5` vector scores and BM25 keyword scores.

### Citation Graph (NetworkX)

Legal documents heavily cross-reference each other. We build a directed graph where:
- Nodes = documents
- Edges = citation relationships (extracted via regex + spaCy)

`graph_expand(doc_ids, hops=1)` fetches 1-hop neighbors of retrieved documents, surfacing additional relevant context beyond what direct search finds.

## Deployment

| Component | Platform | Notes |
|-----------|----------|-------|
| Next.js frontend | Vercel | `ui/` directory, `NEXT_PUBLIC_API_URL` env var |
| FastAPI backend | Render / Railway | `uvicorn src.generation.api:app`, requires `ANTHROPIC_API_KEY` |
| ChromaDB | Embedded (disk) | `data/chroma_db/` — persists on Render disk or mount |
| BM25 Index | Embedded (disk) | `data/bm25_index.pkl` |

## Deliverables Checklist

- [x] Ingestion pipeline (`src/ingestion/`)
- [x] Hybrid indexing — ChromaDB + BM25 (`src/indexing/`)
- [x] Hybrid retrieval + citation graph (`src/retrieval/`)
- [x] Generation with two-pass verification (`src/generation/`)
- [x] FastAPI backend (`POST /ask`, `POST /summarize`, `GET /health`)
- [x] Golden Set (`eval/golden_set.csv`) — 100 rows
- [x] Evaluation runner (`eval/run.py`) — Recall@5/10, MRR, Citation Accuracy, LLM Judge
- [x] Next.js Frontend (`ui/`)
- [x] Architecture Document (`ARCHITECTURE.md`)
- [x] Prompts Document (`PROMPTS.md`)

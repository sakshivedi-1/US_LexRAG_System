# LexRAG — Prompts Document

This document records every key prompt used to build the LexRAG system, in phase order.

---

## Phase 1 — Ingestion & Structural Chunking

**System Build Prompt:**
> Build an ingestion pipeline in /src/ingestion that reads PDFs from /data/raw/Act, /data/raw/Court_Judgements, /data/raw/Point_of_view, /data/raw/Tax, using the subfolder name as doc_type (map to act, judgment, pov, tax_doc). Extract text with PyMuPDF, preserving page number per block. Chunk on structural boundaries per doc_type (section numbers for Acts, ¶/paragraph markers for Judgments, headers for POV/Tax) — not fixed token windows. Output one JSON per document to /data/processed.

---

## Phase 2 — Citation Extraction & Hybrid Indexing

**System Build Prompt:**
> In /src/indexing, build: A deterministic citation extractor (regex + spaCy NER) tuned for US legal citation patterns (e.g. 26 U.S.C. § X, Name v. Name, F.3d ...). A persistent ChromaDB collection, embedding every chunk with bge-base-en-v1.5 (sentence-transformers). An in-process BM25 index via rank_bm25, persisted to disk. Two functions — vector_search(query, top_k) and keyword_search(query, top_k).

---

## Phase 3 — Hybrid Fusion, Citation Graph, Query Classification

**System Build Prompt:**
> In /src/retrieval, build: hybrid_search(query, top_k) using Reciprocal Rank Fusion (RRF, k=60). A citation graph in networkx built from chunk citations fields. graph_expand(doc_ids, hops=1). A rule-based query classifier tagging queries as factual, interpretive, multi_hop, or out_of_scope. One combined retrieve_context(query, top_k=8) function.

---

## Phase 4 — Generation with Verified Citations

### Claude System Prompt (used in `src/generation/generator.py`)

```
You are a precise legal research assistant specializing in US Tax and Legal documents.
You will be given a CONTEXT block containing excerpts from legal documents, each labeled with its source.
Your task is to answer the user's question strictly from the provided context.

STRICT RULES:
1. Answer ONLY from the provided context — never from prior knowledge.
2. Every factual claim in your answer MUST be cited with the exact doc_name and page_number from the context.
3. If the context does not contain enough information to answer the question, return INSUFFICIENT_CONTEXT.
4. You MUST respond ONLY with a valid JSON object matching this exact schema:
   {
     "answer": "Your answer here, with inline references like (Doc: docname, Page: N).",
     "citations": [
       {
         "doc_name": "exact document title as shown in context",
         "page_number": <integer>,
         "chunk_text_snippet": "a short verbatim snippet from the cited chunk"
       }
     ]
   }
5. If returning INSUFFICIENT_CONTEXT, use: {"answer": "INSUFFICIENT_CONTEXT", "citations": []}
```

### LLM-as-Judge Prompt (used in `eval/run.py`)

```
You are an objective evaluator of legal research answers.
Rate the following generated answer against the ground truth on a scale from 0.0 to 1.0.

Scale:
1.0 = Fully correct and complete
0.75 = Mostly correct with minor omissions
0.5 = Partially correct
0.25 = Mostly incorrect or misleading
0.0 = Completely wrong or hallucinated

QUESTION: {query}
GROUND TRUTH: {ground_truth}
GENERATED ANSWER: {generated_answer}

Respond with ONLY a JSON object: {"score": <float>, "reason": "<one sentence reason>"}
```

### Map-Reduce Summarization Prompt — Map Step

```
Summarize the following legal document section in 2-3 sentences. 
Be precise and preserve key legal facts, citations, and figures.

Section: {section_id}
Content: {text}

Summary:
```

### Map-Reduce Summarization Prompt — Reduce Step

```
You are a legal research assistant. Below are summaries of individual sections of a legal document.
Write a coherent, concise 3-5 paragraph overall summary of the document.
Preserve all key legal facts, statutory references, and rulings.

Section Summaries:
{combined}

Overall Document Summary:
```

---

## Phase 5 — Golden Set & Evaluation

**Golden Set Generation Criteria:**
> Create 100 rows spanning: factual (40 rows — specific code sections, rates, deadlines), interpretive (30 rows — how courts/IRS interpret provisions), multi_hop (20 rows — relationships between multiple documents), unanswerable (10 rows — out-of-scope or unknowable questions). Columns: query, ground_truth_answer, source_document, category.

---

## Phase 6 — UI, Deployment, Documentation

**UI Design Prompt:**
> Build a Next.js frontend with: a search box accepting natural-language legal queries, a generated answer panel, an expandable verified citations list (doc name, page number, source snippet), a flagged/hallucinated citations panel, collapsible retrieved context chunks. Use dark glassmorphism design with gold accents for a premium government portal aesthetic.

"""
FastAPI backend for the Legal RAG system.
Exposes:
  POST /ask          - Q&A with verified citations
  POST /summarize    - Document summarization (map-reduce)
  GET  /health       - Health check
"""
import os
import json
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from src.retrieval.retriever import retrieve_context
from src.generation.generator import generate_answer, map_reduce_summarize
from src.generation.llm_client import LLMClient, get_llm_client

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="LexRAG — Legal Research Assistant",
    description="High-precision RAG for US Tax & Legal documents with verified citations.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _get_client() -> LLMClient:
    try:
        return get_llm_client()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ----- Request/Response Models -----

class AskRequest(BaseModel):
    query: str
    top_k: int = 8

class AskResponse(BaseModel):
    query: str
    query_type: str
    answer: str
    verified_citations: list[dict]
    flagged_citations: list[dict]
    retrieved_chunks: list[dict]

class SummarizeRequest(BaseModel):
    doc_id: str

class SummarizeResponse(BaseModel):
    doc_id: str
    summary: str


# ----- Endpoints -----

@app.get("/health")
def health():
    return {"status": "ok", "service": "LexRAG Backend"}


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest):
    """
    Q&A endpoint.
    Retrieves context, generates an answer via the configured LLM provider
    (Gemini → Groq fallback), and verifies all citations.
    Hallucinated citations are flagged and stripped from the verified list.
    """
    logger.info(f"Received /ask query: {request.query}")

    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    # Step 1: Retrieve context
    context = retrieve_context(request.query, top_k=request.top_k)
    query_type = context["query_type"]
    chunks = context["chunks"]

    if not chunks:
        return AskResponse(
            query=request.query,
            query_type=query_type,
            answer="INSUFFICIENT_CONTEXT",
            verified_citations=[],
            flagged_citations=[],
            retrieved_chunks=[]
        )

    # Step 2: Generate with verified citations
    client = _get_client()
    result = generate_answer(request.query, chunks, client)

    return AskResponse(
        query=request.query,
        query_type=query_type,
        answer=result["answer"],
        verified_citations=result["verified_citations"],
        flagged_citations=result["flagged_citations"],
        retrieved_chunks=[{
            "chunk_id": c["chunk_id"],
            "doc_title": c.get("doc_title", ""),
            "page_number": c.get("page_number", 1),
            "text": c["text"][:300],
        } for c in chunks],
    )


@app.post("/summarize", response_model=SummarizeResponse)
def summarize(request: SummarizeRequest):
    """
    Summarization endpoint. Loads all chunks for a doc_id and runs map-reduce summarization.
    """
    import os
    processed_dir = "data/processed"
    target_file = None

    # Find the processed JSON for this doc_id
    for filename in os.listdir(processed_dir):
        if not filename.endswith(".json"):
            continue
        if request.doc_id in filename:
            target_file = os.path.join(processed_dir, filename)
            break

    if not target_file:
        # Try matching by title
        for filename in os.listdir(processed_dir):
            if not filename.endswith(".json"):
                continue
            filepath = os.path.join(processed_dir, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                doc = json.load(f)
            if doc.get("title", "").lower() == request.doc_id.lower() or doc.get("doc_id") == request.doc_id:
                target_file = filepath
                break

    if not target_file:
        raise HTTPException(status_code=404, detail=f"Document '{request.doc_id}' not found.")

    with open(target_file, "r", encoding="utf-8") as f:
        doc = json.load(f)

    client = _get_client()
    summary = map_reduce_summarize(doc["chunks"], client)

    return SummarizeResponse(doc_id=request.doc_id, summary=summary)

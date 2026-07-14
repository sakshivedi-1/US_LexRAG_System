"""
Core generation module.
Implements the mandatory two-pass design:
  Pass 1: LLM generates structured JSON {answer, citations}
  Pass 2: Programmatic verification of every citation against retrieved context

LLM provider is handled transparently by LLMClient (Gemini → Groq fallback).
"""
import logging

from src.generation.llm_client import LLMClient, parse_json_response

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a precise legal research assistant specializing in US Tax and Legal documents.
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
"""


def format_context(chunks: list[dict]) -> str:
    """Formats retrieved chunks into a labeled context block for the LLM prompt."""
    parts = []
    for i, chunk in enumerate(chunks, 1):
        doc_title = chunk.get("doc_title", chunk.get("doc_id", "Unknown"))
        page = chunk.get("page_number", "?")
        text = chunk.get("text", "")
        parts.append(f"[{i}] [{doc_title} | Page {page}]\n{text}")
    return "\n\n".join(parts)


def verify_citations(citations: list[dict], chunks: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Pass 2: Programmatic citation verification.
    Checks each citation's (doc_name, page_number) against the retrieved chunks.
    Returns (verified_citations, flagged_citations).
    """
    # Build a lookup of (normalized_title, page_number) -> chunk text
    context_lookup = {}
    for chunk in chunks:
        doc_title = chunk.get("doc_title", chunk.get("doc_id", "")).lower().strip()
        page = chunk.get("page_number")
        key = (doc_title, page)
        context_lookup[key] = chunk.get("text", "")

    verified = []
    flagged = []

    for cit in citations:
        cited_doc = (cit.get("doc_name", "") or "").lower().strip()
        cited_page = cit.get("page_number")

        # Exact match first
        if (cited_doc, cited_page) in context_lookup:
            verified.append(cit)
            continue

        # Fuzzy match: check if cited doc name is contained in any key
        matched = False
        for (title, page), text in context_lookup.items():
            if cited_doc in title or title in cited_doc:
                if cited_page == page:
                    verified.append(cit)
                    matched = True
                    break

        if not matched:
            cit["_flag"] = "HALLUCINATED - not found in retrieved context"
            flagged.append(cit)

    return verified, flagged


def _call_llm(context_text: str, query: str, client: LLMClient) -> dict:
    """Calls the LLM via the unified client and parses the JSON response."""
    user_message = f"""CONTEXT:
{context_text}

QUESTION: {query}

Respond ONLY with the JSON object as specified. Do not include any text outside the JSON."""

    raw_text = client.generate(
        prompt=user_message,
        system_prompt=SYSTEM_PROMPT,
        max_tokens=2048,
    )
    return parse_json_response(raw_text, source=f"provider={client.last_provider}")


def generate_answer(query: str, chunks: list[dict], client: LLMClient) -> dict:
    """
    Full two-pass generation pipeline.
    Returns: {answer, verified_citations, flagged_citations}
    """
    if not chunks:
        return {
            "answer": "INSUFFICIENT_CONTEXT",
            "verified_citations": [],
            "flagged_citations": []
        }

    context_text = format_context(chunks)

    # Pass 1: LLM generation
    logger.info("Pass 1: Calling LLM for generation...")
    raw_output = _call_llm(context_text, query, client)

    answer = raw_output.get("answer", "INSUFFICIENT_CONTEXT")
    citations = raw_output.get("citations", [])

    if answer == "INSUFFICIENT_CONTEXT":
        return {
            "answer": "INSUFFICIENT_CONTEXT",
            "verified_citations": [],
            "flagged_citations": []
        }

    # Pass 2: Verification
    logger.info(f"Pass 2: Verifying {len(citations)} citations...")
    verified, flagged = verify_citations(citations, chunks)
    logger.info(f"  Verified: {len(verified)}, Flagged/Hallucinated: {len(flagged)}")

    return {
        "answer": answer,
        "verified_citations": verified,
        "flagged_citations": flagged,
    }


def map_reduce_summarize(doc_chunks: list[dict], client: LLMClient) -> str:
    """
    Map-reduce summarization for full document requests.
    Step 1: Summarize each section/chunk individually.
    Step 2: Combine all section summaries into a final summary.
    """
    if not doc_chunks:
        return "No content to summarize."

    # Map: summarize each chunk
    section_summaries = []
    for i, chunk in enumerate(doc_chunks):
        section_id = chunk.get("section_id", f"Section {i+1}")
        text = chunk.get("text", "")
        if not text.strip():
            continue

        prompt = f"""Summarize the following legal document section in 2-3 sentences.
Be precise and preserve key legal facts, citations, and figures.

Section: {section_id}
Content:
{text[:2000]}

Summary:"""

        summary = client.generate(prompt=prompt, max_tokens=256)
        section_summaries.append(f"[{section_id}]: {summary.strip()}")

    if not section_summaries:
        return "No summarizable content found."

    # Reduce: combine all section summaries
    combined = "\n\n".join(section_summaries)
    reduce_prompt = f"""You are a legal research assistant. Below are summaries of individual sections of a legal document.
Write a coherent, concise 3-5 paragraph overall summary of the document.
Preserve all key legal facts, statutory references, and rulings.

Section Summaries:
{combined[:4000]}

Overall Document Summary:"""

    return client.generate(prompt=reduce_prompt, max_tokens=1024).strip()


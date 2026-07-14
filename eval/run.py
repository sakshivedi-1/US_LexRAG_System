"""
Evaluation runner for the Legal RAG system.
Computes:
  - Recall@5, Recall@10, MRR (retrieval metrics)
  - Citation Accuracy (does verified citation match source_document?)
  - Correctness Score (LLM-as-judge comparing answer to ground truth)

Usage: python eval/run.py [--sample N] [--no-generation]
"""
import os
import sys
import csv
import json
import logging
import argparse
from datetime import datetime

# Allow running from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from src.retrieval.retriever import retrieve_context
from src.generation.generator import generate_answer
from src.generation.llm_client import LLMClient, get_llm_client

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

GOLDEN_SET_PATH = "eval/golden_set.csv"
REPORT_CSV_PATH = "eval/report.csv"
REPORT_MD_PATH = "eval/report.md"


def load_golden_set(path: str) -> list[dict]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def compute_recall_and_mrr(query: str, source_doc: str, top_k_chunks: list[dict], recall_at: list[int]) -> dict:
    """Checks if source_doc appears in the retrieved chunks at various cutoffs."""
    if source_doc == "N/A":
        return {"recall@5": None, "recall@10": None, "mrr": None}

    source_lower = source_doc.lower()
    results = {}

    # MRR
    mrr = 0.0
    for rank, chunk in enumerate(top_k_chunks, 1):
        doc_title = chunk.get("doc_title", "").lower()
        if source_lower in doc_title or doc_title in source_lower:
            mrr = 1.0 / rank
            break
    results["mrr"] = mrr

    for k in recall_at:
        found = False
        for chunk in top_k_chunks[:k]:
            doc_title = chunk.get("doc_title", "").lower()
            if source_lower in doc_title or doc_title in source_lower:
                found = True
                break
        results[f"recall@{k}"] = 1.0 if found else 0.0

    return results


def llm_correctness_judge(query: str, ground_truth: str, generated_answer: str, client: LLMClient) -> float:
    """Uses the LLM as a judge to score the generated answer (0.0 to 1.0)."""
    if generated_answer == "INSUFFICIENT_CONTEXT":
        return 0.0

    prompt = f"""You are an objective evaluator of legal research answers.
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

Respond with ONLY a JSON object: {{"score": <float>, "reason": "<one sentence reason>"}}"""

    try:
        raw = client.generate(prompt=prompt, max_tokens=128)
        import json as _json
        data = _json.loads(raw.strip())
        return float(data.get("score", 0.0))
    except Exception as e:
        logger.warning(f"Judge call failed: {e}")
        return 0.0


def check_citation_accuracy(verified_citations: list[dict], source_doc: str) -> float:
    """Checks if any verified citation matches the expected source document."""
    if source_doc == "N/A":
        return None
    if not verified_citations:
        return 0.0
    source_lower = source_doc.lower()
    for cit in verified_citations:
        cited_doc = (cit.get("doc_name", "") or "").lower()
        if source_lower in cited_doc or cited_doc in source_lower:
            return 1.0
    return 0.0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=None, help="Run only N rows (for quick testing)")
    parser.add_argument("--no-generation", action="store_true", help="Skip generation, only eval retrieval")
    args = parser.parse_args()

    golden_set = load_golden_set(GOLDEN_SET_PATH)
    if args.sample:
        golden_set = golden_set[:args.sample]

    client = None
    if not args.no_generation:
        try:
            client = get_llm_client()  # Gemini primary, Groq fallback
            logger.info(f"LLM client initialized (providers: Gemini → Groq)")
        except RuntimeError as e:
            logger.warning(f"No LLM API keys configured: {e}. Running retrieval-only evaluation.")
            args.no_generation = True

    results = []
    total = len(golden_set)

    for i, row in enumerate(golden_set):
        query = row["query"]
        ground_truth = row["ground_truth_answer"]
        source_doc = row["source_document"]
        category = row["category"]

        logger.info(f"[{i+1}/{total}] [{category}] {query[:80]}...")

        try:
            # Retrieval
            context = retrieve_context(query, top_k=10)
            chunks = context["chunks"]
            query_type_pred = context["query_type"]

            recall = compute_recall_and_mrr(query, source_doc, chunks, recall_at=[5, 10])

            # Generation
            answer = "SKIPPED"
            verified_citations = []
            flagged_citations = []
            correctness_score = None
            citation_accuracy = None

            if not args.no_generation and client and category != "unanswerable":
                gen_result = generate_answer(query, chunks[:8], client)
                answer = gen_result["answer"]
                verified_citations = gen_result["verified_citations"]
                flagged_citations = gen_result["flagged_citations"]
                citation_accuracy = check_citation_accuracy(verified_citations, source_doc)
                correctness_score = llm_correctness_judge(query, ground_truth, answer, client)
            elif category == "unanswerable":
                # For unanswerable, correct response is INSUFFICIENT_CONTEXT or similar
                answer = "N/A - unanswerable category"
                correctness_score = 1.0 if not chunks else 0.5

            results.append({
                "query": query,
                "category": category,
                "source_document": source_doc,
                "query_type_predicted": query_type_pred,
                "recall@5": recall.get("recall@5"),
                "recall@10": recall.get("recall@10"),
                "mrr": recall.get("mrr"),
                "answer": answer[:200] if answer else "",
                "citation_accuracy": citation_accuracy,
                "correctness_score": correctness_score,
                "num_verified_citations": len(verified_citations),
                "num_flagged_citations": len(flagged_citations),
            })

        except Exception as e:
            logger.error(f"Error on row {i+1}: {e}")
            results.append({
                "query": query,
                "category": category,
                "source_document": source_doc,
                "query_type_predicted": "error",
                "recall@5": 0, "recall@10": 0, "mrr": 0,
                "answer": f"ERROR: {str(e)[:100]}",
                "citation_accuracy": 0,
                "correctness_score": 0,
                "num_verified_citations": 0,
                "num_flagged_citations": 0,
            })

    # Write CSV report
    with open(REPORT_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        fieldnames = list(results[0].keys()) if results else []
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    logger.info(f"Per-query report saved to {REPORT_CSV_PATH}")

    # Compute aggregates
    valid_recall5 = [r["recall@5"] for r in results if r["recall@5"] is not None]
    valid_recall10 = [r["recall@10"] for r in results if r["recall@10"] is not None]
    valid_mrr = [r["mrr"] for r in results if r["mrr"] is not None]
    valid_citation_acc = [r["citation_accuracy"] for r in results if r["citation_accuracy"] is not None]
    valid_correctness = [r["correctness_score"] for r in results if r["correctness_score"] is not None]

    avg = lambda lst: (sum(lst) / len(lst)) if lst else 0.0

    agg = {
        "total_queries": total,
        "avg_recall@5": avg(valid_recall5),
        "avg_recall@10": avg(valid_recall10),
        "avg_mrr": avg(valid_mrr),
        "avg_citation_accuracy": avg(valid_citation_acc),
        "avg_correctness_score": avg(valid_correctness),
    }

    # Category breakdown
    categories = set(r["category"] for r in results)
    cat_stats = {}
    for cat in categories:
        cat_rows = [r for r in results if r["category"] == cat]
        cat_r5 = [r["recall@5"] for r in cat_rows if r["recall@5"] is not None]
        cat_stats[cat] = {
            "count": len(cat_rows),
            "avg_recall@5": avg(cat_r5),
        }

    # Worst performing (by correctness score)
    scored = [r for r in results if r["correctness_score"] is not None]
    worst = sorted(scored, key=lambda x: x["correctness_score"])[:5]

    # Write MD report
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(REPORT_MD_PATH, "w", encoding="utf-8") as f:
        f.write(f"# LexRAG Evaluation Report\n\n")
        f.write(f"**Generated:** {now}  \n")
        f.write(f"**Total Queries Evaluated:** {total}\n\n")
        f.write("## Aggregate Metrics\n\n")
        f.write("| Metric | Value |\n")
        f.write("|--------|-------|\n")
        f.write(f"| Recall@5 | {agg['avg_recall@5']:.3f} |\n")
        f.write(f"| Recall@10 | {agg['avg_recall@10']:.3f} |\n")
        f.write(f"| MRR | {agg['avg_mrr']:.3f} |\n")
        f.write(f"| Citation Accuracy | {agg['avg_citation_accuracy']:.3f} |\n")
        f.write(f"| LLM Correctness Score | {agg['avg_correctness_score']:.3f} |\n")
        f.write("\n## Category Breakdown\n\n")
        f.write("| Category | Count | Recall@5 |\n")
        f.write("|----------|-------|----------|\n")
        for cat, stats in cat_stats.items():
            f.write(f"| {cat} | {stats['count']} | {stats['avg_recall@5']:.3f} |\n")
        f.write("\n## Worst Performing Queries (by Correctness Score)\n\n")
        for w in worst:
            f.write(f"- **[{w['category']}]** `{w['query'][:80]}...`  \n")
            f.write(f"  Score: {w['correctness_score']:.2f} | Answer: {w['answer'][:80]}\n\n")

    logger.info(f"Evaluation report saved to {REPORT_MD_PATH}")
    print(f"\n=== Evaluation Complete ===")
    for k, v in agg.items():
        print(f"  {k}: {v:.3f}" if isinstance(v, float) else f"  {k}: {v}")


if __name__ == "__main__":
    main()

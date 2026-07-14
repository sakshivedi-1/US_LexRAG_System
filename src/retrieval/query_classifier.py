"""
Rule-based query classifier for legal queries.
Tags each query as one of: factual, interpretive, multi_hop, out_of_scope.
"""
import re

FACTUAL_PATTERNS = [
    r"\bwhat is\b",
    r"\bwhat are\b",
    r"\bdefine\b",
    r"\bwhen did\b",
    r"\bwho is\b",
    r"\bhow much\b",
    r"\bwhat section\b",
    r"\bwhat does .{1,40} say\b",
    r"\brate of\b",
    r"\bdeadline\b",
    r"\bpenalty\b",
    r"\b§\s*\d+\b",
    r"\bu\.s\.c\.\b",
]

INTERPRETIVE_PATTERNS = [
    r"\bhow should\b",
    r"\bwhether\b",
    r"\binterpret\b",
    r"\bimplication\b",
    r"\bmeaning of\b",
    r"\bapply to\b",
    r"\banalyz\b",
    r"\bexplain\b",
    r"\bsignificance\b",
    r"\bwhy did\b",
    r"\bwhat does .{1,40} mean\b",
    r"\bimpact of\b",
    r"\beffect of\b",
]

MULTI_HOP_PATTERNS = [
    r"\bcompare\b",
    r"\bcontrast\b",
    r"\bboth .{1,40} and\b",
    r"\brelationship between\b",
    r"\bcite.*and.*also\b",
    r"\bhow does .{1,40} relate to\b",
    r"\bacross .{1,40} document",
    r"\bmultiple\b",
]

OUT_OF_SCOPE_PATTERNS = [
    r"\bweather\b",
    r"\bsports\b",
    r"\brecipe\b",
    r"\bcooking\b",
    r"\bmusic\b",
    r"\bfilm\b",
    r"\bpolitics\b(?!.*\blaw\b)",
    r"\bgame\b",
    r"\btv show\b",
]


def classify_query(query: str) -> str:
    """
    Rule-based query classifier.
    Returns one of: 'factual', 'interpretive', 'multi_hop', 'out_of_scope'
    """
    q = query.lower()

    for pat in OUT_OF_SCOPE_PATTERNS:
        if re.search(pat, q):
            return "out_of_scope"

    multi_hop_score = sum(1 for p in MULTI_HOP_PATTERNS if re.search(p, q))
    interpretive_score = sum(1 for p in INTERPRETIVE_PATTERNS if re.search(p, q))
    factual_score = sum(1 for p in FACTUAL_PATTERNS if re.search(p, q))

    if multi_hop_score >= 1:
        return "multi_hop"
    if interpretive_score > factual_score:
        return "interpretive"
    if factual_score >= 1:
        return "factual"

    # Default: if query is legal-sounding, treat as interpretive
    if any(kw in q for kw in ["tax", "act", "court", "judgment", "law", "regulation", "code", "section", "statute"]):
        return "interpretive"

    return "out_of_scope"

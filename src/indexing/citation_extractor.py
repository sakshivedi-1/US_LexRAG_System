import re
import spacy

try:
    nlp = spacy.load("en_core_web_sm")
except (OSError, ImportError):
    nlp = None

def extract_citations(text: str) -> list[str]:
    """
    Extracts legal citations deterministically using Regex and spaCy NER.
    Targets: 
      - e.g., 26 U.S.C. § X
      - Name v. Name
      - Volume Reporter Page (e.g., 554 F.3d 123)
    """
    citations = set()
    
    # 1. Regex for U.S.C. (United States Code)
    usc_pattern = r'\b(\d+)\s+U\.S\.C\.\s+(?:§\s*)?(\d+[a-z]?)\b'
    for match in re.finditer(usc_pattern, text, re.IGNORECASE):
        citations.add(f"{match.group(1)} U.S.C. § {match.group(2)}")
        
    # 2. Regex for Federal/State Reporters
    reporter_pattern = r'\b(\d+)\s+(F\.\d?d|F\. Supp\.\d?d|S\. Ct\.|U\.S\.|L\. Ed\.\d?d)\s+(\d+)\b'
    for match in re.finditer(reporter_pattern, text):
        citations.add(f"{match.group(1)} {match.group(2)} {match.group(3)}")
        
    # 3. Regex for 'Name v. Name' - capturing typical party names
    # E.g. "Smith v. Jones" or "State of NY v. Johnson"
    # We restrict to capitalized words to avoid matching regular sentences.
    v_pattern = r'([A-Z][A-Za-z\s\,\.\&\']+?)\s+v\.\s+([A-Z][A-Za-z\s\,\.\&\']+?(?:Inc\.|Corp\.|Co\.|LLC)?)'
    for match in re.finditer(v_pattern, text):
        p1 = match.group(1).strip()
        p2 = match.group(2).strip()
        
        # Simple heuristic to avoid matching too much text
        if 2 < len(p1) < 50 and 2 < len(p2) < 50:
            citations.add(f"{p1} v. {p2}")
            
    # Optionally, we could use spaCy NER to confirm ORG/PERSON around 'v.', 
    # but the regex usually suffices and is much faster for a deterministic baseline.
    if nlp is not None:
        pass # In a full system we'd parse `doc = nlp(text)` and look for entities
        
    return list(citations)

import fitz
import re
import os
import uuid

def is_boundary(text: str, doc_type: str):
    """
    Determines if a given text block represents a structural boundary.
    Returns (is_boundary: bool, section_id: str).
    """
    text = text.strip()
    if not text:
        return False, None
    
    if doc_type == 'act':
        # Match "Section 1", "SECTION 2", "1.", "Article 5"
        match = re.match(r"(?i)^(?:Section\s+\d+|Article\s+\d+|\d+\.)", text)
        if match:
            return True, match.group().strip()
            
    elif doc_type == 'judgment':
        # Match "¶ 1", "¶1", "1.", "[1]"
        match = re.match(r"^(?:¶\s*\d+|\[\d+\]|\d+\.)", text)
        if match:
            return True, match.group().strip()
            
    elif doc_type in ['pov', 'tax_doc']:
        # Match headers: short lines, mostly uppercase or title case
        lines = text.split('\n')
        first_line = lines[0].strip()
        # Ensure it's not a regular sentence and is relatively short
        if 0 < len(first_line) < 80 and not first_line.endswith('.'):
            # If it's all uppercase or Title Case (and contains letters)
            if re.search(r'[a-zA-Z]', first_line) and (first_line.isupper() or first_line.istitle()):
                return True, first_line
                
    return False, None

def parse_pdf(filepath: str, doc_type: str) -> dict:
    """
    Extracts text from a PDF, preserving page numbers, and chunks it
    based on structural boundaries specific to the doc_type.
    """
    doc = fitz.open(filepath)
    title = os.path.splitext(os.path.basename(filepath))[0]
    # We could hash the title or file contents for doc_id, but uuid is fine
    doc_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, title + doc_type))
    
    chunks = []
    current_chunk_text = ""
    current_section_id = "Introduction"
    current_page_start = 1
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        blocks = page.get_text("blocks")
        
        # Blocks are typically (x0, y0, x1, y1, text, block_no, block_type)
        # Sort blocks top-to-bottom (y0), then left-to-right (x0)
        blocks.sort(key=lambda b: (b[1], b[0]))
        
        for b in blocks:
            if b[6] == 0:  # text block
                text = b[4].strip()
                if not text:
                    continue
                    
                is_bound, sec_id = is_boundary(text, doc_type)
                
                if is_bound:
                    # Save current chunk if it has content
                    if current_chunk_text.strip():
                        chunks.append({
                            "chunk_id": str(uuid.uuid4()),
                            "page_number": current_page_start,
                            "section_id": current_section_id,
                            "text": current_chunk_text.strip()
                        })
                    
                    # Start new chunk
                    current_section_id = sec_id
                    current_chunk_text = text + "\n"
                    # We record the page where this section started
                    current_page_start = page_num + 1
                else:
                    if not current_chunk_text.strip():
                        current_page_start = page_num + 1
                    current_chunk_text += text + "\n"
                    
    # Add final chunk
    if current_chunk_text.strip():
        chunks.append({
            "chunk_id": str(uuid.uuid4()),
            "page_number": current_page_start,
            "section_id": current_section_id,
            "text": current_chunk_text.strip()
        })
        
    return {
        "doc_id": doc_id,
        "doc_type": doc_type,
        "title": title,
        "chunks": chunks
    }

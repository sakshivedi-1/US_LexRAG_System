import os
import json
import logging
from src.ingestion.parser import parse_pdf

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

RAW_DIR = "data/raw"
PROCESSED_DIR = "data/processed"

DIR_TO_DOCTYPE = {
    "Act": "act",
    "Court_Judgements": "judgment",
    "Point_of_view": "pov",
    "Tax": "tax_doc"
}

def main():
    logger.info("Starting ingestion pipeline...")
    
    # Ensure processed dir exists
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    
    total_docs = 0
    total_chunks = 0
    
    for subfolder, doc_type in DIR_TO_DOCTYPE.items():
        folder_path = os.path.join(RAW_DIR, subfolder)
        if not os.path.exists(folder_path):
            logger.warning(f"Directory not found: {folder_path}")
            continue
            
        for filename in os.listdir(folder_path):
            if filename.lower().endswith(".pdf"):
                filepath = os.path.join(folder_path, filename)
                logger.info(f"Processing {filename} as {doc_type}...")
                
                try:
                    result = parse_pdf(filepath, doc_type)
                    num_chunks = len(result["chunks"])
                    
                    # Save to processed dir
                    output_path = os.path.join(PROCESSED_DIR, f"{result['doc_id']}.json")
                    with open(output_path, "w", encoding="utf-8") as f:
                        json.dump(result, f, indent=2, ensure_ascii=False)
                        
                    logger.info(f"Successfully processed {filename}: {num_chunks} chunks extracted.")
                    total_docs += 1
                    total_chunks += num_chunks
                except Exception as e:
                    logger.error(f"Error processing {filename}: {str(e)}")
                    
    logger.info(f"Ingestion complete. Processed {total_docs} documents, generated {total_chunks} chunks.")

if __name__ == "__main__":
    main()

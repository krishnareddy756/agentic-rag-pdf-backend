"""
Initialization script - Extract PDF and populate FAISS before running backend
"""
import os
import sys
import json
import logging
import numpy as np

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.etl.pdf_parser import extract_and_parse_pdf
from src.storage.faiss_store import FAISSStore
from src.config import (
    PDF_PATH, 
    FAISS_INDEX_PATH, 
    EXTRACTED_DATA_PATH,
    EMBEDDING_MODEL_LOCAL,
    CHUNK_SIZE,
    CHUNK_OVERLAP
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_chunks(data: dict) -> list:
    """Create text chunks from extracted PDF"""
    chunks = []
    chunk_id = 0
    
    logger.info("Creating chunks from extracted PDF...")
    
    for page in data.get("pages", []):
        page_num = page["page_number"]
        text = page.get("text", "")
        
        if not text.strip():
            continue
        
        # Create overlapping chunks
        words = text.split()
        
        for i in range(0, len(words), CHUNK_SIZE - CHUNK_OVERLAP):
            chunk_words = words[i:i + CHUNK_SIZE]
            
            if chunk_words:
                chunk_content = " ".join(chunk_words)
                chunks.append({
                    "id": f"chunk_{chunk_id}",
                    "page": page_num,
                    "content": chunk_content,
                    "type": "text",
                    "word_count": len(chunk_words)
                })
                chunk_id += 1
        
        # Add table chunks
        for table_idx, table in enumerate(page.get("tables", [])):
            table_data = table.get("data", {})
            
            # Convert table to readable text
            if table_data.get("headers"):
                headers = table_data["headers"]
                rows = table_data.get("rows", [])
                
                table_text = f"Table from page {page_num}:\n"
                table_text += " | ".join(headers) + "\n"
                
                for row in rows:
                    row_values = [str(row.get(h, "")) for h in headers]
                    table_text += " | ".join(row_values) + "\n"
                
                chunks.append({
                    "id": f"chunk_{chunk_id}",
                    "page": page_num,
                    "content": table_text,
                    "type": "table",
                    "table_id": table.get("table_id")
                })
                chunk_id += 1
    
    logger.info(f"Created {len(chunks)} chunks")
    return chunks

def get_embeddings(texts: list) -> np.ndarray:
    """Get embeddings using local sentence-transformers model"""
    logger.info(f"Generating embeddings for {len(texts)} texts (local model)...")
    
    from sentence_transformers import SentenceTransformer
    
    try:
        model = SentenceTransformer(EMBEDDING_MODEL_LOCAL)
        embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)
        logger.info(f"✓ Generated {len(embeddings)} embeddings")
        return embeddings.astype(np.float32)
        
    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        raise

def main():
    """Main initialization flow"""
    logger.info("=== Starting ETL Pipeline ===")
    
    # Check if PDF exists
    if not os.path.exists(PDF_PATH):
        logger.error(f"PDF not found at {PDF_PATH}")
        return False
    
    # Step 1: Extract PDF
    logger.info(f"Step 1: Extracting PDF from {PDF_PATH}")
    extracted_data = extract_and_parse_pdf(PDF_PATH, EXTRACTED_DATA_PATH)
    logger.info(f"✓ Extracted {extracted_data['total_pages']} pages")
    
    # Step 2: Create chunks
    logger.info("Step 2: Creating text chunks...")
    chunks = create_chunks(extracted_data)
    logger.info(f"✓ Created {len(chunks)} chunks")
    
    # Step 3: Generate embeddings
    logger.info("Step 3: Generating embeddings...")
    chunk_texts = [c["content"] for c in chunks]
    embeddings = get_embeddings(chunk_texts)
    logger.info(f"✓ Generated {len(embeddings)} embeddings")
    
    # Step 4: Store in FAISS
    logger.info("Step 4: Storing in FAISS...")
    faiss_store = FAISSStore(FAISS_INDEX_PATH, embedding_dim=384)  # all-MiniLM-L6-v2 is 384-dim
    faiss_store.create_index()
    faiss_store.add_embeddings(embeddings, chunks)
    faiss_store.save()
    logger.info("✓ FAISS index created and saved")
    
    logger.info("=== ETL Pipeline Complete ===\n")
    
    return True

if __name__ == "__main__":
    success = main()
    if success:
        logger.info("System is ready. Run: python -m src.backend.main")
    else:
        logger.error("ETL pipeline failed!")
        sys.exit(1)

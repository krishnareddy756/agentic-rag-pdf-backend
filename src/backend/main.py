"""
FastAPI Backend Application
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import json
import os
import logging
from datetime import datetime
from pathlib import Path

from src.etl.pdf_parser import extract_and_parse_pdf
from src.storage.faiss_store import FAISSStore
from src.backend.agent.graph import CyberIrelandAgent
from src.backend.agent.tools import DocumentRetriever, TableAnalyzer
from src.config import PDF_PATH, FAISS_INDEX_PATH, EXTRACTED_DATA_PATH, EMBEDDING_MODEL_LOCAL
import numpy as np

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Cyber Ireland RAG Agent", version="1.0.0")

# Global state
agent = None
retriever = None

class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    query: str
    answer: str
    thought_process: list
    facts_cited: list
    timestamp: str

@app.on_event("startup")
async def startup_event():
    """Initialize system on startup"""
    global agent, retriever
    
    logger.info("Initializing system...")
    
    # Check if FAISS index exists
    if not os.path.exists(os.path.join(FAISS_INDEX_PATH, "index.faiss")):
        logger.info("FAISS index not found. Running ETL pipeline...")
        await _run_etl_pipeline()
    
    # Load FAISS store
    faiss_store = FAISSStore(FAISS_INDEX_PATH)
    faiss_store.load()
    
    # Initialize retriever and analyzer
    retriever = DocumentRetriever(faiss_store, EXTRACTED_DATA_PATH)
    analyzer = TableAnalyzer(EXTRACTED_DATA_PATH)
    
    # Initialize agent
    agent = CyberIrelandAgent(retriever, analyzer)
    
    logger.info("System ready!")

async def _run_etl_pipeline():
    """Extract PDF and populate FAISS"""
    logger.info(f"Extracting PDF from {PDF_PATH}")
    
    # Extract PDF
    data = extract_and_parse_pdf(PDF_PATH, EXTRACTED_DATA_PATH)
    
    logger.info(f"Extracted {data['total_pages']} pages")
    
    # Create chunks and embeddings
    chunks = _create_chunks_from_pdf(data)
    logger.info(f"Created {len(chunks)} chunks")
    
    # Get embeddings
    embeddings = _get_embeddings([c["content"] for c in chunks])
    
    # Store in FAISS
    faiss_store = FAISSStore(FAISS_INDEX_PATH)
    faiss_store.create_index()
    faiss_store.add_embeddings(embeddings, chunks)
    faiss_store.save()
    
    logger.info("ETL pipeline complete")

def _create_chunks_from_pdf(data: dict, chunk_size: int = 512, overlap: int = 100) -> list:
    """Create text chunks from extracted PDF"""
    chunks = []
    chunk_id = 0
    
    for page in data.get("pages", []):
        page_num = page["page_number"]
        text = page["text"]
        
        # Create chunks from page text
        words = text.split()
        current_chunk = []
        
        for word in words:
            current_chunk.append(word)
            
            if len(" ".join(current_chunk).split()) >= chunk_size:
                chunk_text = " ".join(current_chunk)
                chunks.append({
                    "id": f"chunk_{chunk_id}",
                    "page_number": page_num,
                    "content": chunk_text,
                    "type": "text"
                })
                chunk_id += 1
                
                # Overlap
                current_chunk = current_chunk[-overlap//10:]
        
        # Add remaining text
        if current_chunk and " ".join(current_chunk).strip():
            chunks.append({
                "id": f"chunk_{chunk_id}",
                "page_number": page_num,
                "content": " ".join(current_chunk),
                "type": "text"
            })
            chunk_id += 1
        
        # Add table chunks
        for table in page.get("tables", []):
            table_text = json.dumps(table.get("data"), ensure_ascii=False)
            chunks.append({
                "id": f"chunk_{chunk_id}",
                "page_number": page_num,
                "content": f"Table: {table_text}",
                "type": "table",
                "table_id": table.get("table_id")
            })
            chunk_id += 1
    
    return chunks

def _get_embeddings(texts: list) -> np.ndarray:
    """Get embeddings from local sentence-transformers model"""
    logger.info(f"Generating embeddings for {len(texts)} texts...")
    
    from sentence_transformers import SentenceTransformer
    
    model = SentenceTransformer(EMBEDDING_MODEL_LOCAL)
    embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)
    
    return embeddings.astype(np.float32)

@app.post("/chat", response_model=QueryResponse)
async def chat(request: QueryRequest):
    """Main query endpoint"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    try:
        logger.info(f"Processing query: {request.query}")
        
        # Run agent
        result = await agent.query(request.query)
        
        response = QueryResponse(
            query=request.query,
            answer=result["answer"],
            thought_process=result["thought_process"],
            facts_cited=result["facts_cited"],
            timestamp=datetime.now().isoformat()
        )
        
        # Save logs
        os.makedirs("logs", exist_ok=True)
        agent.save_logs("logs/agent_logs.json")
        
        return response
        
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "ok",
        "agent_initialized": agent is not None
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Cyber Ireland RAG Agent",
        "endpoints": ["/chat", "/health"],
        "version": "1.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

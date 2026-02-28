"""Test script for the three evaluation queries"""
import asyncio
import json
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.backend.agent.graph import CyberIrelandAgent
from src.backend.agent.tools import DocumentRetriever, TableAnalyzer
from src.storage.faiss_store import FAISSStore
from src.config import FAISS_INDEX_PATH, EXTRACTED_DATA_PATH

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test queries from the assignment
TEST_QUERIES = [
    {
        "name": "Test 1: The Verification Challenge",
        "query": "What is the total number of jobs reported, and where exactly is this stated?",
        "expected": "Should find exact job count with page number and citation"
    },
    {
        "name": "Test 2: The Data Synthesis Challenge",
        "query": "Compare the concentration of 'Pure-Play' cybersecurity firms in the South-West against the National Average.",
        "expected": "Should compare regional vs national concentration with specific percentages"
    },
    {
        "name": "Test 3: The Forecasting Challenge",
        "query": "Based on our 2022 baseline and the stated 2030 job target, what is the required compound annual growth rate (CAGR) to hit that goal?",
        "expected": "Should calculate CAGR with formula and result"
    }
]

async def run_tests():
    """Run all three test queries"""
    
    logger.info("Loading FAISS index...")
    faiss_store = FAISSStore(FAISS_INDEX_PATH)
    if not faiss_store.load():
        logger.error("FAISS index not found! Run: python run_etl.py")
        return False
    
    logger.info("Initializing retriever and analyzer...")
    retriever = DocumentRetriever(faiss_store, EXTRACTED_DATA_PATH)
    analyzer = TableAnalyzer(EXTRACTED_DATA_PATH)
    
    logger.info("Creating agent...")
    agent = CyberIrelandAgent(retriever, analyzer)
    
    results = []
    
    for test in TEST_QUERIES:
        logger.info(f"\n{'='*70}")
        logger.info(f"Running: {test['name']}")
        logger.info(f"Query: {test['query']}")
        logger.info(f"{'='*70}\n")
        
        try:
            result = await agent.query(test['query'])
            
            test_result = {
                "test_name": test["name"],
                "query": test['query'],
                "expected": test['expected'],
                "answer": result["answer"],
                "thought_process": result["thought_process"],
                "facts_cited": result["facts_cited"],
                "status": "completed"
            }
            
            logger.info(f"Answer:\n{result['answer']}\n")
            logger.info(f"Facts cited: {result['facts_cited']}\n")
            
            results.append(test_result)
            
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            results.append({
                "test_name": test["name"],
                "query": test['query'],
                "error": str(e),
                "status": "failed"
            })
    
    # Save results
    os.makedirs("logs", exist_ok=True)
    with open("logs/test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    logger.info(f"\n{'='*70}")
    logger.info("Test execution complete. Results saved to logs/test_results.json")
    logger.info(f"{'='*70}")
    
    return True

if __name__ == "__main__":
    success = asyncio.run(run_tests())
    sys.exit(0 if success else 1)

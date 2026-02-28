"""
Agent Tools for LangGraph
Provides tools for retrieval, table lookup, and calculations
"""
import json
import os
from typing import Any, Dict, List, Optional
import numpy as np
from src.storage.faiss_store import FAISSStore
from src.config import EMBEDDING_MODEL_LOCAL


class DocumentRetriever:
    """Retrieve relevant document chunks"""
    
    def __init__(self, faiss_store: FAISSStore, extracted_data_path: str):
        self.faiss_store = faiss_store
        self.extracted_data_path = extracted_data_path
        self.extracted_data = self._load_extracted_data()
    
    def _load_extracted_data(self) -> Dict:
        """Load the extracted PDF data"""
        if os.path.exists(self.extracted_data_path):
            with open(self.extracted_data_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"pages": []}
    
    def retrieve(self, query: str, k: int = 5) -> List[Dict]:
        """Retrieve relevant chunks for a query"""
        from sentence_transformers import SentenceTransformer
        
        # Get embedding for query using local model
        model = SentenceTransformer(EMBEDDING_MODEL_LOCAL)
        query_embedding = model.encode(query, convert_to_numpy=True)
        
        # Search in FAISS
        results, _ = self.faiss_store.search(np.array(query_embedding), k=k)
        
        return results
    
    def get_page_content(self, page_num: int) -> Dict:
        """Get full content of a specific page"""
        for page in self.extracted_data.get("pages", []):
            if page["page_number"] == page_num:
                return page
        return {}


class TableAnalyzer:
    """Analyze and compare data in tables"""
    
    def __init__(self, extracted_data_path: str):
        self.extracted_data_path = extracted_data_path
        self.extracted_data = self._load_extracted_data()
    
    def _load_extracted_data(self) -> Dict:
        """Load the extracted PDF data"""
        if os.path.exists(self.extracted_data_path):
            with open(self.extracted_data_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"pages": []}
    
    def find_table_with_column(self, column_name: str, search_term: str = None) -> List[Dict]:
        """Find tables containing a specific column"""
        matching_tables = []
        
        for page in self.extracted_data.get("pages", []):
            for table in page.get("tables", []):
                headers = table.get("data", {}).get("headers", [])
                
                if any(column_name.lower() in h.lower() for h in headers):
                    matching_tables.append({
                        "page_number": page["page_number"],
                        "table_id": table.get("table_id"),
                        "table": table.get("data")
                    })
        
        return matching_tables
    
    def extract_numeric_value(self, text: str) -> Optional[float]:
        """Extract numeric values from text"""
        import re
        numbers = re.findall(r"[\d,]+\.?\d*", text)
        if numbers:
            try:
                return float(numbers[0].replace(",", ""))
            except:
                pass
        return None


class Calculator:
    """Perform calculations based on data"""
    
    @staticmethod
    def calculate_cagr(starting_value: float, ending_value: float, periods: int) -> float:
        """
        Calculate Compound Annual Growth Rate
        CAGR = (Ending Value / Starting Value)^(1/n) - 1
        where n is number of years
        """
        if starting_value <= 0 or periods <= 0:
            return None
        
        cagr = (ending_value / starting_value) ** (1 / periods) - 1
        return round(cagr * 100, 2)  # Return as percentage
    
    @staticmethod
    def calculate_percentage_difference(value1: float, value2: float) -> float:
        """Calculate percentage difference"""
        if value1 == 0:
            return None
        return round(((value2 - value1) / value1) * 100, 2)
    
    @staticmethod
    def calculate_concentration(subset_value: float, total_value: float) -> float:
        """Calculate concentration percentage"""
        if total_value == 0:
            return None
        return round((subset_value / total_value) * 100, 2)


# Tool definitions for LangGraph
def retrieve_documents(query: str, retriever: DocumentRetriever, k: int = 5) -> List[Dict]:
    """Tool: Retrieve relevant document chunks"""
    return retriever.retrieve(query, k=k)


def find_relevant_tables(column_name: str, analyzer: TableAnalyzer) -> List[Dict]:
    """Tool: Find tables with specific columns"""
    return analyzer.find_table_with_column(column_name)


def perform_calculation(operation: str, values: List[float], **kwargs) -> Dict:
    """Tool: Perform calculations like CAGR, percentages"""
    calculator = Calculator()
    
    result = None
    if operation == "cagr":
        result = calculator.calculate_cagr(values[0], values[1], int(kwargs.get("periods", 1)))
    elif operation == "percentage_diff":
        result = calculator.calculate_percentage_difference(values[0], values[1])
    elif operation == "concentration":
        result = calculator.calculate_concentration(values[0], values[1])
    
    return {"operation": operation, "result": result}


def get_page_content(page_num: int, retriever: DocumentRetriever) -> Dict:
    """Tool: Get full page content"""
    return retriever.get_page_content(page_num)

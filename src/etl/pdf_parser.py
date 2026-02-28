"""
PDF Extraction and Parsing - ETL Pipeline
Handles extraction of text and tables from PDF with precise page tracking
"""
import pdfplumber
import json
import os
from typing import List, Dict, Any, Tuple
import re

class PDFExtractor:
    """Extract and parse the Cyber Ireland PDF"""
    
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.pages_data = []
        self.tables_extracted = []
        
    def extract(self) -> Dict[str, Any]:
        """Extract all content from PDF with page tracking"""
        with pdfplumber.open(self.pdf_path) as pdf:
            print(f"PDF loaded. Total pages: {len(pdf.pages)}")
            
            for page_num, page in enumerate(pdf.pages, 1):
                page_content = self._extract_page(page, page_num)
                self.pages_data.append(page_content)
        
        return {
            "total_pages": len(self.pages_data),
            "pages": self.pages_data,
            "tables": self.tables_extracted
        }
    
    def _extract_page(self, page, page_num: int) -> Dict[str, Any]:
        """Extract text and tables from a single page"""
        page_data = {
            "page_number": page_num,
            "text": page.extract_text() or "",
            "tables": [],
        }
        
        # Extract tables - handle both old and new pdfplumber API
        try:
            # Try new API (pdfplumber >= 0.10)
            tables = page.find_tables()
            if tables:
                for table_idx, table_obj in enumerate(tables):
                    table_data = table_obj.extract()
                    table_dict = self._convert_table_to_dict(table_data)
                    table_item = {
                        "table_id": f"p{page_num}_t{table_idx}",
                        "page": page_num,
                        "data": table_dict,
                        "raw_data": table_data
                    }
                    page_data["tables"].append(table_item)
                    self.tables_extracted.append(table_item)
        except (AttributeError, TypeError):
            # Fallback to old API (pdfplumber < 0.10)
            try:
                if hasattr(page, 'tables') and page.tables:
                    for table_idx, table_data in enumerate(page.tables):
                        table_dict = self._convert_table_to_dict(table_data)
                        table_obj = {
                            "table_id": f"p{page_num}_t{table_idx}",
                            "page": page_num,
                            "data": table_dict,
                            "raw_data": table_data
                        }
                        page_data["tables"].append(table_obj)
                        self.tables_extracted.append(table_obj)
            except:
                pass  # Table extraction not available, continue with text only
        
        return page_data
    
    def _convert_table_to_dict(self, table_data: List[List[str]]) -> Dict[str, List[Dict]]:
        """Convert table data to structured format"""
        if not table_data or len(table_data) < 2:
            return {}
        
        headers = table_data[0]
        rows = []
        
        for row in table_data[1:]:
            row_dict = {}
            for idx, header in enumerate(headers):
                if idx < len(row):
                    row_dict[header.strip()] = row[idx].strip() if row[idx] else ""
            rows.append(row_dict)
        
        return {"headers": headers, "rows": rows}
    
    def save_extracted_data(self, output_path: str):
        """Save extracted data to JSON"""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Serialize for JSON (remove raw_data)
        serializable_data = {
            "total_pages": len(self.pages_data),
            "pages": []
        }
        
        for page in self.pages_data:
            page_copy = page.copy()
            page_copy["tables"] = [
                {k: v for k, v in t.items() if k != "raw_data"}
                for t in page_copy["tables"]
            ]
            serializable_data["pages"].append(page_copy)
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(serializable_data, f, indent=2, ensure_ascii=False)
        
        print(f"Extracted data saved to {output_path}")


def extract_and_parse_pdf(pdf_path: str, output_path: str) -> Dict[str, Any]:
    """Main ETL function"""
    extractor = PDFExtractor(pdf_path)
    data = extractor.extract()
    extractor.save_extracted_data(output_path)
    return data

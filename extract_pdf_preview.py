"""
PDF extraction and analysis script to understand document structure
"""
import pdfplumber
import json
import os

def extract_pdf_content():
    pdf_path = "State-of-the-Cyber-Security-Sector-in-Ireland-2022-Report.pdf"
    
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found at {pdf_path}")
    
    all_content = []
    
    with pdfplumber.open(pdf_path) as pdf:
        print(f"Total pages: {len(pdf.pages)}\n")
        
        for page_num, page in enumerate(pdf.pages, 1):
            page_data = {
                "page_number": page_num,
                "text": page.extract_text(),
                "tables": []
            }
            
            # Extract tables if they exist
            if page.tables:
                for table_idx, table in enumerate(page.tables):
                    page_data["tables"].append({
                        "table_id": f"page_{page_num}_table_{table_idx}",
                        "data": table
                    })
            
            all_content.append(page_data)
            
            # Print first 500 chars of page text to understand structure
            if page_num <= 3:
                print(f"=== PAGE {page_num} ===")
                print(page_data["text"][:500])
                if page_data["tables"]:
                    print(f"Found {len(page_data['tables'])} table(s)")
                print()
    
    return all_content

if __name__ == "__main__":
    try:
        content = extract_pdf_content()
        print("\nPDF extraction complete!")
        
        # Save to JSON for inspection
        with open("pdf_extracted.json", "w") as f:
            json.dump([{**item, "text": item["text"][:200]} for item in content], f, indent=2)
            
    except Exception as e:
        print(f"Error: {e}")

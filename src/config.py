"""
Configuration and constants
"""
import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Paths
PDF_PATH = "State-of-the-Cyber-Security-Sector-in-Ireland-2022-Report.pdf"
FAISS_INDEX_PATH = "storage/faiss_index"
EXTRACTED_DATA_PATH = "storage/extracted_data.json"

# Model settings
MODEL = "gpt-3.5-turbo"
EMBEDDING_MODEL = "text-embedding-3-small"
TEMPERATURE = 0.7

# Vector DB settings
CHUNK_SIZE = 512
CHUNK_OVERLAP = 100
EMBEDDING_MODEL_LOCAL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 dimension (local model)

# Agent settings
MAX_ITERATIONS = 10
TIMEOUT = 60

"""Configuration for vector store service."""

import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Embedding model
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    
    # ChromaDB HTTP host
    chroma_host: str = os.getenv("CHROMA_HOST", "chromadb")
    chroma_port: int = int(os.getenv("CHROMA_PORT", 8000))
    
    # Collection name
    collection_name: str = os.getenv("COLLECTION_NAME", "carbon_documents")
    
    # Chunking settings (if needed)
    chunk_size: int = 1000
    chunk_overlap: int = 200
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
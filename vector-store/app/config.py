"""Configuration for vector store service."""

import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Embedding model
    # fastembed model name (ONNX, no PyTorch required)
    # Default: BAAI/bge-small-en-v1.5  ~90MB model, excellent quality/speed
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    
    # ChromaDB HTTP host
    chroma_host: str = os.getenv("CHROMA_HOST", "chromadb")
    chroma_port: int = int(os.getenv("CHROMA_PORT", 8000))
    chroma_tenant: str = os.getenv("CHROMA_TENANT", "default_tenant")
    chroma_database: str = os.getenv("CHROMA_DATABASE", "default_database")
    
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

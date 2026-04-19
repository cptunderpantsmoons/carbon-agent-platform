"""Vector database management using ChromaDB HTTP client."""

import os
from typing import List, Dict, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer
from app.config import settings


class VectorStore:
    """Manages the ChromaDB vector store for documents."""

    def __init__(self):
        """Initialize ChromaDB HTTP client and embedding model."""
        # Initialize ChromaDB HTTP client
        self.client = chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
            ssl=False,
        )

        # Initialize embedding model
        print(f"Loading embedding model: {settings.embedding_model}")
        self.embedding_model = SentenceTransformer(settings.embedding_model)
        print("Embedding model loaded.")

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=settings.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def _generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts."""
        embeddings = self.embedding_model.encode(texts, show_progress_bar=False)
        return embeddings.tolist()

    def add_documents(
        self,
        documents: List[str],
        metadatas: List[Dict],
        ids: Optional[List[str]] = None,
        batch_size: int = 500,
    ) -> int:
        """Add documents to the vector store in batches."""
        if not documents:
            return 0
        
        # Generate IDs if not provided
        if ids is None:
            import uuid
            ids = [str(uuid.uuid4()) for _ in range(len(documents))]
        
        # Check for existing IDs in the collection
        existing_ids = set(self.collection.get()["ids"]) if self.collection.count() > 0 else set()
        
        # Filter out existing IDs
        unique_docs = []
        unique_metadatas = []
        unique_ids = []
        
        for doc, meta, doc_id in zip(documents, metadatas, ids):
            if doc_id not in existing_ids:
                unique_docs.append(doc)
                unique_metadatas.append(meta)
                unique_ids.append(doc_id)
        
        if not unique_docs:
            print("No new documents to add (all already exist).")
            return 0
        
        total = len(unique_docs)
        print(f"Generating embeddings for {total} unique documents in batches of {batch_size}...")
        
        added_count = 0
        for i in range(0, total, batch_size):
            batch_end = min(i + batch_size, total)
            batch_texts = unique_docs[i:batch_end]
            batch_ids = unique_ids[i:batch_end]
            batch_metadatas = unique_metadatas[i:batch_end]
            
            print(f"  Batch {i//batch_size + 1}: embedding {len(batch_texts)} documents...")
            embeddings = self._generate_embeddings(batch_texts)
            
            self.collection.add(
                ids=batch_ids,
                documents=batch_texts,
                embeddings=embeddings,
                metadatas=batch_metadatas,
            )
            added_count += len(batch_texts)
            print(f"  -> Added {added_count}/{total} total")
        
        print(f"Done. Added {added_count} documents to vector store.")
        return added_count

    def search(
        self,
        query: str,
        n_results: int = 10,
        where_filter: Optional[Dict] = None,
    ) -> Dict:
        """Search the vector store for relevant documents."""
        query_embedding = self.embedding_model.encode([query]).tolist()
        
        search_params = {
            "query_embeddings": query_embedding,
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        
        if where_filter:
            search_params["where"] = where_filter
        
        results = self.collection.query(**search_params)
        
        # Format results for API
        formatted_results = []
        if results and results.get("documents") and results["documents"][0]:
            for i, (doc, metadata, distance) in enumerate(zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            )):
                relevance_score = max(0, 100 - (distance * 100))
                formatted_results.append({
                    "rank": i + 1,
                    "text": doc[:500] + "..." if len(doc) > 500 else doc,
                    "full_text": doc,
                    "metadata": metadata,
                    "relevance_score": round(relevance_score, 1),
                    "distance": float(distance),
                })
        
        return {
            "query": query,
            "results": formatted_results,
            "total_found": len(formatted_results),
        }

    def get_stats(self) -> Dict:
        """Get vector store statistics."""
        count = self.collection.count()
        return {
            "total_documents": count,
            "collection_name": settings.collection_name,
            "embedding_model": settings.embedding_model,
        }

    def clear(self):
        """Clear all documents from the vector store."""
        self.client.delete_collection(name=settings.collection_name)
        self.collection = self.client.create_collection(
            name=settings.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        print("Vector store cleared.")
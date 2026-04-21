"""Vector database management using ChromaDB HTTP client."""

from typing import List, Dict, Optional
import chromadb
from fastembed import TextEmbedding
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
            tenant=settings.chroma_tenant,
            database=settings.chroma_database,
        )

        # Initialize embedding model (fastembed / ONNX — no PyTorch required)
        print(f"Loading embedding model: {settings.embedding_model}")
        self.embedding_model = TextEmbedding(settings.embedding_model)
        print("Embedding model loaded.")

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=settings.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def _generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts using fastembed (ONNX)."""
        # fastembed returns a generator of numpy arrays; convert to list of lists.
        return [emb.tolist() for emb in self.embedding_model.embed(texts)]

    def _normalize_where_filter(self, where_filter: Optional[Dict]) -> Optional[Dict]:
        """Normalize a metadata filter before sending it to Chroma."""
        if not where_filter or any(key.startswith("$") for key in where_filter):
            return where_filter

        document_id = where_filter.get("document_id")
        if document_id is None:
            return where_filter

        clauses = [
            {key: value} for key, value in where_filter.items() if key != "document_id"
        ]
        clauses.append(
            {
                "$or": [
                    {"document_id": document_id},
                    {"doc_id": document_id},
                ]
            }
        )

        if len(clauses) == 1:
            return clauses[0]

        return {"$and": clauses}

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
        existing_ids = (
            set(self.collection.get()["ids"]) if self.collection.count() > 0 else set()
        )

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
        print(
            f"Generating embeddings for {total} unique documents in batches of {batch_size}..."
        )

        added_count = 0
        for i in range(0, total, batch_size):
            batch_end = min(i + batch_size, total)
            batch_texts = unique_docs[i:batch_end]
            batch_ids = unique_ids[i:batch_end]
            batch_metadatas = unique_metadatas[i:batch_end]

            print(
                f"  Batch {i // batch_size + 1}: embedding {len(batch_texts)} documents..."
            )
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
        query_embedding = [emb.tolist() for emb in self.embedding_model.embed([query])][0]
        chroma_where_filter = self._normalize_where_filter(where_filter)

        search_params = {
            "query_embeddings": query_embedding,
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }

        if chroma_where_filter:
            search_params["where"] = chroma_where_filter

        results = self.collection.query(**search_params)

        # Format results for API
        formatted_results = []
        if results and results.get("documents") and results["documents"][0]:
            for i, (doc, metadata, distance) in enumerate(
                zip(
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0],
                )
            ):
                relevance_score = max(0, 100 - (distance * 100))
                formatted_results.append(
                    {
                        "rank": i + 1,
                        "text": doc[:500] + "..." if len(doc) > 500 else doc,
                        "full_text": doc,
                        "metadata": metadata,
                        "relevance_score": round(relevance_score, 1),
                        "distance": float(distance),
                    }
                )

        return {
            "query": query,
            "results": formatted_results,
            "total_found": len(formatted_results),
        }

    def get_stats(self, where_filter: Optional[Dict] = None) -> Dict:
        """Get vector store statistics."""
        count = self.collection.count()
        if where_filter:
            results = self.collection.get(
                where=self._normalize_where_filter(where_filter),
                include=[],
            )
            count = len(results.get("ids", []))

        return {
            "total_documents": count,
            "collection_name": settings.collection_name,
            "embedding_model": settings.embedding_model,
        }

    def delete_documents(self, where_filter: Dict) -> int:
        """Delete documents only within the supplied metadata scope."""
        if not where_filter:
            raise ValueError("where_filter is required for scoped deletes")

        normalized_where_filter = self._normalize_where_filter(where_filter)
        matches = self.collection.get(where=normalized_where_filter, include=[])
        matching_ids = matches.get("ids", [])
        if not matching_ids:
            return 0

        self.collection.delete(where=normalized_where_filter)
        return len(matching_ids)

    def clear(self):
        """Clear all documents from the vector store."""
        self.client.delete_collection(name=settings.collection_name)
        self.collection = self.client.create_collection(
            name=settings.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        print("Vector store cleared.")

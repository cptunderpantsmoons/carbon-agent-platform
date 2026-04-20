"""Vector store API service."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict
import structlog

from app.vector_store import VectorStore
from app.config import settings

logger = structlog.get_logger()
app = FastAPI(title="Carbon Agent Vector Store", version="1.0.0")

# Initialize vector store
store = VectorStore()


class Document(BaseModel):
    text: str
    metadata: Dict = {}


class AddDocumentsRequest(BaseModel):
    documents: List[Document]
    ids: Optional[List[str]] = None
    batch_size: int = 500


class SearchRequest(BaseModel):
    query: str
    n_results: int = 10
    where_filter: Optional[Dict] = None


class ScopedStatsRequest(BaseModel):
    where_filter: Optional[Dict] = None


class DeleteRequest(BaseModel):
    where_filter: Dict


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "vector-store"}


@app.get("/stats")
async def stats():
    """Get vector store statistics."""
    return store.get_stats()


@app.post("/stats")
async def scoped_stats(request: ScopedStatsRequest):
    """Get scoped vector store statistics."""
    try:
        return store.get_stats(where_filter=request.where_filter)
    except Exception as e:
        logger.error("scoped_stats_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/add")
async def add_documents(request: AddDocumentsRequest):
    """Add documents to the vector store."""
    try:
        texts = [doc.text for doc in request.documents]
        metadatas = [doc.metadata for doc in request.documents]
        added = store.add_documents(
            documents=texts,
            metadatas=metadatas,
            ids=request.ids,
            batch_size=request.batch_size,
        )
        return {"added": added, "total_submitted": len(texts)}
    except Exception as e:
        logger.error("add_documents_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search")
async def search(request: SearchRequest):
    """Search the vector store."""
    try:
        results = store.search(
            query=request.query,
            n_results=request.n_results,
            where_filter=request.where_filter,
        )
        return results
    except Exception as e:
        logger.error("search_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/delete")
async def delete_documents(request: DeleteRequest):
    """Delete only documents matching the provided metadata filter."""
    try:
        deleted = store.delete_documents(where_filter=request.where_filter)
        return {"deleted": deleted}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("delete_documents_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/clear")
async def clear():
    """Clear all documents from the vector store."""
    try:
        store.clear()
        return {"message": "Vector store cleared."}
    except Exception as e:
        logger.error("clear_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)

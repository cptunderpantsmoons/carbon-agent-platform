import sys

with open('rag.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the line where delete endpoint starts
delete_idx = None
for i, line in enumerate(lines):
    if line.strip().startswith('@rag_router.delete'):
        delete_idx = i
        break

if delete_idx is None:
    print("Could not find delete endpoint")
    sys.exit(1)

# Insert new endpoint before delete
new_endpoint = '''@rag_router.post("/ingest")
@limiter.limit("60/minute", key_func=_get_clerk_rag_rate_limit_key)
async def ingest_rag(
    request: Request,
    payload: dict[str, Any],
    principal: ClerkPrincipal = Depends(verify_clerk_principal),
) -> dict[str, Any]:
    """Ingest documents into the vector store with Clerk scoping."""
    _ensure_active_principal(principal)

    documents = payload.get("documents", [])
    if not documents:
        raise HTTPException(status_code=400, detail="Missing documents")

    # Merge scope into each document's metadata
    scope = build_scoped_rag_request({}, principal)["scope"]
    metadatas = []
    texts = []
    ids = []
    for doc in documents:
        if not isinstance(doc, dict):
            raise HTTPException(status_code=400, detail="Each document must be a dict")
        text = doc.get("text")
        if not text:
            raise HTTPException(status_code=400, detail="Missing text in document")
        metadata = doc.get("metadata", {})
        # Merge scope
        metadata.update(scope)
        # Add document_id if present in doc
        if "document_id" in doc:
            metadata["document_id"] = doc["document_id"]
        metadatas.append(metadata)
        texts.append(text)
        # Generate ID if not provided
        ids.append(doc.get("id", str(uuid.uuid4())))

    upstream_payload = {
        "documents": [{"text": text, "metadata": metadata} for text, metadata in zip(texts, metadatas)],
        "ids": ids,
        "batch_size": payload.get("batch_size", 500),
    }

    scoped_request = build_scoped_rag_request(payload, principal)
    return await _proxy_scoped_vector_store_request(
        path="/add",
        operation_name="add",
        scoped_request=scoped_request,
        upstream_payload=upstream_payload,
    )

'''

# Insert with a blank line before delete
lines.insert(delete_idx, '\n' + new_endpoint)

with open('rag.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Ingest endpoint added successfully.")
import re

with open('rag.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Replace the _get_fixed_tenant_id and build_scoped_rag_request block
old_block = '''def _get_fixed_tenant_id() -> str:
    """Return the tenant id used to scope all RAG requests."""
    tenant_id = get_settings().rag_fixed_tenant_id.strip()
    if not tenant_id:
        raise HTTPException(status_code=500, detail="RAG tenant id is not configured")
    return tenant_id


def build_scoped_rag_request(
    payload: dict[str, Any],
    principal: ClerkPrincipal,
) -> dict[str, Any]:
    """Attach the fixed tenant id and Clerk subject to a RAG payload."""
    return {
        "scope": {
            "tenant_id": _get_fixed_tenant_id(),
            "clerk_user_id": principal["clerk_user_id"],
        },
        "payload": payload,
    }'''

new_block = '''def _get_fixed_tenant_id() -> str:
    """Return the tenant id used to scope all RAG requests."""
    tenant_id = get_settings().rag_fixed_tenant_id.strip()
    if not tenant_id:
        raise HTTPException(status_code=500, detail="RAG tenant id is not configured")
    return tenant_id


def _get_tenant_id_from_request(request: Request) -> str:
    """Extract tenant id from X-Tenant-Id header or fallback to fixed."""
    tenant_id = request.headers.get("X-Tenant-Id", "").strip()
    if tenant_id:
        return tenant_id
    return _get_fixed_tenant_id()


def build_scoped_rag_request(
    payload: dict[str, Any],
    principal: ClerkPrincipal,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Attach the tenant id and Clerk subject to a RAG payload."""
    if tenant_id is None:
        tenant_id = _get_fixed_tenant_id()
    return {
        "scope": {
            "tenant_id": tenant_id,
            "clerk_user_id": principal["clerk_user_id"],
        },
        "payload": payload,
    }'''

if old_block not in content:
    print("Old block not found exactly; maybe the file already changed?")
    # Try a more flexible replacement
    # We'll do regex replace for each function separately
    # Replace _get_fixed_tenant_id (keep same)
    # Replace build_scoped_rag_request
    pattern = r'def build_scoped_rag_request\\([^)]+\\)[^:]+:"[^"]*"[^}]+}'
    # But let's just abort and do manual
    exit(1)

content = content.replace(old_block, new_block)

# 2. Update query_rag endpoint to use tenant id from request
# Find the function and insert tenant_id extraction
# We'll replace the line "scoped_request = build_scoped_rag_request(payload, principal)"
# with "tenant_id = _get_tenant_id_from_request(request)"
#          "scoped_request = build_scoped_rag_request(payload, principal, tenant_id)"
# Use regex to replace within the function
query_func_pattern = r'(@rag_router.post\("/query"\)[\\s\\S]+?async def query_rag\\([^)]+\\)[\\s\\S]+?)_ensure_active_principal\\(principal\\)[\\s\\S]+?scoped_request = build_scoped_rag_request\\(payload, principal\\)'
# This is complex; let's do a simpler line-by-line replacement after we have the new block.
# We'll instead process line by line.

print("Block replaced. Now updating endpoint functions...")

# Let's split lines and iterate
lines = content.splitlines(keepends=True)
new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    new_lines.append(line)
    # Look for query_rag function signature
    if line.strip().startswith('async def query_rag'):
        # Find the line with _ensure_active_principal
        j = i + 1
        while j < len(lines) and '_ensure_active_principal(principal)' not in lines[j]:
            j += 1
        if j < len(lines):
            # Insert tenant_id extraction after that line
            new_lines.extend(lines[i+1:j+1])  # include the _ensure line
            new_lines.append('    tenant_id = _get_tenant_id_from_request(request)\n')
            i = j
            continue
    i += 1

# This is getting messy. Let's just write the whole file with a full replacement.
# Instead, we'll create a new version from scratch? Too much.
# Let's output the current content and manually edit later.
print("Writing updated file...")
with open('rag.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done. Please manually update endpoint functions to use tenant_id.")
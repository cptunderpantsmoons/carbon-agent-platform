import re

with open('rag.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update query_rag
query_pattern = r'(@rag_router.post\("/query"\)[\s\S]+?async def query_rag\([^)]+\)[\s\S]+?_ensure_active_principal\(principal\)\s*\n\s*)(scoped_request = build_scoped_rag_request\(payload, principal\)\s*\n\s*return await proxy_rag_request\(scoped_request\))'
def replace_query(match):
    before = match.group(1)
    after = match.group(2)
    new_after = '''    tenant_id = _get_tenant_id_from_request(request)
    scoped_request = build_scoped_rag_request(payload, principal, tenant_id)
    return await proxy_rag_request(scoped_request)'''
    return before + new_after
content = re.sub(query_pattern, replace_query, content)

# 2. Update ingest_rag
# Need to replace two occurrences: scope = build_scoped_rag_request({}, principal)["scope"]
# and scoped_request = build_scoped_rag_request(payload, principal)
ingest_pattern = r'(@rag_router.post\("/ingest"\)[\s\S]+?async def ingest_rag\([^)]+\)[\s\S]+?_ensure_active_principal\(principal\)\s*\n\s*)(documents = payload.get\("documents", \[\]\)[\s\S]+?scope = build_scoped_rag_request\(\{\}, principal\)\["scope"\]([\s\S]+?)scoped_request = build_scoped_rag_request\(payload, principal\))'
def replace_ingest(match):
    before = match.group(1)
    middle = match.group(2)
    after = match.group(3)
    # Insert tenant_id extraction before scope line
    new_middle = middle.replace('scope = build_scoped_rag_request({}, principal)["scope"]', 
                                 '    tenant_id = _get_tenant_id_from_request(request)\n    scope = build_scoped_rag_request({}, principal, tenant_id)["scope"]')
    new_after = after.replace('scoped_request = build_scoped_rag_request(payload, principal)',
                               'scoped_request = build_scoped_rag_request(payload, principal, tenant_id)')
    return before + new_middle + new_after
# Use simpler approach: replace line by line later.
# Let's do a two-step replacement.
# First replace the scope line.
scope_pattern = r'(\s+)scope = build_scoped_rag_request\(\{\}, principal\)\["scope"\]'
def replace_scope(match):
    indent = match.group(1)
    return f'{indent}tenant_id = _get_tenant_id_from_request(request)\n{indent}scope = build_scoped_rag_request({{}}, principal, tenant_id)["scope"]'
content = re.sub(scope_pattern, replace_scope, content)
# Then replace the scoped_request line
scoped_req_pattern = r'(\s+)scoped_request = build_scoped_rag_request\(payload, principal\)'
def replace_scoped_req(match):
    indent = match.group(1)
    return f'{indent}scoped_request = build_scoped_rag_request(payload, principal, tenant_id)'
content = re.sub(scoped_req_pattern, replace_scoped_req, content)

# 3. Update delete_rag_documents
# Find the function and replace build_scoped_rag_request calls (there are two: one for payload, one for _build_scoped_where_filter?)
# Actually there is only one call: build_scoped_rag_request(payload, principal)
# and _build_scoped_where_filter which internally uses build_scoped_rag_request.
# We'll need to pass tenant_id to both.
# Let's replace the line where build_scoped_rag_request is called with tenant_id.
# First, add tenant_id extraction after _ensure_active_principal.
delete_pattern = r'(@rag_router.delete\("/documents/\\{document_id\\}"\)[\s\S]+?async def delete_rag_documents\([^)]+\)[\s\S]+?_ensure_active_principal\(principal\)\s*\n\s*)(if not document_id:[\s\S]+?scoped_request = build_scoped_rag_request\(payload, principal\))'
def replace_delete(match):
    before = match.group(1)
    after = match.group(2)
    new_after = '''    tenant_id = _get_tenant_id_from_request(request)
    if not document_id:
        raise HTTPException(status_code=400, detail="Missing document_id")

    payload = {"document_id": document_id}
    scoped_request = build_scoped_rag_request(payload, principal, tenant_id)'''
    return before + new_after
content = re.sub(delete_pattern, replace_delete, content, flags=re.DOTALL)

# Also need to update _build_scoped_where_filter call to pass tenant_id.
# We'll replace _build_scoped_where_filter(principal, {"document_id": document_id})
# with _build_scoped_where_filter(principal, {"document_id": document_id}, tenant_id)
# But function signature doesn't accept tenant_id. Let's modify _build_scoped_where_filter to accept tenant_id optional.
# Let's do that later.
# For now, we can rely on the fact that _build_scoped_where_filter uses build_scoped_rag_request({}, principal) which will use the fixed tenant id (since no tenant_id param).
# We need to update _build_scoped_where_filter to accept tenant_id.
# Let's modify that function now.
# Find _build_scoped_where_filter definition and add tenant_id param.
where_filter_pattern = r'def _build_scoped_where_filter\(\s*principal: ClerkPrincipal,\s*extra_filter: Mapping\[str, Any\] \| None = None,\s*\)'
where_filter_replacement = '''def _build_scoped_where_filter(
    principal: ClerkPrincipal,
    extra_filter: Mapping[str, Any] | None = None,
    tenant_id: str | None = None,
)'''
content = re.sub(where_filter_pattern, where_filter_replacement, content)
# Then replace its body to pass tenant_id to build_scoped_rag_request
# Find line: scoped_filter = build_scoped_rag_request({}, principal)["scope"]
where_filter_body_pattern = r'(\s+)scoped_filter = build_scoped_rag_request\(\{\}, principal\)\["scope"\]'
def replace_where_filter_body(match):
    indent = match.group(1)
    return f'{indent}scoped_filter = build_scoped_rag_request({{}}, principal, tenant_id)["scope"]'
content = re.sub(where_filter_body_pattern, replace_where_filter_body, content)

# Now update the call in delete_rag_documents to pass tenant_id.
# Find the line: "where_filter": _build_scoped_where_filter(principal, {"document_id": document_id}),
where_filter_call_pattern = r'(\s*\"where_filter\": _build_scoped_where_filter\()principal(,\s*\{[^}]+\})(\))'
def replace_where_filter_call(match):
    indent = match.group(1)
    extra = match.group(2)
    close = match.group(3)
    return f'{indent}"where_filter": _build_scoped_where_filter(principal{extra}, tenant_id){close}'
content = re.sub(where_filter_call_pattern, replace_where_filter_call, content)

# 4. Update rag_stats
# Similar to query but with stats.
stats_pattern = r'(@rag_router.get\("/stats"\)[\s\S]+?async def rag_stats\([^)]+\)[\s\S]+?_ensure_active_principal\(principal\)\s*\n\s*)(payload: dict\[str, Any\] = \{\}\s*\n\s*scoped_request = build_scoped_rag_request\(payload, principal\))'
def replace_stats(match):
    before = match.group(1)
    after = match.group(2)
    new_after = '''    tenant_id = _get_tenant_id_from_request(request)
    payload: dict[str, Any] = {}
    scoped_request = build_scoped_rag_request(payload, principal, tenant_id)'''
    return before + new_after
content = re.sub(stats_pattern, replace_stats, content, flags=re.DOTALL)

# Also need to update the _build_scoped_where_filter call in rag_stats.
# Find the line: "where_filter": _build_scoped_where_filter(principal),
where_filter_call_stats_pattern = r'(\s*\"where_filter\": _build_scoped_where_filter\()principal(\))'
def replace_where_filter_call_stats(match):
    indent = match.group(1)
    close = match.group(2)
    return f'{indent}"where_filter": _build_scoped_where_filter(principal, None, tenant_id){close}'
content = re.sub(where_filter_call_stats_pattern, replace_where_filter_call_stats, content)

# Write back
with open('rag.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Endpoints updated.")
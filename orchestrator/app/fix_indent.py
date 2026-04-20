import re

with open('rag.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix query_rag
in_query = False
for i, line in enumerate(lines):
    if line.strip().startswith('async def query_rag'):
        in_query = True
    if in_query and line.strip() == '_ensure_active_principal(principal)':
        # Find the tenant_id line (should be next non-empty line after blank line)
        j = i + 1
        while j < len(lines) and lines[j].strip() == '':
            j += 1
        if j < len(lines) and 'tenant_id = _get_tenant_id_from_request(request)' in lines[j]:
            # Check indentation
            if lines[j].startswith('        '):
                # Fix to 4 spaces
                lines[j] = '    tenant_id = _get_tenant_id_from_request(request)\n'
        # Also ensure scoped_request line is correct (should be 4 spaces)
        # We'll just trust.
        break

# Fix delete_rag_documents: ensure tenant_id line exists and correctly indented
in_delete = False
for i, line in enumerate(lines):
    if line.strip().startswith('async def delete_rag_documents'):
        in_delete = True
    if in_delete and line.strip() == '_ensure_active_principal(principal)':
        # Look for tenant_id line after that
        j = i + 1
        while j < len(lines) and lines[j].strip() == '':
            j += 1
        if j < len(lines) and 'tenant_id = _get_tenant_id_from_request(request)' in lines[j]:
            if lines[j].startswith('        '):
                lines[j] = '    tenant_id = _get_tenant_id_from_request(request)\n'
        break

# Fix rag_stats similarly
in_stats = False
for i, line in enumerate(lines):
    if line.strip().startswith('async def rag_stats'):
        in_stats = True
    if in_stats and line.strip() == '_ensure_active_principal(principal)':
        j = i + 1
        while j < len(lines) and lines[j].strip() == '':
            j += 1
        if j < len(lines) and 'tenant_id = _get_tenant_id_from_request(request)' in lines[j]:
            if lines[j].startswith('        '):
                lines[j] = '    tenant_id = _get_tenant_id_from_request(request)\n'
        break

with open('rag.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Indentation fixed.")
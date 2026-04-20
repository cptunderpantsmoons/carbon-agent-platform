with open("rag.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

# 1. Fix rag_stats where_filter line
for i, line in enumerate(lines):
    if (
        '"where_filter": _build_scoped_where_filter("where_filter": _build_scoped_where_filter'
        in line
    ):
        # Replace with correct line
        lines[i] = (
            '            "where_filter": _build_scoped_where_filter(principal, None, tenant_id),\n'
        )
        break

# 2. Ensure tenant_id line exists in delete_rag_documents
in_delete = False
for i, line in enumerate(lines):
    if line.strip().startswith("async def delete_rag_documents"):
        in_delete = True
    if in_delete and line.strip() == "_ensure_active_principal(principal)":
        # Insert tenant_id line after blank line
        j = i + 1
        while j < len(lines) and lines[j].strip() == "":
            j += 1
        if (
            j < len(lines)
            and "tenant_id = _get_tenant_id_from_request(request)" not in lines[j]
        ):
            lines.insert(j, "    tenant_id = _get_tenant_id_from_request(request)\n")
        # Also need to update the where_filter call
        # Find the line containing \"where_filter\": _build_scoped_where_filter
        for k in range(j, len(lines)):
            if '"where_filter": _build_scoped_where_filter' in lines[k]:
                # Replace line with tenant_id parameter
                # The line currently has principal, {"document_id": document_id}
                # We need to add tenant_id as third argument
                if "tenant_id" not in lines[k]:
                    lines[k] = lines[k].replace(
                        '_build_scoped_where_filter(\n                principal,\n                {"document_id": document_id},\n            )',
                        '_build_scoped_where_filter(\n                principal,\n                {"document_id": document_id},\n                tenant_id,\n            )',
                    )
                break
        break

# 3. Ensure tenant_id line exists in rag_stats (already added? check)
in_stats = False
for i, line in enumerate(lines):
    if line.strip().startswith("async def rag_stats"):
        in_stats = True
    if in_stats and line.strip() == "_ensure_active_principal(principal)":
        j = i + 1
        while j < len(lines) and lines[j].strip() == "":
            j += 1
        if (
            j < len(lines)
            and "tenant_id = _get_tenant_id_from_request(request)" not in lines[j]
        ):
            lines.insert(j, "    tenant_id = _get_tenant_id_from_request(request)\n")
        break

# 4. Ensure tenant_id line exists in query_rag (already fixed but check)
in_query = False
for i, line in enumerate(lines):
    if line.strip().startswith("async def query_rag"):
        in_query = True
    if in_query and line.strip() == "_ensure_active_principal(principal)":
        j = i + 1
        while j < len(lines) and lines[j].strip() == "":
            j += 1
        if (
            j < len(lines)
            and "tenant_id = _get_tenant_id_from_request(request)" not in lines[j]
        ):
            lines.insert(j, "    tenant_id = _get_tenant_id_from_request(request)\n")
        break

# Write back
with open("rag.py", "w", encoding="utf-8") as f:
    f.writelines(lines)

print("Fixed.")

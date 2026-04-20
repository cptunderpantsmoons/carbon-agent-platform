import re

with open('.env.example', 'r', encoding='utf-8') as f:
    content = f.read()

# Insert after CORS section, before Rate Limiting
new_lines = '''# RAG Gateway
RAG_FIXED_TENANT_ID=contract-hub-tenant
VECTOR_STORE_URL=http://vector-store:8000
'''

# Find the line '# Rate Limiting Storage URI' and insert before it
pattern = r'(\n# Rate Limiting Storage URI)'
replacement = r'\n' + new_lines + r'\1'
content = re.sub(pattern, replacement, content)

with open('.env.example', 'w', encoding='utf-8') as f:
    f.write(content)

print('Updated .env.example')
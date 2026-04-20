"""Write contract-hub/lib/services/carbon-rag-client.ts with proper content."""
import os

OUT = r"C:\Users\MoonBuggy\Documents\LegalRepos\contract-hub\lib\services\carbon-rag-client.ts"

content = """\
/**
 * Carbon RAG Client
 * Forwards vector operations to the shared Carbon Agent Platform RAG gateway.
 * Clerk authentication is passed via Bearer token.
 */

// ── Types ─────────────────────────────────────────────────────────────────

interface CarbonRAGConfig {
  baseUrl: string;
}

export interface IngestDocument {
  text: string;
  metadata?: Record<string, unknown>;
  id?: string;
  document_id?: string;
}

export interface SearchResult {
  rank: number;
  text: string;
  full_text: string;
  metadata: Record<string, unknown>;
  relevance_score: number;
  distance: number;
}

export interface IngestResponse {
  scope: { tenant_id: string; clerk_user_id: string };
  payload: object;
  result: { added: number };
}

export interface SearchResponse {
  scope: { tenant_id: string; clerk_user_id: string };
  payload: object;
  result: {
    query: string;
    results: SearchResult[];
    total_found: number;
  };
}

export interface DeleteResponse {
  scope: { tenant_id: string; clerk_user_id: string };
  payload: { document_id: string };
  result: { deleted: number };
}

export interface StatsResponse {
  scope: { tenant_id: string; clerk_user_id: string };
  payload: object;
  result: {
    total_documents: number;
    collection_name: string;
    embedding_model: string;
  };
}

// ── Client ────────────────────────────────────────────────────────────────

export class CarbonRAGClient {
  private baseUrl: string;

  constructor(config: CarbonRAGConfig) {
    this.baseUrl = config.baseUrl.replace(/\\/$/, '');
  }

  private headers(authToken: string, tenantId: string): HeadersInit {
    return {
      Authorization: `Bearer ${authToken}`,
      'Content-Type': 'application/json',
      'X-Tenant-Id': tenantId,
    };
  }

  async ingestDocuments(
    authToken: string,
    tenantId: string,
    documents: IngestDocument[],
    batchSize = 500
  ): Promise<IngestResponse> {
    const res = await fetch(`${this.baseUrl}/api/v1/rag/ingest`, {
      method: 'POST',
      headers: this.headers(authToken, tenantId),
      body: JSON.stringify({ documents, batch_size: batchSize }),
    });
    if (!res.ok) {
      const err = await res.text();
      throw new Error(`Carbon RAG ingest failed: ${res.status} ${err}`);
    }
    return res.json();
  }

  async search(
    authToken: string,
    tenantId: string,
    query: string,
    nResults = 10
  ): Promise<SearchResponse> {
    const res = await fetch(`${this.baseUrl}/api/v1/rag/query`, {
      method: 'POST',
      headers: this.headers(authToken, tenantId),
      body: JSON.stringify({ query, n_results: nResults }),
    });
    if (!res.ok) {
      const err = await res.text();
      throw new Error(`Carbon RAG search failed: ${res.status} ${err}`);
    }
    return res.json();
  }

  async deleteDocument(
    authToken: string,
    tenantId: string,
    documentId: string
  ): Promise<DeleteResponse> {
    const res = await fetch(
      `${this.baseUrl}/api/v1/rag/documents/${encodeURIComponent(documentId)}`,
      {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${authToken}`,
          'X-Tenant-Id': tenantId,
        },
      }
    );
    if (!res.ok) {
      const err = await res.text();
      throw new Error(`Carbon RAG delete failed: ${res.status} ${err}`);
    }
    return res.json();
  }

  async getStats(authToken: string, tenantId: string): Promise<StatsResponse> {
    const res = await fetch(`${this.baseUrl}/api/v1/rag/stats`, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${authToken}`,
        'X-Tenant-Id': tenantId,
      },
    });
    if (!res.ok) {
      const err = await res.text();
      throw new Error(`Carbon RAG stats failed: ${res.status} ${err}`);
    }
    return res.json();
  }
}

// ── Singleton ─────────────────────────────────────────────────────────────

let _client: CarbonRAGClient | null = null;

export function getDefaultCarbonRAGClient(): CarbonRAGClient {
  if (!_client) {
    const baseUrl = process.env.CARBON_RAG_URL;
    if (!baseUrl) {
      throw new Error('CARBON_RAG_URL environment variable is not set');
    }
    _client = new CarbonRAGClient({ baseUrl });
  }
  return _client;
}
"""

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    f.write(content)
print(f"Written {len(content)} bytes to {OUT}")

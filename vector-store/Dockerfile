FROM python:3.12-slim@sha256:804ddf3251a60bbf9c92e73b7566c40428d54d0e79d3428194edf40da6521286

WORKDIR /app

# Install system dependencies
# curl/tini for health-check and signal handling;
# gcc/g++/cmake needed to compile chroma-hnswlib
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tini \
    gcc \
    g++ \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the fastembed model so the first request is instant.
# Model is stored in /app/.cache/fastembed (~90 MB for bge-small-en-v1.5)
ENV FASTEMBED_CACHE_PATH=/app/.cache/fastembed
RUN python -c \
    "from fastembed import TextEmbedding; \
     import os; \
     os.environ['FASTEMBED_CACHE_PATH']='/app/.cache/fastembed'; \
     m = TextEmbedding('BAAI/bge-small-en-v1.5'); \
     _ = list(m.embed(['warmup'])); \
     print('Model cached OK')"

# Copy application code
COPY app/ ./app/

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Use tini for proper signal handling
ENTRYPOINT ["/usr/bin/tini", "--"]

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

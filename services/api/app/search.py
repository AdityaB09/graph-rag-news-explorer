# services/api/app/search.py
from __future__ import annotations
import os
from datetime import datetime
from typing import List, Optional

INDEX_NAME = "news_docs"

OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "").strip()
OPENSEARCH_USERNAME = os.getenv("OPENSEARCH_USERNAME", "").strip()
OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD", "").strip()

os_client = None
if OPENSEARCH_URL:
    try:
        from opensearchpy import OpenSearch
        # Basic connection; supports http or https
        kwargs = {}
        if OPENSEARCH_USERNAME and OPENSEARCH_PASSWORD:
            kwargs["http_auth"] = (OPENSEARCH_USERNAME, OPENSEARCH_PASSWORD)
        if OPENSEARCH_URL.startswith("https://"):
            kwargs.update(dict(use_ssl=True, verify_certs=True))
        os_client = OpenSearch(hosts=[OPENSEARCH_URL], **kwargs)
    except Exception as e:
        print(f"[search] Failed to init OpenSearch client: {e}")
        os_client = None
else:
    print("[search] OPENSEARCH_URL not set; search is DISABLED")

def ensure_index() -> bool:
    """Create the index if missing. Returns True if usable, False if disabled/unavailable."""
    if not os_client:
        return False
    try:
        if not os_client.indices.exists(INDEX_NAME):
            body = {
                "settings": {"number_of_shards": 1, "number_of_replicas": 0},
                "mappings": {
                    "properties": {
                        "title": {"type": "text"},
                        "url": {"type": "keyword"},
                        "source": {"type": "keyword"},
                        "published_at": {"type": "date"},
                        "entities": {"type": "keyword"},
                        "embedding": {"type": "dense_vector", "dims": 384, "index": False},
                    }
                },
            }
            os_client.indices.create(index=INDEX_NAME, body=body)
        return True
    except Exception as e:
        print(f"[search] ensure_index error: {e}")
        return False

def reset_index():
    if not os_client:
        return
    try:
        if os_client.indices.exists(INDEX_NAME):
            os_client.indices.delete(index=INDEX_NAME)
    except Exception as e:
        print(f"[search] reset_index error: {e}")
    ensure_index()

def index_document(
    doc_id: str,
    title: str,
    url: str,
    source: str,
    published_at,
    entities: List[str],
    embedding: Optional[list] = None,
):
    """Index a document if OpenSearch is configured; otherwise no-op."""
    if not os_client:
        return
    try:
        body = {
            "title": title,
            "url": url,
            "source": source,
            "published_at": published_at if isinstance(published_at, str) else (published_at or datetime.utcnow()),
            "entities": entities or [],
            "embedding": embedding or [],
        }
        os_client.index(index=INDEX_NAME, id=doc_id, body=body)
    except Exception as e:
        print(f"[search] index_document error: {e}")

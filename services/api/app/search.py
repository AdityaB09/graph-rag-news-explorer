# services/api/app/search.py
import os
from datetime import datetime
from typing import Iterable, Optional, Any, Dict, List

from opensearchpy import OpenSearch, RequestsHttpConnection
from opensearchpy.exceptions import TransportError

OPENSEARCH_URL = os.environ.get("OPENSEARCH_URL", "http://opensearch:9200")
INDEX_NAME = os.environ.get("OPENSEARCH_INDEX", "news_docs")

_os_client: Optional[OpenSearch] = None


def _client() -> OpenSearch:
    global _os_client
    if _os_client is None:
        _os_client = OpenSearch(
            hosts=[OPENSEARCH_URL],
            http_auth=None,
            use_ssl=False,
            verify_certs=False,
            connection_class=RequestsHttpConnection,
            timeout=30,
            max_retries=3,
            retry_on_timeout=True,
        )
    return _os_client


def ensure_index() -> None:
    """
    Create index with a simple mapping. We store the embedding as a float array
    (no k-NN plugin required), which avoids dense_vector / knn_vector issues.
    """
    os_client = _client()
    try:
        if os_client.indices.exists(index=INDEX_NAME):
            return
    except TransportError:
        # If security plugin returns 401 for exists, try creating anyway
        pass

    body = {
        "settings": {
            "index": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
            }
        },
        "mappings": {
            "properties": {
                "title": {"type": "text"},
                "url": {"type": "keyword"},
                "source": {"type": "keyword"},
                "published_at": {"type": "date"},
                "entities": {"type": "keyword"},
                # store embeddings as a plain float array
                "embedding": {"type": "float"},
            }
        },
    }

    try:
        os_client.indices.create(index=INDEX_NAME, body=body)
    except TransportError as e:
        # ignore "resource_already_exists_exception"
        err_type = getattr(e, "error", None) or ""
        if "resource_already_exists_exception" not in str(err_type).lower():
            raise


def index_document(
    doc_id: Any,
    title: Optional[str],
    url: str,
    source: Optional[str],
    published_at: Optional[datetime],
    *,
    entities: Optional[Iterable[str]] = None,
    embedding: Optional[Iterable[float]] = None,
) -> Dict[str, Any]:
    """
    Upsert a doc into OpenSearch. Accepts extra fields used by callers.
    """
    doc: Dict[str, Any] = {
        "title": title,
        "url": url,
        "source": source,
        "published_at": published_at.isoformat() if published_at else None,
    }
    if entities is not None:
        doc["entities"] = list(entities)
    if embedding is not None:
        # store as list[float]
        doc["embedding"] = list(embedding)

    res = _client().index(index=INDEX_NAME, id=str(doc_id), body=doc, refresh=True)
    return res

# services/api/app/opensearch_index.py
import os
from opensearchpy import OpenSearch, helpers

OS_URL = os.getenv("OPENSEARCH_URL", "http://opensearch:9200")
INDEX = os.getenv("OS_NEWS_INDEX", "news_docs")

client = OpenSearch(OS_URL)

MAPPING = {
    "settings": {
        "index": {"number_of_shards": 1, "number_of_replicas": 0},
        "analysis": {"analyzer": {"std_english": {"type": "standard"}}},
    },
    "mappings": {
        "properties": {
            "id": {"type": "keyword"},
            "url": {"type": "keyword"},
            "title": {"type": "text", "analyzer": "std_english"},
            "published": {"type": "date"},
            "site": {"type": "keyword"},
            "text": {"type": "text", "analyzer": "std_english"},
            "entities": {
                "type": "nested",
                "properties": {
                    "text": {"type": "keyword"},
                    "label": {"type": "keyword"},
                    "start": {"type": "integer"},
                    "end": {"type": "integer"},
                },
            },
        }
    },
}

def ensure_index():
    if not client.indices.exists(INDEX):
        client.indices.create(index=INDEX, body=MAPPING)

def upsert_docs(docs):
    if not docs:
        return 0
    actions = [
        {"_index": INDEX, "_id": d["id"], "_op_type": "index", "_source": d}
        for d in docs
    ]
    helpers.bulk(client, actions)
    return len(docs)

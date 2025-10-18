# services/api/app/ingest_jobs.py
import hashlib
import time
import feedparser
import trafilatura
import spacy
from urllib.parse import urlparse, quote_plus
from typing import List, Dict, Any

from .opensearch_index import ensure_index, upsert_docs
from .graph_client import upsert_graph  # uses your existing client to graph-engine

# Lazy load spaCy to keep worker memory lower on boot
_nlp = None
def nlp():
    global _nlp
    if _nlp is None:
        # small English model; you can switch to a larger one if needed
        _nlp = spacy.blank("en")
        try:
            # If en_core_web_sm is installed, use it for better NER
            _nlp = spacy.load("en_core_web_sm")
        except Exception:
            pass
    return _nlp

def _doc_id(url: str) -> str:
    return "doc:" + hashlib.md5(url.encode("utf-8")).hexdigest()[:16]

def _site(url: str) -> str:
    try:
        return urlparse(url).netloc
    except Exception:
        return "unknown"

def _extract(url: str) -> Dict[str, Any]:
    downloaded = trafilatura.fetch_url(url, no_ssl=True)
    if not downloaded:
        raise RuntimeError("fetch failed")
    text = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
    if not text:
        raise RuntimeError("extract failed")
    return {"text": text}

def _ner(text: str) -> List[Dict[str, Any]]:
    doc = nlp()(text)
    ents = []
    for ent in getattr(doc, "ents", []):
        ents.append({
            "text": ent.text,
            "label": ent.label_,
            "start": ent.start_char,
            "end": ent.end_char,
        })
    return ents

def _index_and_graph(record: Dict[str, Any]):
    ensure_index()
    upsert_docs([record])

    # Build nodes/edges from entities
    ts_ms = int(record.get("published_ms") or time.time() * 1000)
    doc_id = record["id"]
    nodes = [{"id": doc_id, "type": "doc", "ts": ts_ms, "attrs": {"title": record.get("title", record["url"])}}]
    edges = []
    seen_entities = set()

    for e in record.get("entities", []):
        # very basic entity key
        key = f'ent:{e["label"]}:{e["text"].upper().strip()}'
        if key not in seen_entities:
            nodes.append({"id": key, "type": "entity", "ts": ts_ms, "attrs": {"name": e["text"], "label": e["label"]}})
            seen_entities.add(key)
        edges.append({"src": doc_id, "dst": key, "type": "MENTIONS", "weight": 1.0, "ts": ts_ms})

    # naive co-occur edges between all entity pairs in this doc
    ents = list(seen_entities)
    for i in range(len(ents)):
        for j in range(i + 1, len(ents)):
            edges.append({"src": ents[i], "dst": ents[j], "type": "CO_OCCUR", "weight": 1.0, "ts": ts_ms})

    # upsert to graph-engine
    upsert_graph(nodes, edges)

def job_ingest_url(url: str) -> int:
    rec = {"id": _doc_id(url), "url": url, "site": _site(url)}
    ex = _extract(url)
    rec["text"] = ex["text"]
    rec["title"] = rec.get("title") or rec["url"]
    rec["published"] = None
    rec["published_ms"] = int(time.time() * 1000)
    rec["entities"] = _ner(rec["text"])
    _index_and_graph(rec)
    return 1

def job_ingest_rss(rss_url: str, limit: int = 20) -> int:
    feed = feedparser.parse(rss_url)
    count = 0
    for entry in (feed.entries or [])[:limit]:
        url = entry.link
        try:
            rec = {"id": _doc_id(url), "url": url, "site": _site(url)}
            rec["title"] = getattr(entry, "title", url)
            published = getattr(entry, "published_parsed", None)
            rec["published_ms"] = int(time.mktime(published) * 1000) if published else int(time.time() * 1000)
            ex = _extract(url)
            rec["text"] = ex["text"]
            rec["entities"] = _ner(rec["text"])
            _index_and_graph(rec)
            count += 1
        except Exception:
            # continue best-effort
            continue
    return count

def job_ingest_search(query: str, limit: int = 20) -> int:
    # Use Google News RSS (free, no keys)
    q = quote_plus(query)
    rss_url = f"https://news.google.com/rss/search?q={q}"
    return job_ingest_rss(rss_url, limit=limit)

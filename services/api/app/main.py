# services/api/app/main.py
from __future__ import annotations

from uuid import uuid4
from datetime import datetime
from typing import Dict, Any, List

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .schemas import (
    Health, IngestTopicRequest, IngestRssRequest, IngestUrlRequest,
    JobCreateResponse, JobStatusResponse,
    ExpandRequest, ExpandResponse, GraphNode, GraphEdge
)
from .db import init_schema, SessionLocal, upsert_document, upsert_entity, link_doc_entity, expand_graph
from .crawler import fetch_url, fetch_rss
from .nlp import extract_entities, embed
from .search import index_document, ensure_index


app = FastAPI(title="Graph-RAG News Explorer (real)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# simple in-memory job store
JOBS: Dict[str, Dict[str, Any]] = {}

# init DB + index
init_schema()
ensure_index()


@app.get("/health", response_model=Health)
def health():
    return Health()


def _ingest_single(url: str, title_hint: str | None = None, source: str = "") -> Dict[str, Any]:
    """
    Fetch a URL, persist as a Document, extract/link entities, and index.
    Uses a proper SQLAlchemy Session for upsert_entity() (required by db.py).
    """
    page = fetch_url(url)
    title = title_hint or page.get("title") or url
    text = page.get("text") or ""
    published_at = page.get("published_at") or datetime.utcnow()

    # persist doc (ORM)
    doc_id = upsert_document(
        url=url,
        title=title,
        source=source,
        text=text,
        published_at=published_at
    )

    # NER → upsert entities with a real Session
    ents = extract_entities(text)  # list[(name, type)]
    ent_names: List[str] = []
    if ents:
        with SessionLocal() as s:
            for name, etype in ents:
                try:
                    ent_id = upsert_entity(s, name, etype)
                    link_doc_entity(doc_id=doc_id, ent_id=ent_id, relation="MENTION")
                    ent_names.append(name)
                except Exception as e:
                    # Non-fatal; continue with other entities
                    print(f"[entity-link] failed for '{name}': {e}")

    # embed + index (vector + metadata)
    try:
        vec = embed((title or "") + "\n" + text[:4000])
        index_document(doc_id, title, url, source, published_at, entities=ent_names, embedding=vec)
    except Exception as e:
        # Indexing should not fail the ingestion
        print(f"[index] failed for {url}: {e}")

    return {
        "doc_id": str(doc_id),
        "title": title,
        "url": url,
        "entities": ent_names,
        "published_at": published_at.isoformat(),
    }


# ---------------------------
# Topic ingestion (safe path)
# ---------------------------

# We avoid fetch_topic() and any raw-connection usage.
# Instead, collect from a couple of broad RSS feeds and keyword-filter the titles.

_TOPIC_FEEDS = [
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
]

def _normalize_topic(s: str) -> str:
    return " ".join((s or "").split()).strip()

def _topic_terms(topic: str) -> List[str]:
    import re
    return [w for w in re.split(r"[^\w]+", topic.lower()) if w]

def _title_matches(title: str, terms: List[str]) -> bool:
    t = (title or "").lower()
    return any(w and w in t for w in terms)


@app.post("/ingest/topic", response_model=JobCreateResponse)
def ingest_topic(req: IngestTopicRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid4())
    JOBS[job_id] = {"status": "queued", "result": None}

    def work():
        try:
            topic = _normalize_topic(req.topic)
            if not topic:
                JOBS[job_id] = {"status": "error", "result": {"error": "empty topic"}}
                return

            terms = _topic_terms(topic)

            # Collect items from a couple of reliable world feeds
            candidates: List[Dict[str, Any]] = []
            for feed in _TOPIC_FEEDS:
                try:
                    items = fetch_rss(feed)  # expects list of {title, url, published_at, ...}
                    # Tag the source so we can persist it
                    for it in items:
                        it["__source"] = feed
                    candidates.extend(items)
                except Exception as e:
                    print(f"[topic] fetch_rss failed for {feed}: {e}")

            # Filter by topic terms (title-based)
            matches = [it for it in candidates if _title_matches(it.get("title", ""), terms)]

            # Ingest (cap to a reasonable number)
            results: List[Dict[str, Any]] = []
            for item in matches[:20]:
                results.append(
                    _ingest_single(
                        item["url"],
                        item.get("title"),
                        source=item.get("__source", "topic")
                    )
                )

            JOBS[job_id] = {"status": "done", "result": {"ingested": results}}
        except Exception as e:
            import traceback
            print("[TOPIC-JOB-ERROR]", repr(e), flush=True)
            traceback.print_exc()
            JOBS[job_id] = {"status": "error", "result": {"error": str(e)}}

    background_tasks.add_task(work)
    return JobCreateResponse(job_id=job_id)


# ---------------------------
# RSS & URL ingestion (as-is)
# ---------------------------

@app.post("/ingest/rss", response_model=JobCreateResponse)
def ingest_rss(req: IngestRssRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid4())
    JOBS[job_id] = {"status": "queued", "result": None}

    def work():
        try:
            items = fetch_rss(req.rss_url)
            results: List[Dict[str, Any]] = []
            for item in items[:30]:
                results.append(_ingest_single(item["url"], item.get("title"), source=req.rss_url))
            JOBS[job_id] = {"status": "done", "result": {"ingested": results}}
        except Exception as e:
            JOBS[job_id] = {"status": "error", "result": {"error": str(e)}}

    background_tasks.add_task(work)
    return JobCreateResponse(job_id=job_id)


@app.post("/ingest/url", response_model=JobCreateResponse)
def ingest_url(req: IngestUrlRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid4())
    JOBS[job_id] = {"status": "queued", "result": None}

    def work():
        try:
            result = _ingest_single(req.url, source="single-url")
            JOBS[job_id] = {"status": "done", "result": {"ingested": [result]}}
        except Exception as e:
            JOBS[job_id] = {"status": "error", "result": {"error": str(e)}}

    background_tasks.add_task(work)
    return JobCreateResponse(job_id=job_id)


# ---------------------------
# Jobs & Graph
# ---------------------------

@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
def jobs(job_id: str):
    j = JOBS.get(job_id)
    if not j:
        raise HTTPException(404, "job not found")
    return JobStatusResponse(job_id=job_id, status=j["status"], result=j["result"])


@app.post("/graph/expand", response_model=ExpandResponse)
def graph_expand(req: ExpandRequest):
    nodes, edges = expand_graph(req.seed_ids, req.window_days)
    return ExpandResponse(
        nodes=[GraphNode(**n) for n in nodes],
        edges=[GraphEdge(**e) for e in edges],
    )

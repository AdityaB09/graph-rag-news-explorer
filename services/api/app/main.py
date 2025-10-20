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


# at top
from .db import init_schema, upsert_document, upsert_entity, link_doc_entity, expand_graph, SessionLocal
from .nlp import extract_entities, embed

def _ingest_single(url: str, title_hint: str | None = None, source: str = "") -> dict:
    page = fetch_url(url)
    title = title_hint or page.get("title") or url
    text = page.get("text") or ""
    published_at = page.get("published_at") or datetime.utcnow()

    # 1) persist/ensure doc
    doc_id = upsert_document(url=url, title=title, source=source, text=text, published_at=published_at)

    # 2) NER (use title + text)
    ents = extract_entities(text, title=title)  # <-- important

    ent_names: list[str] = []
    # 3) Upsert entities + create links in ONE transaction
    with SessionLocal() as s:
        for name, etype in ents:
            ent_id = upsert_entity(s, name, etype)
            link_doc_entity(s, doc_id=doc_id, ent_id=ent_id, relation="MENTION")
            ent_names.append(name)
        s.commit()  # <-- single commit so FKs are satisfied

    # 4) embed + index
    vec = embed((title or "") + "\n" + text[:4000])
    index_document(doc_id, title, url, source, published_at, entities=ent_names, embedding=vec)

    return {
        "doc_id": str(doc_id),
        "title": title,
        "url": url,
        "entities": ent_names,
        "published_at": published_at.isoformat()
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


# --- Admin: Flush DB & reset index ------------------------------------------
# --- Admin: Flush & Stats ----------------------------------------------------
from sqlalchemy import text as sa_text, func, select
from .db import engine, SessionLocal, Document, Entity, DocEntity

@app.post("/admin/flush")
def admin_flush():
    """
    Wipe all ingested data (documents, entities, links). Resets JOBS.
    Tries TRUNCATE CASCADE (Postgres); falls back to DELETE.
    """
    with engine.begin() as conn:
        try:
            conn.execute(sa_text("TRUNCATE TABLE doc_entities, documents, entities RESTART IDENTITY CASCADE;"))
        except Exception:
            conn.execute(sa_text("DELETE FROM doc_entities;"))
            conn.execute(sa_text("DELETE FROM documents;"))
            conn.execute(sa_text("DELETE FROM entities;"))

    JOBS.clear()

    # Best-effort index reset (optional)
    try:
        from .search import reset_index, ensure_index
        try:
            reset_index()
        except Exception:
            ensure_index()
    except Exception:
        pass

    from datetime import datetime
    return {"status": "ok", "flushed_at": datetime.utcnow().isoformat() + "Z"}

@app.get("/admin/stats")
def admin_stats():
    """
    Return simple table counts to verify flush/ingest operations.
    """
    with SessionLocal() as s:
        docs = s.scalar(select(func.count(Document.id))) or 0
        ents = s.scalar(select(func.count(Entity.id))) or 0
        links = s.scalar(select(func.count(DocEntity.id))) or 0
    return {"status": "ok", "documents": int(docs), "entities": int(ents), "doc_entities": int(links)}

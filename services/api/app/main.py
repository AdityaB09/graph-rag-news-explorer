# services/api/app/main.py
from __future__ import annotations

import os
import json
import time
from uuid import uuid4
from datetime import datetime
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, BackgroundTasks, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import text as sa_text, func, select, desc

from .schemas import (
    Health, IngestTopicRequest, IngestRssRequest, IngestUrlRequest,
    JobCreateResponse, JobStatusResponse,
    ExpandRequest, ExpandResponse, GraphNode, GraphEdge
)
from .db import (
    init_schema, SessionLocal, upsert_document, upsert_entity,
    link_doc_entity, expand_graph, engine, Document, Entity, DocEntity
)
from .crawler import fetch_url, fetch_rss, fetch_topic
from .nlp import extract_entities, embed
from .search import index_document, ensure_index

# --------------------------------------------------------------------------------------
# Feature flags to keep Render instance stable (avoid OOM from local embeddings)
# --------------------------------------------------------------------------------------
EMBED_DISABLED = (os.getenv("EMBED_DISABLED", "").lower() in ("1", "true", "yes"))
INDEX_DISABLED = (os.getenv("INDEX_DISABLED", "").lower() in ("1", "true", "yes"))

# --------------------------------------------------------------------------------------
# Job store (Redis-backed with in-memory fallback) so /jobs/{id} survives restarts
# --------------------------------------------------------------------------------------
REDIS_URL = os.getenv("REDIS_URL") or os.getenv("UPSTASH_REDIS_REST_URL")
_redis = None
_redis_mode = "memory"
if REDIS_URL:
    try:
        import redis  # ensure 'redis' is in requirements
        # Upstash "rediss://" needs SSL=True; plain "redis://" doesn't.
        use_ssl = REDIS_URL.startswith("rediss://")
        _redis = redis.from_url(REDIS_URL, decode_responses=True, ssl=use_ssl)
        _redis.ping()
        _redis_mode = "redis"
        print(f"[jobs] Redis OK via {REDIS_URL[:32]}... (ssl={use_ssl})")
    except Exception as _e:
        print(f"[jobs] Redis unavailable ({type(_e).__name__}: {_e}); falling back to memory.")
        _redis = None
        _redis_mode = "memory"

_memory_jobs: Dict[str, Dict[str, Any]] = {}

def _job_key(job_id: str) -> str:
    return f"jobs:{job_id}"

def _jobs_set(job_id: str, status: str, result: Optional[dict] = None, ttl_s: int = 24 * 3600) -> None:
    doc = {"status": status, "result": result or {}, "ts": time.time()}
    if _redis:
        try:
            _redis.setex(_job_key(job_id), ttl_s, json.dumps(doc))
        except Exception as e:
            print(f"[jobs] setex failed ({e}); using memory")
            _memory_jobs[job_id] = doc
    else:
        _memory_jobs[job_id] = doc

def _jobs_get(job_id: str) -> Optional[dict]:
    if _redis:
        try:
            raw = _redis.get(_job_key(job_id))
            return json.loads(raw) if raw else None
        except Exception as e:
            print(f"[jobs] get failed ({e}); falling back to memory")
            return _memory_jobs.get(job_id)
    return _memory_jobs.get(job_id)

def _jobs_clear_all_memory_only() -> None:
    _memory_jobs.clear()


# --------------------------------------------------------------------------------------
# FastAPI app + CORS
# --------------------------------------------------------------------------------------
app = FastAPI(title="Graph-RAG News Explorer (real)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# init DB + index
init_schema()
try:
    ensure_index()  # returns False when disabled; that's OK
except Exception as e:
    print(f"[main] ensure_index skipped/failed: {e}")


@app.get("/health", response_model=Health)
def health():
    return Health()


# --------------------------------------------------------------------------------------
# Core ingest worker
# --------------------------------------------------------------------------------------
def _ingest_single(url: str, title_hint: str | None = None, source: str = "") -> dict:
    print(f"[ingest] fetch_url -> {url}")
    page = fetch_url(url)
    title = title_hint or page.get("title") or url
    text = page.get("text") or ""
    published_at = page.get("published_at") or datetime.utcnow()

    # 1) persist/ensure doc
    doc_id = upsert_document(url=url, title=title, source=source, text=text, published_at=published_at)

    # 2) NER (best-effort)
    try:
        try:
            ents = extract_entities(text, title=title)
        except TypeError:
            ents = extract_entities(text)
    except Exception as nlp_err:
        print(f"[ingest] extract_entities error: {nlp_err}")
        ents = []

    # 3) Upsert entities + links
    ent_names: list[str] = []
    with SessionLocal() as s:
        for name, etype in ents:
            ent_id = upsert_entity(s, name, etype)
            link_doc_entity(s, doc_id=doc_id, ent_id=ent_id, relation="MENTION")
            ent_names.append(name)
        s.commit()

    # 4) Embed + index are OPTIONAL and NON-FATAL
    vec = None
    if not EMBED_DISABLED:
        try:
            vec = embed((title or "") + "\n" + text[:4000])
        except Exception as e:
            print(f"[ingest] embed skipped (error): {e}")

    if not INDEX_DISABLED:
        try:
            index_document(doc_id, title, url, source, published_at, entities=ent_names, embedding=vec)
        except Exception as _e:
            print(f"[ingest] index_document warning: {_e}")

    print(f"[ingest] OK -> doc_id={doc_id} title={title!r}")
    return {
        "doc_id": str(doc_id),
        "title": title,
        "url": url,
        "entities": ent_names,
        "published_at": published_at.isoformat(),
    }


# --------------------------------------------------------------------------------------
# Topic ingestion
# --------------------------------------------------------------------------------------
@app.post("/ingest/topic", response_model=JobCreateResponse)
def ingest_topic(req: IngestTopicRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid4())
    _jobs_set(job_id, "queued")

    def work():
        try:
            t = fetch_topic(req.topic)  # {"items": [...], "source_used": ..., "attempts":[...]}
            items = t.get("items") or []
            results = []
            for i, item in enumerate(items[:20], start=1):
                try:
                    res = _ingest_single(item["url"], item.get("title"), source=f"topic:{t.get('source_used') or 'unknown'}")
                    results.append(res)
                    if i % 5 == 0:
                        _jobs_set(job_id, "running", {"ingested_so_far": len(results)})
                except Exception as ie:
                    print(f"[ingest] item error: {ie}")
            _jobs_set(job_id, "done", {
                "count": len(results),
                "source_used": t.get("source_used"),
                "attempts": t.get("attempts", []),
                "ingested": results,
            })
        except Exception as e:
            _jobs_set(job_id, "error", {"error": str(e)})

    background_tasks.add_task(work)
    return JobCreateResponse(job_id=job_id)


# --------------------------------------------------------------------------------------
# RSS ingestion
# --------------------------------------------------------------------------------------
@app.post("/ingest/rss", response_model=JobCreateResponse)
def ingest_rss(req: IngestRssRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid4())
    _jobs_set(job_id, "queued")

    def work():
        try:
            items, diag = fetch_rss(req.rss_url)
            results: List[Dict[str, Any]] = []
            for i, item in enumerate(items[:30], start=1):
                try:
                    res = _ingest_single(item["url"], item.get("title"), source=req.rss_url)
                    results.append(res)
                    if i % 5 == 0:
                        _jobs_set(job_id, "running", {"ingested_so_far": len(results)})
                except Exception as ie:
                    print(f"[ingest] item error: {ie}")
            _jobs_set(job_id, "done", {
                "count": len(results),
                "diag": diag,
                "ingested": results
            })
        except Exception as e:
            _jobs_set(job_id, "error", {"error": str(e)})

    background_tasks.add_task(work)
    return JobCreateResponse(job_id=job_id)


# --------------------------------------------------------------------------------------
# Single URL ingestion
# --------------------------------------------------------------------------------------
@app.post("/ingest/url", response_model=JobCreateResponse)
def ingest_url(req: IngestUrlRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid4())
    _jobs_set(job_id, "queued")

    def work():
        try:
            result = _ingest_single(req.url, source="single-url")
            _jobs_set(job_id, "done", {"ingested": [result]})
        except Exception as e:
            _jobs_set(job_id, "error", {"error": str(e)})

    background_tasks.add_task(work)
    return JobCreateResponse(job_id=job_id)


# --------------------------------------------------------------------------------------
# Jobs & Graph
# --------------------------------------------------------------------------------------
@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
def jobs(job_id: str):
    j = _jobs_get(job_id)
    if not j:
        raise HTTPException(404, "job not found")
    return JobStatusResponse(job_id=job_id, status=j["status"], result=j.get("result"))


@app.post("/graph/expand", response_model=ExpandResponse)
def graph_expand(req: ExpandRequest):
    nodes, edges = expand_graph(req.seed_ids, req.window_days)
    return ExpandResponse(
        nodes=[GraphNode(**n) for n in nodes],
        edges=[GraphEdge(**e) for e in edges],
    )


# --------------------------------------------------------------------------------------
# Admin: Flush, Stats, Entities, Recent, Checks
# --------------------------------------------------------------------------------------
@app.post("/admin/flush")
def admin_flush():
    """
    Wipe all ingested data (documents, entities, links). Resets memory JOBS.
    Tries TRUNCATE CASCADE (Postgres); falls back to DELETE.
    Also resets the vector index if available.
    """
    with engine.begin() as conn:
        try:
            conn.execute(sa_text("TRUNCATE TABLE doc_entities, documents, entities RESTART IDENTITY CASCADE;"))
        except Exception:
            conn.execute(sa_text("DELETE FROM doc_entities;"))
            conn.execute(sa_text("DELETE FROM documents;"))
            conn.execute(sa_text("DELETE FROM entities;"))

    _jobs_clear_all_memory_only()

    # Best-effort index reset
    try:
        from .search import reset_index
        try:
            reset_index()
        except Exception:
            ensure_index()
    except Exception:
        pass

    return {"status": "ok", "flushed_at": datetime.utcnow().isoformat() + "Z"}


@app.get("/admin/stats")
def admin_stats():
    with SessionLocal() as s:
        docs = s.scalar(select(func.count(Document.id))) or 0
        ents = s.scalar(select(func.count(Entity.id))) or 0
        links = s.scalar(select(func.count(DocEntity.id))) or 0
    return {"status": "ok", "documents": int(docs), "entities": int(ents), "doc_entities": int(links)}


@app.get("/admin/entities")
def admin_entities(limit: int = 50):
    with SessionLocal() as s:
        q = (
            s.query(Entity.name, func.count(DocEntity.id))
            .join(DocEntity, DocEntity.ent_id == Entity.id)
            .group_by(Entity.name)
            .order_by(func.count(DocEntity.id).desc())
            .limit(limit)
        )
        rows = q.all()

    out = []
    for name, cnt in rows:
        out.append({
            "id": f"ent:{name.upper()}",
            "label": name,
            "links": int(cnt),
        })
    return {"status": "ok", "entities": out}


@app.get("/admin/recent_docs")
def recent_docs(limit: int = Query(50, ge=1, le=500)):
    with SessionLocal() as s:
        rows = (
            s.query(Document.id, Document.title, Document.url, Document.source, Document.published_at)
             .order_by(desc(Document.published_at))
             .limit(limit)
             .all()
        )
    return {"status": "ok", "items": [
        {"id": str(r.id), "title": r.title, "url": r.url, "source": r.source,
         "published_at": (r.published_at.isoformat() if r.published_at else None)}
        for r in rows
    ]}


@app.get("/admin/checks")
def admin_checks():
    """
    Lightweight self-checks to debug deployment quickly.
    """
    # Redis ping status
    redis_ok = False
    if _redis:
        try:
            _redis.ping()
            redis_ok = True
        except Exception:
            redis_ok = False

    return {
        "status": "ok",
        "embed_disabled": EMBED_DISABLED,
        "index_disabled": INDEX_DISABLED,
        "job_store": _redis_mode,
        "redis_url_present": bool(REDIS_URL),
        "redis_ok": redis_ok,
        "time_utc": datetime.utcnow().isoformat() + "Z",
    }

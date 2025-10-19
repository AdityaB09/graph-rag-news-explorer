# services/api/app/main.py
from __future__ import annotations

from uuid import uuid4
from datetime import datetime
from typing import Dict, Any

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .schemas import (
    Health, IngestTopicRequest, IngestRssRequest, IngestUrlRequest,
    JobCreateResponse, JobStatusResponse,
    ExpandRequest, ExpandResponse, GraphNode, GraphEdge
)
from .db import init_schema, upsert_document, upsert_entity, link_doc_entity, expand_graph
from .crawler import fetch_url, fetch_rss, fetch_topic
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
    page = fetch_url(url)
    title = title_hint or page.get("title") or url
    text = page.get("text") or ""
    published_at = page.get("published_at") or datetime.utcnow()

    # persist doc
    doc_id = upsert_document(url=url, title=title, source=source, text=text, published_at=published_at)

    # NER
    ents = extract_entities(text)  # [(name, type)]
    ent_names = []
    for name, etype in ents:
        ent_id = upsert_entity(name, etype)
        link_doc_entity(doc_id=doc_id, ent_id=ent_id, relation="MENTION")
        ent_names.append(name)

    # embed + index
    vec = embed((title or "") + "\n" + text[:4000])
    index_document(doc_id, title, url, source, published_at, entities=ent_names, embedding=vec)

    return {"doc_id": str(doc_id), "title": title, "url": url, "entities": ent_names, "published_at": published_at.isoformat()}


@app.post("/ingest/topic", response_model=JobCreateResponse)
def ingest_topic(req: IngestTopicRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid4())
    JOBS[job_id] = {"status": "queued", "result": None}

    def work():
        try:
            items = fetch_topic(req.topic)
            results = []
            for item in items[:20]:
                results.append(_ingest_single(item["url"], item.get("title"), source="topic"))
            JOBS[job_id] = {"status": "done", "result": {"ingested": results}}
        except Exception as e:
            JOBS[job_id] = {"status": "error", "result": {"error": str(e)}}

    background_tasks.add_task(work)
    return JobCreateResponse(job_id=job_id)


@app.post("/ingest/rss", response_model=JobCreateResponse)
def ingest_rss(req: IngestRssRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid4())
    JOBS[job_id] = {"status": "queued", "result": None}

    def work():
        try:
            items = fetch_rss(req.rss_url)
            results = []
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

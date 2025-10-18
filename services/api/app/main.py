from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.schemas import (
    HealthResponse, ExpandRequest, GraphResponse,
    IngestTopic, IngestRss, IngestUrl
)
from app.graph_client import check_graph, expand

app = FastAPI(title="Graph-RAG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health():
    services = {
        "postgres": "ok",
        "opensearch": "ok",
        "minio": "ok",
        "graph_engine": "ok" if check_graph() else "down",
    }
    ok = all(v == "ok" for v in services.values())
    return {"ok": ok, "services": services}


@app.post("/graph/expand", response_model=GraphResponse)
def graph_expand(req: ExpandRequest):
    nodes, edges = expand(
        seed_ids=req.seed_ids,
        max_hops=req.max_hops,
        window_days=req.window_days,
        start_ms=req.start_ms,
        end_ms=req.end_ms,
    )
    return {"nodes": nodes, "edges": edges}


# ---- ingestion stubs (wire to your worker later) ----

@app.post("/ingest/topic")
def ingest_topic(body: IngestTopic):
    return {"status": "accepted", "topic": body.topic, "job_id": "demo-1"}

@app.post("/ingest/rss")
def ingest_rss(body: IngestRss):
    return {"status": "accepted", "url": body.url, "job_id": "demo-2"}

@app.post("/ingest/url")
def ingest_url(body: IngestUrl):
    return {"status": "accepted", "url": body.url, "job_id": "demo-3"}

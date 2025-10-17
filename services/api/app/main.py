from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.schemas import (
    HealthResponse, ExpandRequest, GraphResponse,
    IngestTopic, IngestRss, IngestUrl
)
from app import graph_client

app = FastAPI(title="Graph-RAG API")

# Wide-open CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

@app.get("/health", response_model=HealthResponse)
def health():
    # very light checks – extend as needed
    services = {
        "postgres": "ok",     # swap with a real check_pg() later
        "opensearch": "ok",   # swap with a real check_os() later
        "minio": "ok",        # swap with a real check_minio() later
        "graph_engine": "ok" if graph_client.check_graph() else "down",
    }
    ok = all(v == "ok" for v in services.values())
    return {"ok": ok, "services": services}

@app.post("/graph/expand", response_model=GraphResponse)
def expand(req: ExpandRequest):
    nodes, edges = graph_client.expand(
        seed_ids=req.seed_ids,
        start_ms=req.start_ms,
        end_ms=req.end_ms,
        max_hops=req.max_hops,
    )
    return {"nodes": nodes, "edges": edges}

# --- ingestion stubs (return accepted). Hook your worker later. ---

@app.post("/ingest/topic")
def ingest_topic(body: IngestTopic):
    # enqueue your real job here; for now, pretend it's done
    return {"status": "accepted", "topic": body.topic, "job_id": "demo-1"}

@app.post("/ingest/rss")
def ingest_rss(body: IngestRss):
    return {"status": "accepted", "url": body.url, "job_id": "demo-2"}

@app.post("/ingest/url")
def ingest_url(body: IngestUrl):
    return {"status": "accepted", "url": body.url, "job_id": "demo-3"}

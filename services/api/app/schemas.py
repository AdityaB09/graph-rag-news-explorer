# services/api/app/schemas.py
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Dict, Any

class Health(BaseModel):
    status: str = "ok"

class IngestTopicRequest(BaseModel):
    topic: str

class IngestRssRequest(BaseModel):
    rss_url: str

class IngestUrlRequest(BaseModel):
    url: str

class JobCreateResponse(BaseModel):
    job_id: str

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    result: Dict[str, Any] | None = None

class GraphNode(BaseModel):
    id: str
    label: str
    type: str  # "ent"|"doc"

class GraphEdge(BaseModel):
    source: str
    target: str
    label: str

class ExpandRequest(BaseModel):
    seed_ids: List[str] = Field(default_factory=list)
    max_hops: int = 2
    window_days: int = 14

class ExpandResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]

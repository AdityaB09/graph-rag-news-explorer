from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class HealthResponse(BaseModel):
    ok: bool
    services: Dict[str, str]

class ExpandRequest(BaseModel):
    seed_ids: List[str] = Field(default_factory=list)
    start_ms: Optional[int] = None
    end_ms: Optional[int] = None
    max_hops: int = 2

class GraphNode(BaseModel):
    id: str
    type: str
    attrs: Dict[str, Any] = {}

class GraphEdge(BaseModel):
    src: str
    dst: str
    type: str
    ts: Optional[str] = None

class GraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]

class IngestTopic(BaseModel):
    topic: str

class IngestRss(BaseModel):
    url: str

class IngestUrl(BaseModel):
    url: str

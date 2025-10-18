from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class HealthResponse(BaseModel):
    ok: bool
    services: Dict[str, str]


class ExpandRequest(BaseModel):
    # what the UI sends
    seed_ids: List[str] = Field(default_factory=list)
    max_hops: int = 2
    # your engine proto appears to use window_days rather than start/end
    window_days: Optional[int] = 14
    # keep these in case your UI still posts them; we just ignore them
    start_ms: Optional[int] = None
    end_ms: Optional[int] = None


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

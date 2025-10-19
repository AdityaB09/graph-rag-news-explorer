# app/graph.py
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Tuple

from .schemas import GraphNode, GraphEdge, GraphResponse
from .config import (
    ENTITY_BLACKLIST,
    PREFERRED_ENTITY_TYPES,
    RELATED_DOC_MIN_SHARED,
    MAX_NODES,
    MAX_EDGES,
)

# ---- Interfaces this module expects from your data layer ----
# You likely already have equivalent functions in your repo. If their names differ,
# adapt the calls in build_graph() accordingly.

def list_recent_documents(window_days: int) -> Iterable[Dict]:
    """
    Return an iterable of docs within the time window.
    Each doc dict should minimally have:
      {
        "doc_id": "<uuid>",
        "title": "str",
        "published_at": "iso" or dt (unused here)
      }
    """
    # >>> Replace with your actual DB/search call <<<
    raise NotImplementedError


def list_entities_for_doc(doc_id: str) -> Iterable[Dict]:
    """
    Return entities extracted for a document.
    Each entity dict should have:
      {
        "id": "ent:<CANONICAL NAME IN CAPS>",   # or your format
        "name": "Canonical Name",
        "type": "ORG|PERSON|PRODUCT|GPE|...|SOURCE",  # whatever your NER uses
        "count": int,            # frequency of mentions in the doc
        "in_title": bool         # True if appears in title
      }
    """
    # >>> Replace with your actual DB/search call <<<
    raise NotImplementedError


def get_entities_by_ids(entity_ids: Iterable[str]) -> Dict[str, Dict]:
    """
    Optional helper if you need to resolve entity metadata by ID.
    """
    # >>> Replace with your actual DB/search call (if needed) <<<
    return {}


# ----------------- Core logic for building the graph ----------------- #

def _is_blacklisted(name: str) -> bool:
    return name.upper() in ENTITY_BLACKLIST


def _score_entity_for_doc(ent: Dict) -> float:
    """
    Score how central an entity is for a doc:
      - +1.0 if appears in title
      - +0.5 if preferred type (ORG/PRODUCT/GPE)
      - +0.1 per mention count (capped a bit)
    """
    score = 0.0
    if ent.get("in_title"):
        score += 1.0
    if ent.get("type", "").upper() in PREFERRED_ENTITY_TYPES:
        score += 0.5
    count = max(0, int(ent.get("count", 0)))
    score += min(0.1 * count, 0.7)
    return score


def build_graph(
    seed_ids: List[str],
    window_days: int,
    max_hops: int = 1,
) -> GraphResponse:
    """
    Build a graph around the given seeds. We keep semantics simple:
      - Nodes: docs + (non-blacklisted) entities
      - Edges: 'about' / 'mentions' for doc->entity,
               'related' for doc<->doc with shared entities
    """
    # 1) Pull candidate docs in the window
    docs = list(list_recent_documents(window_days))

    # If seeds include doc:* then ensure those docs are included first
    seed_doc_ids = {sid.split("doc:", 1)[1] for sid in seed_ids if sid.startswith("doc:")}
    if seed_doc_ids:
        doc_id_to_row = {d["doc_id"]: d for d in docs}
        missing = [d for d in seed_doc_ids if d not in doc_id_to_row]
        # Optional: fetch missing seed docs (left noop if your list function already includes them)

    # 2) Collect entities per doc (and filter)
    doc_entities: Dict[str, List[Dict]] = {}
    all_entity_names: Counter = Counter()

    for d in docs:
        ents = []
        for e in list_entities_for_doc(d["doc_id"]):
            # Basic cleanups
            name = (e.get("name") or "").strip()
            if not name:
                continue
            if _is_blacklisted(name):
                continue
            ent_id = e.get("id") or f"ent:{name.upper()}"
            ent_type = (e.get("type") or "").upper()

            ents.append({
                "id": ent_id,
                "name": name,
                "type": ent_type,
                "count": int(e.get("count", 1)),
                "in_title": bool(e.get("in_title", False)),
            })
            all_entity_names[name.upper()] += 1

        doc_entities[d["doc_id"]] = ents

    # 3) Build nodes
    nodes: Dict[str, GraphNode] = {}
    edges: List[GraphEdge] = []

    # Doc nodes
    for d in docs:
        nid = f"doc:{d['doc_id']}"
        nodes[nid] = GraphNode(id=nid, label=(d.get("title") or "")[:60] + ("…" if len(d.get("title",""))>60 else ""), type="doc")

    # Entity nodes & doc->entity edges
    for d in docs:
        nid = f"doc:{d['doc_id']}"
        ents = doc_entities.get(d["doc_id"], [])

        # Rank entities for this doc
        ranked = sorted(ents, key=_score_entity_for_doc, reverse=True)

        for ent in ranked:
            eid = ent["id"]
            ename = ent["name"]
            etype = ent["type"]

            if eid not in nodes:
                nodes[eid] = GraphNode(id=eid, label=ename, type="entity")

            # Decide edge label
            score = _score_entity_for_doc(ent)
            label = "about" if score >= 1.0 else "mentions"

            edges.append(GraphEdge(source=nid, target=eid, label=label))

    # 4) Doc<->Doc 'related' edges (shared non-blacklisted entities)
    # Build inverted index: ent_id -> list of doc_ids
    ent_to_docs: Dict[str, List[str]] = defaultdict(list)
    for d in docs:
        for ent in doc_entities.get(d["doc_id"], []):
            ent_to_docs[ent["id"]].append(d["doc_id"])

    # For each doc, find other docs sharing >= RELATED_DOC_MIN_SHARED entities
    doc_to_shared_counts: Dict[Tuple[str, str], int] = defaultdict(int)
    for ent_id, dlist in ent_to_docs.items():
        if len(dlist) < 2:
            continue
        for i in range(len(dlist)):
            for j in range(i + 1, len(dlist)):
                a, b = dlist[i], dlist[j]
                if a > b:
                    a, b = b, a
                doc_to_shared_counts[(a, b)] += 1

    for (a, b), shared in doc_to_shared_counts.items():
        if shared >= RELATED_DOC_MIN_SHARED:
            edges.append(GraphEdge(source=f"doc:{a}", target=f"doc:{b}", label="related"))

    # 5) Trim to caps (keeps UI happy)
    if len(nodes) > MAX_NODES:
        # Keep all docs; trim entities by global frequency
        doc_nodes = {k: v for k, v in nodes.items() if v.type == "doc"}
        ent_nodes = [(k, v) for k, v in nodes.items() if v.type == "entity"]
        # Sort entity nodes by how often they show across docs (all_entity_names)
        ent_nodes.sort(key=lambda kv: all_entity_names.get(kv[1].label.upper(), 0), reverse=True)
        keep_count = max(0, MAX_NODES - len(doc_nodes))
        kept_entities = dict(ent_nodes[:keep_count])
        nodes = {**doc_nodes, **kept_entities}

        # Drop edges to removed nodes
        kept_ids = set(nodes.keys())
        edges = [e for e in edges if e.source in kept_ids and e.target in kept_ids]

    if len(edges) > MAX_EDGES:
        # Prefer to keep 'about' and 'related' edges first
        about_related = [e for e in edges if e.label in ("about", "related")]
        mentions = [e for e in edges if e.label == "mentions"]
        edges = about_related[:MAX_EDGES] if len(about_related) >= MAX_EDGES else about_related + mentions[: MAX_EDGES - len(about_related)]

    return GraphResponse(nodes=list(nodes.values()), edges=edges)

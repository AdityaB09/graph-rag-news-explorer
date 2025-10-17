# Simple stub so /health and /graph/expand work.
# You can replace this with a real gRPC client to your C++ engine later.

import socket

def check_graph() -> bool:
    host = "graph-engine"
    port = 50061
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except Exception:
        return False

def expand(seed_ids, start_ms=None, end_ms=None, max_hops=2):
    # Return a tiny deterministic graph for now so the UI works.
    nodes = [
        {"id": "ent:TATA", "type": "entity", "attrs": {"name": "TATA"}},
        {"id": "ent:FOX", "type": "entity", "attrs": {"name": "Foxconn"}},
        {"id": "doc:1", "type": "doc", "attrs": {"title": "Doc 1"}},
    ]
    edges = [
        {"src": "ent:TATA", "dst": "doc:1", "type": "MENTION"},
        {"src": "ent:FOX",  "dst": "doc:1", "type": "MENTION"},
    ]
    # If user seeds are unrelated, still return something small so it's visible
    if seed_ids and not any(s in {"ent:TATA", "ent:FOX", "doc:1"} for s in seed_ids):
        nodes = [{"id": seed_ids[0], "type": "entity", "attrs": {"name": seed_ids[0]}}]
        edges = []
    return nodes, edges

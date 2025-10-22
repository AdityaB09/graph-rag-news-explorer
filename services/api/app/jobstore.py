import os, json, time
import redis

# Works with Upstash `rediss://...`
REDIS_URL = os.getenv("REDIS_URL") or os.getenv("UPSTASH_REDIS_REST_URL")
if not REDIS_URL:
    # fall back to in-memory if you really have nothing
    _MEM = {}
    def set_status(job_id: str, status: str, meta: dict | None = None, ttl_s: int = 86400):
        _MEM[job_id] = {"status": status, "meta": meta or {}, "ts": time.time()}
    def get_status(job_id: str) -> dict | None:
        return _MEM.get(job_id)
else:
    r = redis.from_url(REDIS_URL, decode_responses=True, ssl=REDIS_URL.startswith("rediss://"))

    def _key(job_id: str) -> str: return f"jobs:{job_id}"

    def set_status(job_id: str, status: str, meta: dict | None = None, ttl_s: int = 86400):
        doc = {"status": status, "meta": meta or {}, "ts": time.time()}
        r.setex(_key(job_id), ttl_s, json.dumps(doc))

    def get_status(job_id: str) -> dict | None:
        v = r.get(_key(job_id))
        return json.loads(v) if v else None

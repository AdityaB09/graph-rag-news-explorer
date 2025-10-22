import os

OPENSEARCH_URL: str = os.getenv("OPENSEARCH_URL", "http://opensearch:9200")
OPENSEARCH_USER: str | None = os.getenv("OPENSEARCH_USER") or None
OPENSEARCH_PASSWORD: str | None = os.getenv("OPENSEARCH_PASSWORD") or None

DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_doAYeECs8U1n@ep-nameless-resonance-a4jiv5og-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require",
)

REDIS_URL: str | None = os.getenv("REDIS_URL") or None
REDIS_HOST: str = os.getenv("REDIS_HOST", "redis")
REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD: str | None = os.getenv("REDIS_PASSWORD") or None

GRAPH_ENGINE_ADDR: str = os.getenv("GRAPH_ENGINE_ADDR", "graph-engine:50061")

CORS_ORIGINS = [
    o.strip()
    for o in (os.getenv("CORS_ORIGINS") or "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if o.strip()
]

ENV: str = os.getenv("ENV", "dev")
DEBUG: bool = os.getenv("DEBUG", "0") in ("1", "true", "True")

# Browser-like UA so publishers don't block Render fetches
FETCH_UA = os.getenv(
    "FETCH_UA",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Keep short articles instead of dropping everything
MIN_CONTENT_LEN = int(os.getenv("MIN_CONTENT_LEN", "300"))

# Upper bound to avoid overloading free tiers (still generous)
MAX_ITEMS_CAP = int(os.getenv("MAX_ITEMS_CAP", "60"))
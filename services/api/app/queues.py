# services/api/app/queues.py
import os
from redis import Redis
from rq import Queue

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

redis = Redis.from_url(REDIS_URL)
q = Queue("default", connection=redis)

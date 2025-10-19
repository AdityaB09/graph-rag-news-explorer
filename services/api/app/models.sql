-- services/api/app/models.sql
-- Minimal schema in SQL, aligned with SQLAlchemy models (UUID PK + FKs)

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  url TEXT UNIQUE NOT NULL,
  title TEXT,
  source TEXT,
  published_at TIMESTAMPTZ,
  text TEXT
);

CREATE TABLE IF NOT EXISTS entities (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  type VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS doc_entities (
  id SERIAL PRIMARY KEY,
  doc_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  ent_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  relation VARCHAR(50) NOT NULL,
  CONSTRAINT uq_doc_ent_rel UNIQUE (doc_id, ent_id, relation)
);

-- Optional activity view (uses doc_entities timestamps if you add them later)

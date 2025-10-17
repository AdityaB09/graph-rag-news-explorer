CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS documents (
  id SERIAL PRIMARY KEY,
  url TEXT UNIQUE,
  site TEXT,
  published_at TIMESTAMP,
  language TEXT,
  title TEXT,
  text_hash TEXT,
  embedding vector(768)
);
CREATE INDEX IF NOT EXISTS idx_documents_published ON documents(published_at);

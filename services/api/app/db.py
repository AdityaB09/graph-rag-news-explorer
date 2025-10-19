import os
import uuid
from datetime import datetime, timedelta
from typing import List, Tuple, Optional

from sqlalchemy import (
    create_engine, text as sa_text, func,
    Column, Integer, String, Text, DateTime, ForeignKey, select, desc, UniqueConstraint, insert, update
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres@postgres:5432/postgres",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


# ----------------------- Models -----------------------

class Document(Base):
    __tablename__ = "documents"
    # UUID primary key
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url = Column(Text, unique=True, nullable=False)
    title = Column(Text, nullable=True)
    source = Column(Text, nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    text = Column(Text, nullable=True)

    entities = relationship("DocEntity", back_populates="document", cascade="all, delete-orphan")


class Entity(Base):
    __tablename__ = "entities"
    id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False)
    type = Column(String(50), nullable=True)

    __table_args__ = (UniqueConstraint("name", name="uq_entities_name"),)

    docs = relationship("DocEntity", back_populates="entity", cascade="all, delete-orphan")


class DocEntity(Base):
    __tablename__ = "doc_entities"
    id = Column(Integer, primary_key=True)
    # FK to UUID documents.id (matches Document.id type)
    doc_id = Column(PG_UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    ent_id = Column(Integer, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    relation = Column(String(50), nullable=False)

    __table_args__ = (UniqueConstraint("doc_id", "ent_id", "relation", name="uq_doc_ent_rel"),)

    document = relationship("Document", back_populates="entities")
    entity = relationship("Entity", back_populates="docs")


# ------------------- Schema bootstrap -------------------

def init_schema() -> None:
    """
    Create missing tables and ensure columns we rely on exist.
    Safe to run on startup.
    """
    with engine.begin() as conn:
        Base.metadata.create_all(bind=conn)

        # Ensure 'source' and 'text' exist (no-op if already present)
        conn.execute(sa_text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='documents' AND column_name='source'
                ) THEN
                    ALTER TABLE documents ADD COLUMN source TEXT;
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='documents' AND column_name='text'
                ) THEN
                    ALTER TABLE documents ADD COLUMN text TEXT;
                END IF;
            END$$;
        """))


# ------------------ Upsert helpers used by API/worker ------------------

def upsert_document(
    *,
    url: str,
    title: Optional[str] = None,
    source: Optional[str] = None,
    published_at: Optional[datetime] = None,
    text: Optional[str] = None,
    text_content: Optional[str] = None,
) -> uuid.UUID:
    """
    Insert or update a document by URL. Returns the document UUID.

    NOTE: accepts both `text` and `text_content` for compatibility.
    If both are provided, `text` takes precedence.
    """
    body_text = text if text is not None else text_content

    with SessionLocal() as s:
        doc = s.scalars(select(Document).where(Document.url == url)).first()
        if doc:
            if title is not None:
                doc.title = title
            if source is not None:
                doc.source = source
            if published_at is not None:
                doc.published_at = published_at
            if body_text is not None:
                doc.text = body_text
            s.commit()
            return doc.id

        new_id = uuid.uuid4()
        doc = Document(
            id=new_id,
            url=url,
            title=title,
            source=source,
            published_at=published_at,
            text=body_text,
        )
        s.add(doc)
        s.commit()
        return new_id


def upsert_entity(s: Session, name: str, etype: str | None = None) -> int:
    """
    Ensure an entity row exists; return its integer id.
    Accepts the two positional args the worker sends.
    """
    row = s.execute(select(Entity).where(Entity.name == name)).scalar_one_or_none()
    if row:
        # optionally update type if provided
        if etype and getattr(row, "type", None) != etype:
            s.execute(
                update(Entity)
                .where(Entity.id == row.id)
                .values(type=etype)
            )
            s.flush()
        return row.id

    ins = (
        insert(Entity)
        .values(name=name, type=etype)
        .returning(Entity.id)
    )
    new_id = s.execute(ins).scalar_one()
    s.flush()
    return new_id


def link_doc_entity(*, doc_id: uuid.UUID, ent_id: int, relation: str) -> None:
    """
    Create a (doc, entity, relation) link if it doesn't already exist.
    """
    rel = (relation or "").strip() or "mentions"
    with SessionLocal() as s:
        exists = s.scalars(
            select(DocEntity)
            .where(
                DocEntity.doc_id == doc_id,
                DocEntity.ent_id == ent_id,
                DocEntity.relation == rel,
            )
        ).first()
        if exists:
            return
        s.add(DocEntity(doc_id=doc_id, ent_id=ent_id, relation=rel))
        s.commit()


# ---------------- Graph query used by /graph/expand ----------------

def expand_graph(seed_ids: List[str], window_days: int = 30) -> Tuple[list, list]:
    """
    Build simple doc-entity graph for the last N days.
    seed_ids like ["ent:TATA","ent:FOX"] are optional; current logic returns recent doc/entity graph regardless.
    """
    since = datetime.utcnow() - timedelta(days=window_days)
    nodes: list = []
    edges: list = []

    with SessionLocal() as s:
        # Recent documents
        docs = s.scalars(
            select(Document)
            .where((Document.published_at.is_not(None)) & (Document.published_at >= since))
            .order_by(desc(Document.published_at))
            .limit(200)
        ).all()

        # Top entities by mention count
        ents = s.execute(
            select(Entity.id, Entity.name, Entity.type, func.count(DocEntity.id))
            .join(DocEntity, DocEntity.ent_id == Entity.id)
            .join(Document, Document.id == DocEntity.doc_id)
            .where((Document.published_at.is_not(None)) & (Document.published_at >= since))
            .group_by(Entity.id, Entity.name, Entity.type)
            .order_by(func.count(DocEntity.id).desc())
            .limit(300)
        ).all()

        for d in docs:
            nodes.append({
                "id": f"doc:{d.id}",
                "label": (d.title or d.url)[:40] + ("…" if (d.title and len(d.title) > 40) else ""),
                "type": "doc",
                "url": d.url,
                "source": d.source,
                "published_at": d.published_at.isoformat() if d.published_at else None,
            })

        for ent_id, name, etype, cnt in ents:
            nodes.append({
                "id": f"ent:{name.upper()}",
                "label": name,
                "type": "entity",
                "mentions": int(cnt),
                "entity_type": etype,
            })

        pairs = s.execute(
            select(DocEntity.doc_id, Entity.name)
            .join(Entity, Entity.id == DocEntity.ent_id)
            .join(Document, Document.id == DocEntity.doc_id)
            .where((Document.published_at.is_not(None)) & (Document.published_at >= since))
            .limit(3000)
        ).all()

        for doc_id, ent_name in pairs:
            if not ent_name:
                continue
            edges.append({
                "source": f"doc:{doc_id}",
                "target": f"ent:{ent_name.upper()}",
                "label": "mentions",   # <-- required by GraphEdge schema
            })

    return nodes, edges

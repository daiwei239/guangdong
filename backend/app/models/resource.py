from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ResourceNodeORM(Base):
    __tablename__ = "resource_nodes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    cluster_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    host_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    topo_context: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    static_attrs: Mapped[dict] = mapped_column(JSON, nullable=False)
    dynamic_state: Mapped[dict] = mapped_column(JSON, nullable=False)
    semantic_tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ResourceEdgeORM(Base):
    __tablename__ = "resource_edges"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    relation_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    bandwidth_gbps: Mapped[float] = mapped_column(Float, nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

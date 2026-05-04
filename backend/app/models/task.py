from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TaskProfileORM(Base):
    __tablename__ = "task_profiles"

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    dag_nodes: Mapped[list] = mapped_column(JSON, nullable=False)
    compute_req: Mapped[dict] = mapped_column(JSON, nullable=False)
    memory_req: Mapped[dict] = mapped_column(JSON, nullable=False)
    storage_req: Mapped[dict] = mapped_column(JSON, nullable=False)
    network_req: Mapped[dict] = mapped_column(JSON, nullable=False)
    energy_limit: Mapped[float] = mapped_column(Float, nullable=False)
    qos_deadline_sec: Mapped[float] = mapped_column(Float, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    constraints: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

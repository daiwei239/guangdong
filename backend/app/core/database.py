from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, future=True, echo=False, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.models.match import CandidateSubgraphORM, MatchResultORM  # noqa: F401
    from app.models.resource import ResourceEdgeORM, ResourceNodeORM  # noqa: F401
    from app.models.task import TaskProfileORM  # noqa: F401

    Base.metadata.create_all(bind=engine)

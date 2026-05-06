import logging
from typing import Optional

from sqlalchemy import desc, select

from app.core.database import SessionLocal
from app.mock.mock_task_generator import MockTaskGenerator
from app.models.task import TaskProfileORM
from app.schemas.task_schema import TaskProfileCreate, TaskProfileRead


logger = logging.getLogger(__name__)


class TaskService:
    def __init__(self) -> None:
        self.generator = MockTaskGenerator()
        self._tasks = {}
        self._current_task_id = None

    def generate_task(self) -> TaskProfileRead:
        task = self.generator.generate_task_profile()
        self._tasks[task.task_id] = task
        self._current_task_id = task.task_id
        self._persist_task(task)
        return task

    def create_task(self, task: TaskProfileCreate) -> TaskProfileRead:
        task_read = TaskProfileRead(**task.dict())
        self._tasks[task_read.task_id] = task_read
        self._current_task_id = task_read.task_id
        self._persist_task(task_read)
        return task_read

    def get_task(self, task_id: str) -> Optional[TaskProfileRead]:
        task = self._tasks.get(task_id)
        if task is not None:
            return task
        return self._load_task_from_db(task_id)

    def get_current_task(self) -> Optional[TaskProfileRead]:
        if self._current_task_id is None:
            return self._load_latest_task_from_db()
        task = self._tasks.get(self._current_task_id)
        if task is not None:
            return task
        return self._load_task_from_db(self._current_task_id)

    def _persist_task(self, task: TaskProfileRead) -> None:
        """将任务画像写入数据库，便于后续回放与查询。"""
        try:
            with SessionLocal() as session:
                session.merge(
                    TaskProfileORM(
                        task_id=task.task_id,
                        task_type=task.task_type,
                        dag_nodes=task.dag_nodes,
                        compute_req=task.compute_req,
                        memory_req=task.memory_req,
                        storage_req=task.storage_req,
                        network_req=task.network_req,
                        energy_limit=task.energy_limit,
                        qos_deadline_sec=task.qos_deadline_sec,
                        priority=task.priority,
                        constraints=task.constraints,
                        created_at=task.created_at,
                    )
                )
                session.commit()
        except Exception as exc:  # pragma: no cover
            logger.warning("failed to persist task profile: %s", exc)

    def _load_task_from_db(self, task_id: str) -> Optional[TaskProfileRead]:
        try:
            with SessionLocal() as session:
                row = session.get(TaskProfileORM, task_id)
        except Exception as exc:  # pragma: no cover
            logger.warning("failed to load task profile from database: %s", exc)
            return None

        if row is None:
            return None
        task = self._row_to_schema(row)
        self._tasks[task.task_id] = task
        self._current_task_id = task.task_id
        return task

    def _load_latest_task_from_db(self) -> Optional[TaskProfileRead]:
        try:
            with SessionLocal() as session:
                row = session.execute(select(TaskProfileORM).order_by(desc(TaskProfileORM.created_at))).scalars().first()
        except Exception as exc:  # pragma: no cover
            logger.warning("failed to load latest task profile from database: %s", exc)
            return None
        if row is None:
            return None
        task = self._row_to_schema(row)
        self._tasks[task.task_id] = task
        self._current_task_id = task.task_id
        return task

    def _row_to_schema(self, row: TaskProfileORM) -> TaskProfileRead:
        return TaskProfileRead(
            task_id=row.task_id,
            task_type=row.task_type,
            dag_nodes=row.dag_nodes or [],
            compute_req=row.compute_req or {},
            memory_req=row.memory_req or {},
            storage_req=row.storage_req or {},
            network_req=row.network_req or {},
            energy_limit=row.energy_limit,
            qos_deadline_sec=row.qos_deadline_sec,
            priority=row.priority,
            constraints=row.constraints or {},
            created_at=row.created_at,
        )


task_service = TaskService()

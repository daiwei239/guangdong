from typing import Dict, Optional

from app.mock.mock_task_generator import MockTaskGenerator
from app.schemas.task_schema import TaskProfileCreate, TaskProfileRead


class TaskService:
    def __init__(self) -> None:
        self.generator = MockTaskGenerator()
        self._tasks = {}
        self._current_task_id = None

    def generate_task(self) -> TaskProfileRead:
        task = self.generator.generate_task_profile()
        self._tasks[task.task_id] = task
        self._current_task_id = task.task_id
        return task

    def create_task(self, task: TaskProfileCreate) -> TaskProfileRead:
        task_read = TaskProfileRead(**task.dict())
        self._tasks[task_read.task_id] = task_read
        self._current_task_id = task_read.task_id
        return task_read

    def get_task(self, task_id: str) -> Optional[TaskProfileRead]:
        return self._tasks.get(task_id)

    def get_current_task(self) -> Optional[TaskProfileRead]:
        if self._current_task_id is None:
            return None
        return self._tasks.get(self._current_task_id)


task_service = TaskService()

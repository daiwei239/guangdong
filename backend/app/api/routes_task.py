from fastapi import APIRouter

from app.schemas.task_schema import TaskProfileCreate
from app.services.task_service import task_service

router = APIRouter(tags=["tasks"])


@router.post("/tasks")
def create_task(task: TaskProfileCreate):
    return task_service.create_task(task).dict()

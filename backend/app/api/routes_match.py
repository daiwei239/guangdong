from fastapi import APIRouter, HTTPException

from app.schemas.task_schema import TaskProfileCreate
from app.services.graph_service import graph_service
from app.services.matching_service import matching_service
from app.services.resource_service import resource_service
from app.services.task_service import task_service

router = APIRouter(tags=["match"])


@router.post("/match")
def match_task(task_profile: TaskProfileCreate):
    task = task_service.create_task(task_profile)
    resources = resource_service.get_resources()
    edges = resource_service.get_edges()
    if not resources or not edges:
        snapshot = resource_service.generate_snapshot()
        resources = snapshot["resources"]
        edges = snapshot["edges"]
    graph = graph_service.build_networkx_graph(resources, edges)
    result = matching_service.match_task(task, resources, edges, graph)
    return result.dict()


@router.get("/match/{task_id}")
def get_match_result(task_id: str):
    result = matching_service.get_result(task_id)
    if result is None:
        raise HTTPException(status_code=404, detail="match result not found")
    return result.dict()

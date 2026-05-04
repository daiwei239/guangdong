from fastapi import APIRouter

from app.services.graph_service import graph_service
from app.services.resource_service import resource_service

router = APIRouter(tags=["resources"])


@router.get("/resources")
def get_resources():
    return [resource.dict() for resource in resource_service.get_resources()]


@router.get("/resource-graph")
def get_resource_graph():
    resources = resource_service.get_resources()
    edges = resource_service.get_edges()
    return graph_service.build_graph_snapshot(resources, edges)

from fastapi import APIRouter

from app.services.graph_service import graph_service
from app.services.resource_service import resource_service
from app.utils.pydantic_compat import model_dump_compat

router = APIRouter(tags=["resources"])


@router.get("/resources")
def get_resources():
    resources = resource_service.get_resources()

    if not resources:
        snapshot = resource_service.generate_snapshot()
        resources = snapshot["resources"]

    return [model_dump_compat(resource) for resource in resources]


@router.get("/resource-graph")
def get_resource_graph():
    resources = resource_service.get_resources()
    edges = resource_service.get_edges()

    if not resources:
        snapshot = resource_service.generate_snapshot()
        resources = snapshot["resources"]
        edges = snapshot["edges"]

    return graph_service.build_graph_snapshot(resources, edges)
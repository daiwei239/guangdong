import time
from typing import Dict, List, Set

from fastapi import APIRouter

from app.services.graph_service import graph_service
from app.services.matching_service import matching_service
from app.services.resource_service import resource_service
from app.services.task_service import task_service
from app.services.websocket_service import websocket_service

router = APIRouter(tags=["simulate"])


PIPELINE_EVENTS = [
    "step_1_collecting_resource",
    "step_2_building_resource_graph",
    "step_3_extracting_task_requirement",
    "step_4_encoding_resource_graph",
    "step_5_searching_candidate_subgraph",
    "step_6_validating_match_result",
    "finished",
]


@router.post("/simulate")
async def simulate():
    pipeline_steps = []

    pipeline_steps.append(PIPELINE_EVENTS[0])
    await websocket_service.broadcast(PIPELINE_EVENTS[0], pipeline_steps)
    snapshot = resource_service.generate_snapshot()
    resources = snapshot["resources"]
    edges = snapshot["edges"]

    pipeline_steps.append(PIPELINE_EVENTS[1])
    await websocket_service.broadcast(PIPELINE_EVENTS[1], pipeline_steps)
    graph = graph_service.build_networkx_graph(resources, edges)
    graph_service.sync_to_neo4j(resources, edges)

    pipeline_steps.append(PIPELINE_EVENTS[2])
    await websocket_service.broadcast(PIPELINE_EVENTS[2], pipeline_steps)
    task = task_service.generate_task()

    pipeline_steps.append(PIPELINE_EVENTS[3])
    await websocket_service.broadcast(PIPELINE_EVENTS[3], pipeline_steps)

    pipeline_steps.append(PIPELINE_EVENTS[4])
    await websocket_service.broadcast(PIPELINE_EVENTS[4], pipeline_steps)
    match_result = matching_service.match_task(task, resources, edges, graph, pipeline_steps)

    pipeline_steps.append(PIPELINE_EVENTS[5])
    await websocket_service.broadcast(PIPELINE_EVENTS[5], pipeline_steps)

    pipeline_steps.append(PIPELINE_EVENTS[6])
    await websocket_service.broadcast(PIPELINE_EVENTS[6], pipeline_steps)

    candidate_node_ids = set()
    candidate_edge_ids = set()
    top1_node_ids = set(match_result.top1.nodes)
    top1_edge_ids = set(match_result.top1.edges)
    for candidate in match_result.candidates:
        candidate_node_ids.update(candidate.nodes)
        candidate_edge_ids.update(candidate.edges)

    return {
        "resource_snapshot": resource_service.build_snapshot_summary(),
        "task_profile": task.dict(),
        "resource_graph": graph_service.build_graph_snapshot(
            resources,
            edges,
            candidate_node_ids=candidate_node_ids,
            top1_node_ids=top1_node_ids,
            candidate_edge_ids=candidate_edge_ids,
            top1_edge_ids=top1_edge_ids,
        ),
        "candidates": [candidate.dict() for candidate in match_result.candidates],
        "top1": match_result.top1.dict(),
        "verification": match_result.verification.dict(),
        "pipeline_steps": pipeline_steps,
    }

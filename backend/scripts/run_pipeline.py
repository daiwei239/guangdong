from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.database import init_db
from app.schemas.resource_schema import ResourceSnapshotWrite
from app.schemas.task_schema import TaskProfileCreate
from app.services.graph_service import graph_service
from app.services.matching_service import matching_service
from app.services.resource_service import resource_service
from app.services.task_service import task_service


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def run_pipeline(resources_path: Path, task_path: Path) -> dict:
    init_db()

    resource_payload = ResourceSnapshotWrite.model_validate(load_json(resources_path))
    task_payload = TaskProfileCreate.model_validate(load_json(task_path))

    resource_service.set_snapshot(resource_payload.resources, resource_payload.edges)
    task = task_service.create_task(task_payload)

    resources = resource_service.get_resources()
    edges = resource_service.get_edges()
    graph = graph_service.build_networkx_graph(resources, edges)
    result = matching_service.match_task(task, resources, edges, graph)

    artifacts = matching_service.get_encoding_artifacts(task.task_id)
    return {
        "task": task.model_dump(),
        "result": result.model_dump(),
        "encoding_artifacts": artifacts,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the backend matching pipeline from JSON inputs.")
    parser.add_argument("--resources", required=True, type=Path, help="Path to a resource snapshot JSON file.")
    parser.add_argument("--task", required=True, type=Path, help="Path to a task profile JSON file.")
    parser.add_argument("--output", type=Path, help="Optional path to write the result JSON.")
    args = parser.parse_args()

    payload = run_pipeline(args.resources, args.task)
    text = json.dumps(payload, ensure_ascii=False, indent=2)

    if args.output is not None:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()

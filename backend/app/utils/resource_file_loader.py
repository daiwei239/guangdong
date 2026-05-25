import json
from pathlib import Path
from typing import List, Tuple
from app.schemas.resource_schema import ResourceNodeRead, ResourceEdgeRead

'''
从外部添加数据
'''

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data" / "processed"

RESOURCES_JSONL = DATA_DIR / "resources.jsonl"
EDGES_JSONL = DATA_DIR / "edges.jsonl"


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []

    records = []

    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()

            if not line:
                continue

            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"JSONL 解析失败：{path} 第 {line_no} 行"
                ) from exc

    return records


def load_resources_and_edges_from_files() -> Tuple[List[ResourceNodeRead], List[ResourceEdgeRead]]:
    resource_records = _read_jsonl(RESOURCES_JSONL)
    edge_records = _read_jsonl(EDGES_JSONL)

    resources = [ResourceNodeRead(**item) for item in resource_records]
    edges = [ResourceEdgeRead(**item) for item in edge_records]

    return resources, edges
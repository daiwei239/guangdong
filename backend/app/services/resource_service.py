from collections import Counter
from typing import Dict, List, Optional

from app.mock.mock_resource_generator import MockResourceGenerator
from app.mock.mock_topology_generator import MockTopologyGenerator
from app.schemas.resource_schema import ResourceEdgeRead, ResourceNodeRead
from app.utils.pydantic_compat import model_dump_compat


class ResourceService:
    def __init__(self) -> None:
        self.generator = MockResourceGenerator()
        self.topology_generator = MockTopologyGenerator()
        self._resources = []
        self._edges = []

    def generate_snapshot(self) -> Dict[str, List]:
        self._resources = self.generator.generate_resources()
        self._edges = self.topology_generator.generate_edges(self._resources)
        return {"resources": self._resources, "edges": self._edges}

    def set_snapshot(self, resources: List[ResourceNodeRead], edges: List[ResourceEdgeRead]) -> None:
        self._resources = list(resources)
        self._edges = list(edges)

    def get_resources(self) -> List[ResourceNodeRead]:
        return list(self._resources)

    def get_edges(self) -> List[ResourceEdgeRead]:
        return list(self._edges)

    def build_snapshot_summary(self) -> Dict:
        counts = Counter(resource.type for resource in self._resources)
        return {
            "total_nodes": len(self._resources),
            "total_edges": len(self._edges),
            "by_type": dict(counts),
            "resources": [model_dump_compat(resource) for resource in self._resources],
        }


resource_service = ResourceService()

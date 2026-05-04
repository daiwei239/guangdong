import random
from typing import List, Sequence, Tuple

from app.schemas.resource_schema import ResourceEdgeRead, ResourceNodeRead
from app.utils.id_generator import generate_id


class MockTopologyGenerator:
    RELATION_TYPES = [
        "CONNECTED_TO",
        "SAME_HOST",
        "SAME_RACK",
        "SHARES_MEMORY",
        "COMPETES_BANDWIDTH",
        "LOW_LATENCY_LINK",
        "SCHEDULING_DEPENDENCY",
    ]

    def generate_edges(self, resources: Sequence[ResourceNodeRead]) -> List[ResourceEdgeRead]:
        target_count = random.randint(50, 70)
        edges = []
        seen_pairs = set()

        while len(edges) < target_count:
            source, target = random.sample(list(resources), 2)
            pair = tuple(sorted([source.id, target.id]))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            relation_type = random.choice(self.RELATION_TYPES)
            latency = round(random.uniform(0.05, 8.0), 2)
            bandwidth = round(random.uniform(10, 400), 2)
            weight = round((bandwidth / max(latency, 0.1)) / 25.0, 3)
            edges.append(
                ResourceEdgeRead(
                    id=generate_id("edge"),
                    source=source.id,
                    target=target.id,
                    relation_type=relation_type,
                    bandwidth_gbps=bandwidth,
                    latency_ms=latency,
                    weight=weight,
                )
            )
        return edges

import logging
from collections import Counter
from typing import Dict, List

from sqlalchemy import delete, select

from app.core.database import SessionLocal
from app.mock.mock_resource_generator import MockResourceGenerator
from app.mock.mock_topology_generator import MockTopologyGenerator
from app.models.resource import ResourceEdgeORM, ResourceNodeORM
from app.schemas.resource_schema import ResourceEdgeRead, ResourceNodeRead
from app.utils.pydantic_compat import model_dump_compat


logger = logging.getLogger(__name__)


class ResourceService:
    def __init__(self) -> None:
        self.generator = MockResourceGenerator()
        self.topology_generator = MockTopologyGenerator()
        self._resources = []
        self._edges = []

    def generate_snapshot(self) -> Dict[str, List]:
        self._resources = self.generator.generate_resources()
        self._edges = self.topology_generator.generate_edges(self._resources)
        self._persist_snapshot()
        return {"resources": self._resources, "edges": self._edges}

    def set_snapshot(self, resources: List[ResourceNodeRead], edges: List[ResourceEdgeRead]) -> None:
        self._resources = list(resources)
        self._edges = list(edges)
        self._persist_snapshot()

    def get_resources(self) -> List[ResourceNodeRead]:
        if not self._resources:
            self._load_snapshot_from_db()
        return list(self._resources)

    def get_edges(self) -> List[ResourceEdgeRead]:
        if not self._edges:
            self._load_snapshot_from_db()
        return list(self._edges)

    def build_snapshot_summary(self) -> Dict:
        counts = Counter(resource.type for resource in self._resources)
        return {
            "total_nodes": len(self._resources),
            "total_edges": len(self._edges),
            "by_type": dict(counts),
            "resources": [model_dump_compat(resource) for resource in self._resources],
        }

    def _persist_snapshot(self) -> None:
        """将当前资源快照写入数据库，作为当前阶段的持久化主通路。"""
        try:
            with SessionLocal() as session:
                session.execute(delete(ResourceEdgeORM))
                session.execute(delete(ResourceNodeORM))
                session.add_all(
                    [
                        ResourceNodeORM(
                            id=resource.id,
                            name=resource.name,
                            type=resource.type,
                            cluster_id=resource.cluster_id,
                            host_id=resource.host_id,
                            topo_context=resource.topo_context,
                            static_attrs=resource.static_attrs,
                            dynamic_state=resource.dynamic_state,
                            semantic_tags=resource.semantic_tags,
                            created_at=resource.created_at,
                            updated_at=resource.updated_at,
                        )
                        for resource in self._resources
                    ]
                )
                session.add_all(
                    [
                        ResourceEdgeORM(
                            id=edge.id,
                            source=edge.source,
                            target=edge.target,
                            relation_type=edge.relation_type,
                            bandwidth_gbps=edge.bandwidth_gbps,
                            latency_ms=edge.latency_ms,
                            weight=edge.weight,
                        )
                        for edge in self._edges
                    ]
                )
                session.commit()
        except Exception as exc:  # pragma: no cover - 依赖外部数据库时允许降级
            logger.warning("failed to persist resource snapshot: %s", exc)

    def _load_snapshot_from_db(self) -> None:
        """在内存缓存为空时，从数据库恢复最近的资源快照。"""
        try:
            with SessionLocal() as session:
                resource_rows = session.execute(select(ResourceNodeORM)).scalars().all()
                edge_rows = session.execute(select(ResourceEdgeORM)).scalars().all()
        except Exception as exc:  # pragma: no cover
            logger.warning("failed to load resource snapshot from database: %s", exc)
            return

        self._resources = [
            ResourceNodeRead(
                id=row.id,
                name=row.name,
                type=row.type,
                cluster_id=row.cluster_id,
                host_id=row.host_id,
                topo_context=row.topo_context or {},
                static_attrs=row.static_attrs or {},
                dynamic_state=row.dynamic_state or {},
                semantic_tags=row.semantic_tags or [],
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            for row in resource_rows
        ]
        self._edges = [
            ResourceEdgeRead(
                id=row.id,
                source=row.source,
                target=row.target,
                relation_type=row.relation_type,
                bandwidth_gbps=row.bandwidth_gbps,
                latency_ms=row.latency_ms,
                weight=row.weight,
            )
            for row in edge_rows
        ]


resource_service = ResourceService()

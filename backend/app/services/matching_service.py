import logging
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import networkx as nx
import torch
from sqlalchemy import delete, desc, select
from torch.nn.parameter import UninitializedBuffer, UninitializedParameter

from app.algorithms.beam_search import BeamSearchSubgraphFinder
from app.algorithms.feature_builder import RESOURCE_INPUT_DIMS, build_mock_heterodata_from_resources
from app.algorithms.gnn_encoder import ResourceGraphEncoder
from app.core.database import SessionLocal
from app.models.match import CandidateSubgraphORM, MatchResultORM
from app.schemas.match_schema import MatchResponseSchema
from app.schemas.resource_schema import ResourceEdgeRead, ResourceNodeRead
from app.schemas.task_schema import TaskProfileRead
from app.services.scoring_service import scoring_service
from app.utils.id_generator import generate_id
from app.utils.pydantic_compat import model_dump_compat


logger = logging.getLogger(__name__)


class MatchingService:
    def __init__(self) -> None:
        self.finder = BeamSearchSubgraphFinder()
        self._results = {}
        self._encoding_artifacts = {}
        self.checkpoint_path = Path(__file__).resolve().parents[2] / "models" / "matcher_checkpoint.pt"
        self.resource_encoder = ResourceGraphEncoder(
            input_dims=RESOURCE_INPUT_DIMS,
            hidden_dim=64,
            out_dim=64,
            edge_attr_dim=5,
            num_layers=2,
            heads=2,
            dropout=0.1,
        )
        self._load_encoder_checkpoint()
        self.resource_encoder.eval()

    def match_task(
        self,
        task: TaskProfileRead,
        resources: Sequence[ResourceNodeRead],
        edges: Sequence[ResourceEdgeRead],
        graph: nx.Graph,
        pipeline_steps: Optional[List[str]] = None,
        full_graph_embedding: Optional[torch.Tensor] = None,
    ) -> MatchResponseSchema:
        pipeline_steps = list(pipeline_steps or [])
        resource_lookup = {resource.id: resource for resource in resources}
        full_graph_embedding = full_graph_embedding if full_graph_embedding is not None else self.encode_resource_graph(resources, edges, task.task_type)
        candidate_node_sets = self.finder.search(task, resources, graph)

        if not candidate_node_sets:
            available_ids = [resource.id for resource in resources[:6]]
            candidate_node_sets = [available_ids] * 3

        candidates = []
        candidate_embeddings = {}
        for index, node_ids in enumerate(candidate_node_sets[:3], start=1):
            signature = self._candidate_signature(node_ids)
            candidate_embeddings[signature] = self.encode_candidate_subgraph(task, resources, edges, node_ids)
            candidates.append(scoring_service.score_candidate(task, resource_lookup, graph, node_ids, index))

        candidates.sort(key=lambda candidate: candidate.final_score, reverse=True)
        for index, candidate in enumerate(candidates, start=1):
            candidate.rank = index
            candidate.is_top1 = index == 1

        while len(candidates) < 3:
            clone = candidates[-1].copy(deep=True)
            clone.subgraph_id = "{0}-alt{1}".format(clone.subgraph_id, len(candidates) + 1)
            clone.rank = len(candidates) + 1
            clone.is_top1 = False
            clone.final_score = max(0.0, round(clone.final_score - 1.5 * len(candidates), 2))
            clone.score = clone.final_score
            candidates.append(clone)

        top1 = candidates[0]
        verification = scoring_service.validate_top1(task, top1)
        result = MatchResponseSchema(
            task_id=task.task_id,
            candidates=candidates,
            top1=top1,
            verification=verification,
            pipeline_steps=pipeline_steps,
        )
        self._results[task.task_id] = result
        self._encoding_artifacts[task.task_id] = {
            "encoder_used": True,
            "task_type": task.task_type,
            "full_graph_embedding": full_graph_embedding.squeeze(0).detach().cpu().tolist(),
            "candidate_embeddings": candidate_embeddings,
            "top1_embedding": candidate_embeddings.get(self._candidate_signature(top1.nodes), []),
        }
        self._persist_result(result)
        return result

    def get_result(self, task_id: str) -> Optional[MatchResponseSchema]:
        result = self._results.get(task_id)
        if result is not None:
            return result
        return self._load_result_from_db(task_id)

    def _load_encoder_checkpoint(self) -> None:
        if not self.checkpoint_path.exists():
            return
        checkpoint = torch.load(self.checkpoint_path, map_location="cpu")
        resource_encoder_state = checkpoint.get("resource_encoder_state_dict")
        configured_edge_types = checkpoint.get("resource_encoder_edge_types") or []
        if configured_edge_types:
            self.resource_encoder._ensure_hetero_layers(configured_edge_types)
        if resource_encoder_state is not None:
            self._safe_load_state_dict(resource_encoder_state)
            return

        full_model_state = checkpoint.get("model_state_dict")
        if not full_model_state:
            return

        # 兼容旧格式：从完整 matcher 模型权重中过滤 resource_encoder 前缀。
        filtered_state = {}
        prefix = "resource_encoder."
        for key, value in full_model_state.items():
            if key.startswith(prefix):
                filtered_state[key[len(prefix) :]] = value
        if filtered_state:
            self._safe_load_state_dict(filtered_state)

    def _safe_load_state_dict(self, state_dict: Dict[str, torch.Tensor]) -> None:
        current_state = self.resource_encoder.state_dict()
        compatible_state = {}
        for key, value in state_dict.items():
            current_value = current_state.get(key)
            if current_value is None:
                continue
            if isinstance(current_value, (UninitializedParameter, UninitializedBuffer)):
                continue
            if current_value.shape != value.shape:
                continue
            compatible_state[key] = value
        if compatible_state:
            self.resource_encoder.load_state_dict(compatible_state, strict=False)

    def encode_resource_graph(
        self,
        resources: Sequence[ResourceNodeRead],
        edges: Sequence[ResourceEdgeRead],
        task_type: Optional[str] = None,
    ) -> torch.Tensor:
        data = build_mock_heterodata_from_resources(resources, edges)
        with torch.no_grad():
            z_subgraph, _ = self.resource_encoder(data, task_type=task_type)
        return z_subgraph

    def encode_candidate_subgraph(
        self,
        task: TaskProfileRead,
        resources: Sequence[ResourceNodeRead],
        edges: Sequence[ResourceEdgeRead],
        node_ids: Sequence[str],
    ) -> List[float]:
        selected_nodes = [resource for resource in resources if resource.id in node_ids]
        selected_node_ids = {resource.id for resource in selected_nodes}
        selected_edges = [edge for edge in edges if edge.source in selected_node_ids and edge.target in selected_node_ids]
        data = build_mock_heterodata_from_resources(selected_nodes, selected_edges)
        with torch.no_grad():
            z_subgraph, _ = self.resource_encoder(data, task_type=task.task_type)
        return z_subgraph.squeeze(0).detach().cpu().tolist()

    def get_encoding_artifacts(self, task_id: str) -> Optional[Dict]:
        return self._encoding_artifacts.get(task_id)

    def _candidate_signature(self, node_ids: Sequence[str]) -> Tuple[str, ...]:
        return tuple(sorted(node_ids))

    def _persist_result(self, result: MatchResponseSchema) -> None:
        """将候选子图与最终匹配结果写入数据库。"""
        try:
            with SessionLocal() as session:
                session.execute(delete(CandidateSubgraphORM).where(CandidateSubgraphORM.task_id == result.task_id))
                session.execute(delete(MatchResultORM).where(MatchResultORM.task_id == result.task_id))
                session.add_all(
                    [
                        CandidateSubgraphORM(
                            id=candidate.subgraph_id,
                            task_id=result.task_id,
                            rank=candidate.rank,
                            nodes=candidate.nodes,
                            edges=candidate.edges,
                            score=candidate.final_score,
                            score_breakdown={
                                "capacity_score": candidate.capacity_score,
                                "performance_score": candidate.performance_score,
                                "topology_score": candidate.topology_score,
                                "qos_score": candidate.qos_score,
                                "communication_cost": candidate.communication_cost,
                                "energy_cost": candidate.energy_cost,
                                "load_cost": candidate.load_cost,
                                "final_score": candidate.final_score,
                            },
                            is_top1=candidate.is_top1,
                        )
                        for candidate in result.candidates
                    ]
                )
                session.add(
                    MatchResultORM(
                        id=generate_id("match"),
                        task_id=result.task_id,
                        top1_subgraph_id=result.top1.subgraph_id,
                        verification=model_dump_compat(result.verification),
                        top1_score=result.top1.final_score,
                        pipeline_steps=result.pipeline_steps,
                    )
                )
                session.commit()
        except Exception as exc:  # pragma: no cover
            logger.warning("failed to persist match result: %s", exc)

    def _load_result_from_db(self, task_id: str) -> Optional[MatchResponseSchema]:
        try:
            with SessionLocal() as session:
                match_row = (
                    session.execute(
                        select(MatchResultORM).where(MatchResultORM.task_id == task_id).order_by(desc(MatchResultORM.created_at))
                    )
                    .scalars()
                    .first()
                )
                candidate_rows = (
                    session.execute(
                        select(CandidateSubgraphORM).where(CandidateSubgraphORM.task_id == task_id).order_by(CandidateSubgraphORM.rank)
                    )
                    .scalars()
                    .all()
                )
        except Exception as exc:  # pragma: no cover
            logger.warning("failed to load match result from database: %s", exc)
            return None

        if match_row is None or not candidate_rows:
            return None

        candidates = []
        top1 = None
        for row in candidate_rows:
            score_breakdown = row.score_breakdown or {}
            candidate = {
                "subgraph_id": row.id,
                "rank": row.rank,
                "nodes": row.nodes or [],
                "edges": row.edges or [],
                "score": row.score,
                "capacity_score": score_breakdown.get("capacity_score", 0.0),
                "performance_score": score_breakdown.get("performance_score", 0.0),
                "topology_score": score_breakdown.get("topology_score", 0.0),
                "qos_score": score_breakdown.get("qos_score", 0.0),
                "communication_cost": score_breakdown.get("communication_cost", 0.0),
                "energy_cost": score_breakdown.get("energy_cost", 0.0),
                "load_cost": score_breakdown.get("load_cost", 0.0),
                "final_score": score_breakdown.get("final_score", row.score),
                "is_top1": row.is_top1,
            }
            candidates.append(candidate)
            if row.is_top1:
                top1 = candidate

        if top1 is None:
            top1 = dict(candidates[0])
            top1["is_top1"] = True
            candidates[0]["is_top1"] = True

        result = MatchResponseSchema(
            task_id=task_id,
            candidates=candidates,
            top1=top1,
            verification=match_row.verification,
            pipeline_steps=match_row.pipeline_steps or [],
        )
        self._results[task_id] = result
        return result


matching_service = MatchingService()

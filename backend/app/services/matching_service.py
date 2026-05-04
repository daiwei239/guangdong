from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import networkx as nx
import torch

from app.algorithms.beam_search import BeamSearchSubgraphFinder
from app.algorithms.feature_builder import RESOURCE_INPUT_DIMS, build_mock_heterodata_from_resources
from app.algorithms.gnn_encoder import ResourceGraphEncoder
from app.schemas.match_schema import MatchResponseSchema
from app.schemas.resource_schema import ResourceEdgeRead, ResourceNodeRead
from app.schemas.task_schema import TaskProfileRead
from app.services.scoring_service import scoring_service


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
        return result

    def get_result(self, task_id: str) -> Optional[MatchResponseSchema]:
        return self._results.get(task_id)

    def _load_encoder_checkpoint(self) -> None:
        if not self.checkpoint_path.exists():
            return
        checkpoint = torch.load(self.checkpoint_path, map_location="cpu")
        resource_encoder_state = checkpoint.get("resource_encoder_state_dict")
        configured_edge_types = checkpoint.get("resource_encoder_edge_types") or []
        if configured_edge_types:
            self.resource_encoder._ensure_hetero_layers(configured_edge_types)
        if resource_encoder_state is not None:
            self.resource_encoder.load_state_dict(resource_encoder_state, strict=False)
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
            self.resource_encoder.load_state_dict(filtered_state, strict=False)

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


matching_service = MatchingService()

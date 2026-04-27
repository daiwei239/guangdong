from resource_mapping.constants import EDGE_TYPES, NODE_TYPES
from resource_mapping.graph_builder import ResourceGraphBuilder


def test_graph_builder_contains_all_types() -> None:
    from conftest import sample_edges, sample_resources

    data = ResourceGraphBuilder().build(sample_resources(), sample_edges())
    for node_type in NODE_TYPES:
        assert node_type in data.node_types
        assert data[node_type].x.ndim == 2
    for edge_type in EDGE_TYPES:
        assert edge_type in data.edge_types

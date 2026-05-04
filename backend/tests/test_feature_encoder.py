import torch

from app.algorithms.feature_builder import (
    RESOURCE_INPUT_DIMS,
    ResourceFeatureBuilder,
    build_raw_feature_tensors,
)
from app.algorithms.feature_encoder import ResourceFeatureEncoder
from app.mock.mock_resource_generator import MockResourceGenerator


def test_feature_encoder_maps_all_resource_types_to_same_hidden_dim() -> None:
    encoder = ResourceFeatureEncoder(input_dims=RESOURCE_INPUT_DIMS, hidden_dim=64)
    x_dict = {
        "CPU": torch.rand(3, RESOURCE_INPUT_DIMS["CPU"]),
        "GPU": torch.rand(2, RESOURCE_INPUT_DIMS["GPU"]),
        "FPGA": torch.rand(1, RESOURCE_INPUT_DIMS["FPGA"]),
        "MEMORY": torch.rand(4, RESOURCE_INPUT_DIMS["MEMORY"]),
        "STORAGE": torch.rand(2, RESOURCE_INPUT_DIMS["STORAGE"]),
        "NIC": torch.rand(2, RESOURCE_INPUT_DIMS["NIC"]),
        "SWITCH": torch.rand(1, RESOURCE_INPUT_DIMS["SWITCH"]),
    }

    encoded = encoder(x_dict)

    for resource_type, tensor in encoded.items():
        assert tensor.shape[-1] == 64
        assert tensor.shape[0] == x_dict[resource_type].shape[0]


def test_feature_builder_fills_missing_fields_with_defaults() -> None:
    resources = MockResourceGenerator().generate_resources()
    gpu = next(resource for resource in resources if resource.type == "GPU")
    gpu.static_attrs.pop("memory_total", None)
    gpu.dynamic_state.pop("memory_free", None)

    vector = ResourceFeatureBuilder().build_feature_vector(gpu)

    assert len(vector) == RESOURCE_INPUT_DIMS["GPU"]
    assert all(0.0 <= value <= 1.0 for value in vector)


def test_build_raw_feature_tensors_groups_resources_by_type() -> None:
    resources = MockResourceGenerator().generate_resources()

    x_dict = build_raw_feature_tensors(resources)

    assert set(x_dict) == set(RESOURCE_INPUT_DIMS)
    assert x_dict["CPU"].shape[1] == RESOURCE_INPUT_DIMS["CPU"]
    assert x_dict["GPU"].shape[1] == RESOURCE_INPUT_DIMS["GPU"]

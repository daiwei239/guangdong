from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.input.resource_input import resource_input_layer
from app.input.adapters.huawei_management_adapter import FusionDirectorAdapter, HuaweiManagementInputAdapter, JsonPlatformAdapter
from app.output.resource_output import resource_output_layer
from app.process.normalizer import resource_process_layer
from app.schemas.resource_schema import SensedResourceState


def run_pipeline_from_state(sensed_state: SensedResourceState, output_dir: Path | None = None) -> dict:
    normalized_state = resource_process_layer.normalize(sensed_state)
    outputs = resource_output_layer.build_outputs(normalized_state)
    if output_dir is not None:
        resource_output_layer.write_outputs(outputs, output_dir)
    return resource_output_layer.dump_outputs(outputs)


def run_pipeline(input_path: Path, output_dir: Path | None = None) -> dict:
    return run_pipeline_from_state(resource_input_layer.read_resource_state(input_path), output_dir=output_dir)


def build_huawei_management_adapter(config: dict) -> HuaweiManagementInputAdapter:
    adapters = []

    for platform_config in config.get("platforms", []):
        if platform_config["source_type"] == "fusiondirector":
            adapters.append(
                FusionDirectorAdapter(
                    source_name=platform_config.get("source_name", "fusiondirector"),
                    base_url=platform_config.get("base_url"),
                    file_path=platform_config.get("file_path"),
                    path=platform_config.get("path", "/api/resource-events"),
                    username=platform_config.get("username"),
                    password=platform_config.get("password"),
                    bearer_token=platform_config.get("bearer_token"),
                    verify_tls=platform_config.get("verify_tls", True),
                )
            )
        else:
            adapters.append(
                JsonPlatformAdapter(
                    source_type=platform_config["source_type"],
                    source_name=platform_config.get("source_name", platform_config["source_type"]),
                    base_url=platform_config.get("base_url"),
                    file_path=platform_config.get("file_path"),
                    path=platform_config.get("path", "/"),
                    username=platform_config.get("username"),
                    password=platform_config.get("password"),
                    bearer_token=platform_config.get("bearer_token"),
                    verify_tls=platform_config.get("verify_tls", True),
                )
            )

    return HuaweiManagementInputAdapter(
        adapters=adapters,
        timestamp=config.get("timestamp"),
        trace_id=config.get("trace_id"),
    )


def resolve_huawei_management_config_paths(config: dict, config_dir: Path) -> dict:
    resolved = dict(config)
    platforms = []
    for platform_config in config.get("platforms", []):
        platform = dict(platform_config)
        file_path = platform.get("file_path")
        if file_path:
            path = Path(file_path)
            if not path.is_absolute():
                path = config_dir / path
            platform["file_path"] = str(path)
        platforms.append(platform)
    resolved["platforms"] = platforms
    return resolved


def run_pipeline_from_huawei_management(config_path: Path, output_dir: Path | None = None) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config = resolve_huawei_management_config_paths(config, config_path.parent)
    sensed_state = build_huawei_management_adapter(config).fetch_state()
    return run_pipeline_from_state(sensed_state, output_dir=output_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the three-layer resource-state data pipeline.")
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--input", "--resources", dest="input_path", type=Path, help="Path to a resource state JSON file.")
    input_group.add_argument("--huawei-management-config", type=Path, help="Path to a JSON config for Huawei management platform inputs (FusionDirector, MindX, MindCluster, etc.).")
    parser.add_argument("--output-dir", type=Path, help="Optional directory to write ResourceProfile, ResourceState, and ResourceTopology JSON files.")
    parser.add_argument("--output", type=Path, help="Optional path to write a combined preview JSON.")
    args = parser.parse_args()

    if args.huawei_management_config:
        payload = run_pipeline_from_huawei_management(args.huawei_management_config, output_dir=args.output_dir)
    else:
        payload = run_pipeline(args.input_path, output_dir=args.output_dir)

    text = json.dumps(payload, ensure_ascii=False, indent=2)

    if args.output is not None:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()

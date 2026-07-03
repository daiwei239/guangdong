from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.input.resource_input import resource_input_layer
from app.output.resource_output import resource_output_layer
from app.process.normalizer import resource_process_layer


def run_pipeline(input_path: Path, output_dir: Path | None = None) -> dict:
    sensed_state = resource_input_layer.read_resource_state(input_path)
    normalized_state = resource_process_layer.normalize(sensed_state)
    outputs = resource_output_layer.build_outputs(normalized_state)
    if output_dir is not None:
        resource_output_layer.write_outputs(outputs, output_dir)
    return resource_output_layer.dump_outputs(outputs)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the three-layer resource-state data pipeline.")
    parser.add_argument("--input", "--resources", dest="input_path", required=True, type=Path, help="Path to a resource state JSON file.")
    parser.add_argument("--output-dir", type=Path, help="Optional directory to write ResourceProfile, ResourceState, and ResourceTopology JSON files.")
    parser.add_argument("--output", type=Path, help="Optional path to write a combined preview JSON.")
    args = parser.parse_args()

    payload = run_pipeline(args.input_path, output_dir=args.output_dir)
    text = json.dumps(payload, ensure_ascii=False, indent=2)

    if args.output is not None:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()

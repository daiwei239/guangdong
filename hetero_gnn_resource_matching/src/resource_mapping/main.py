"""Convenience entrypoint."""

from __future__ import annotations


def main() -> None:
    """Print available commands."""

    print(
        "Step packages:\n"
        "  step_01_resource_description: data schemas, I/O, feature constants\n"
        "  step_02_resource_graph: HeteroData graph construction\n"
        "  step_03_task_expression: task requirement vectorization\n"
        "  step_04_candidate_gnn_matching: candidate search, dataset, model, training\n"
        "  step_05_ranking_verification: inference, ranking, verification, reports\n\n"
        "Commands:\n"
        "  python -m resource_mapping.step_04_candidate_gnn_matching.train\n"
        "  python -m resource_mapping.step_05_ranking_verification.infer\n"
        "  python -m resource_mapping.step_05_ranking_verification.evaluate\n"
        "  python -m resource_mapping.step_05_ranking_verification.visualize\n"
        "  python -m resource_mapping.step_05_ranking_verification.web_demo"
    )


if __name__ == "__main__":
    main()

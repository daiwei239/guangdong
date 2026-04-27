# Backend Step Layout

The backend mirrors the five-step technical route used by the visual frontend.
The primary implementations live in the step folders below. Legacy top-level
wrappers were removed to avoid duplicate files; import from the step packages
directly.

## 1. `step_01_resource_description`

Resource collection, unified schema and reusable data utilities.

- `constants.py`: node types, edge types and feature field definitions
- `schemas.py`: typed dataclasses for resources, edges, tasks and candidates
- `io_utils.py`: JSON/YAML I/O, path resolution, device and seed helpers
- `feature_normalizer.py`: per-type feature normalization

## 2. `step_02_resource_graph`

Global heterogeneous resource graph construction.

- `graph_builder.py`: converts raw resources and edges into PyG `HeteroData`

## 3. `step_03_task_expression`

Multi-modal task requirement expression.

- `task_vectorizer.py`: converts task dictionaries into fixed-length vectors

## 4. `step_04_candidate_gnn_matching`

Candidate resource subnet search and task-conditioned GNN matching.

- `candidate_generator.py`: heuristic candidate subnet generation
- `dataset.py`: task-candidate supervised dataset
- `label_generator.py`: pseudo-label generation for candidates
- `model.py`: HGT encoder, task encoder, pooler and scorer
- `losses.py`: BCE and pairwise ranking losses
- `train.py`: training command implementation

## 5. `step_05_ranking_verification`

Ranking, verification and output.

- `infer.py`: Top-K inference command implementation
- `evaluate.py`: evaluation metrics command implementation
- `verify.py`: rule-based capacity, performance, topology and QoS checks
- `visualize.py`: static evaluation report generation
- `web_demo.py`: interactive local web demo

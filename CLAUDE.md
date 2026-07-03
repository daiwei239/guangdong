# CLAUDE.md

This repository is now script-driven and backend-only.

## Project Overview

The codebase focuses on heterogeneous resource matching, graph construction, feature encoding, GNN encoding, candidate search, and scoring.

## Commands

```bash
pip install -r requirements.txt
cd backend && python scripts/run_pipeline.py --resources path/to/resources.json --task path/to/task.json
```

## Layout

```text
backend/app/
  core/       - config and database setup
  models/     - SQLAlchemy models
  schemas/    - Pydantic schemas
  services/   - graph, resource, task, matching, scoring
  algorithms/ - graph building, feature encoding, GNN, beam search, scoring
  utils/      - shared helpers
```

## Notes

- No FastAPI route layer remains.
- No frontend, simulation, or mock-data workflow remains.
- Use `backend/scripts/run_pipeline.py` as the main execution entrypoint.

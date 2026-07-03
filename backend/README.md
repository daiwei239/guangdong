# Backend

当前后端通过脚本直接运行匹配流程，不再提供 HTTP 服务。

## Main Entry

```bash
python scripts/run_pipeline.py --resources path/to/resources.json --task path/to/task.json
```

## Active Modules

- `app/services/resource_service.py`
- `app/services/task_service.py`
- `app/services/graph_service.py`
- `app/services/matching_service.py`
- `app/algorithms/gnn_encoder.py`

## Removed

- `app/api/`
- `app/main.py`
- FastAPI / uvicorn runtime
- frontend integration

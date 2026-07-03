# Heterogeneous Resource Mapping Backend

本项目现在是一个脚本驱动的后端仓库，专注于异构资源匹配流程本身，不再提供 HTTP API。

## Scope

- 资源快照建模与持久化
- 任务建模与持久化
- NetworkX 资源图构建
- 特征构建与特征编码
- 异构 GNN 资源图编码
- 候选子图搜索与评分
- 脚本方式执行完整匹配流程

## Run

```bash
pip install -r requirements.txt
cd backend
python scripts/run_pipeline.py --resources path/to/resources.json --task path/to/task.json
```

可选输出文件：

```bash
python scripts/run_pipeline.py --resources path/to/resources.json --task path/to/task.json --output outputs/result.json
```

## Input Format

`resources.json`:

```json
{
  "resources": [],
  "edges": []
}
```

`task.json`:

```json
{
  "task_id": "task-001",
  "task_type": "计算密集型",
  "dag_nodes": [],
  "compute_req": {},
  "memory_req": {},
  "storage_req": {},
  "network_req": {},
  "energy_limit": 1000,
  "qos_deadline_sec": 60,
  "priority": 1,
  "constraints": {}
}
```

## Notes

- `backend/scripts/run_pipeline.py` 是当前主入口。
- FastAPI、路由层、WebSocket、前端和 mock 演示链路都已经移除。
- GNN 核心实现仍在 `backend/app/algorithms/gnn_encoder.py`。

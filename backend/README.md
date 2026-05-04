# Semi-Real Backend

面向前端大屏的第二阶段后端骨架，负责把“前端纯模拟”升级为“半真实后端”：

- 生成异构资源节点与拓扑边
- 构建 NetworkX 内存资源图
- 生成任务需求画像
- 使用规则筛选 + Beam Search 搜索候选资源子网
- 进行规则评分与 Top-1 验证
- 通过 REST API 和 WebSocket 输出给前端

当前阶段不做真实 GNN 训练，不接 Slurm/Kubernetes，只为后续接入 PyTorch Geometric / DGL / HeteroGNN 预留清晰结构。

## 项目结构

```text
backend/
  app/
    main.py
    core/
    models/
    schemas/
    services/
    algorithms/
    api/
    mock/
    utils/
  tests/
  docker-compose.yml
  Dockerfile
  requirements.txt
  README.md
```

## 技术说明

- 运行时主图引擎：`NetworkX`
- 图数据库接入：`Neo4j`，不可用时自动降级
- 结构化存储：`SQLAlchemy ORM`
- 缓存/事件扩展：`Redis` 预留
- 指标：`prometheus_client`，提供 `/metrics`
- 推送：`WebSocket /ws/pipeline`

## 数据模型

PostgreSQL ORM 已包含以下表模型：

- `resource_nodes`
- `resource_edges`
- `task_profiles`
- `candidate_subgraphs`
- `match_results`

## 核心接口

### `GET /health`

返回服务状态。

### `POST /api/simulate`

一次性完成：

- 生成 36 个资源节点
- 生成 50-70 条资源边
- 生成 1 个任务需求画像
- 搜索 3 个候选子网
- 输出 Top-1、评分和验证结果

返回结构：

```json
{
  "resource_snapshot": {},
  "task_profile": {},
  "resource_graph": {
    "nodes": [],
    "edges": []
  },
  "candidates": [],
  "top1": {},
  "verification": {},
  "pipeline_steps": []
}
```

### `GET /api/resources`

返回当前资源节点列表。

### `GET /api/resource-graph`

返回当前资源图节点与边，包含前端大屏需要的高亮字段。

### `POST /api/tasks`

提交任务需求画像。

### `POST /api/match`

输入任务画像，返回候选子网与 Top-1 匹配结果。

### `GET /api/match/{task_id}`

查询指定任务的匹配结果。

### `WebSocket /ws/pipeline`

流程状态推送事件：

- `step_1_collecting_resource`
- `step_2_building_resource_graph`
- `step_3_extracting_task_requirement`
- `step_4_encoding_resource_graph`
- `step_5_searching_candidate_subgraph`
- `step_6_validating_match_result`
- `finished`

## 本地环境

推荐：

- Python `3.11+`
- 虚拟环境或 Conda

你当前要求使用本地 Conda 的 `torch_gpu` 环境；如果该环境仍为 Python 3.9，建议后续升级到 3.11+，以完全符合本项目目标技术栈。

## 安装依赖

```bash
pip install -r requirements.txt
```

## 本地启动

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Docker 启动

```bash
docker compose up --build
```

## 测试

```bash
pytest tests/test_resource_graph.py tests/test_matching.py -v
```

## 测试模拟接口

```bash
curl -X POST http://localhost:8000/api/simulate
```

## Prometheus 接入

已预留 `/metrics` 接口，当前包含以下指标：

- `resource_node_count`
- `resource_edge_count`
- `match_request_total`
- `match_latency_seconds`
- `candidate_subgraph_count`
- `top1_score`

Prometheus 示例抓取配置：

```yaml
scrape_configs:
  - job_name: semi-real-backend
    static_configs:
      - targets: ["localhost:8000"]
```

## 后续可扩展方向

- 把规则评分替换为 GNN 编码后的 learned scorer
- 将候选子网搜索升级为 PyG / DGL 图推理
- 接入真实 PostgreSQL 持久化与历史回放
- 对接 Slurm/Kubernetes 提交器

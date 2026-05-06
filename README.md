# Heterogeneous Resource Mapping

这个项目是一个异构资源匹配演示系统：前端用 React + Vite 展示资源图、匹配流程和候选结果；后端用 FastAPI 生成模拟资源、构建资源图、执行任务匹配、输出 API 和 WebSocket 流程事件。

## 项目结构

```text
guangdong/
  backend/                 # FastAPI 后端服务
  hetero_gnn/              # React + Vite 前端
  docs/                    # 项目文档
  projects/                # 项目材料或阶段性文件
  requirement.txt          # 根目录安装入口，转发到 backend/requirements.txt
  requirements.txt         # 标准根目录安装入口，转发到 backend/requirements.txt
  README.md                # 当前说明文档
```

## 当前运行步骤

### 1. 准备 Python 环境

建议使用 Python 3.11+。

从项目根目录安装后端依赖：

```bash
pip install -r requirements.txt
```

也可以进入后端目录安装：

```bash
cd backend
pip install -r requirements.txt
```

依赖清单在 `backend/requirements.txt`，包括 FastAPI、SQLAlchemy、PostgreSQL/Neo4j/Redis 客户端、NetworkX、PyTorch、PyTorch Geometric、Prometheus、pytest 等。

### 2. 启动后端

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

启动后可以检查：

```bash
curl http://localhost:8000/health
```

后端默认会使用本地 SQLite 配置；如果需要 PostgreSQL、Neo4j、Redis，可以使用 `.env` 或 Docker Compose。

### 3. 使用 Docker Compose 启动后端相关服务

```bash
cd backend
copy .env.example .env
docker compose up --build
```

Docker Compose 会启动：

- `backend`: FastAPI 服务
- `postgres`: PostgreSQL
- `neo4j`: 图数据库
- `redis`: Redis

常用端口由 `.env` 控制，默认后端端口是 `8000`。

### 4. 准备前端环境

```bash
cd hetero_gnn
npm install
```

前端依赖在 `hetero_gnn/package.json`，当前主要包括：

- `react`
- `react-dom`
- `framer-motion`
- `lucide-react`
- `vite`
- `typescript`
- `tailwindcss`

### 5. 启动前端

```bash
cd hetero_gnn
npm run dev
```

Vite 配置在 `hetero_gnn/vite.config.ts`，默认监听：

```text
http://localhost:5173
```

### 6. 构建前端

```bash
cd hetero_gnn
npm run build
```

当前构建流程是：

```text
tsc -b && vite build
```

### 7. 运行后端测试

```bash
cd backend
pytest tests/ -v
```

当前测试覆盖资源图、匹配逻辑、特征构建、特征编码和 GNN 编码。

### 8. 训练和推理脚本

训练匹配模型：

```bash
cd backend
python scripts/train_matcher.py
```

运行推理示例：

```bash
cd backend
python scripts/infer_matcher.py
```

模型文件位于：

```text
backend/models/matcher_checkpoint.pt
```

## 后端结构

```text
backend/
  app/
    main.py                         # FastAPI 应用入口，注册 CORS、metrics、路由
    api/
      routes_resource.py            # 资源列表和资源图 API
      routes_task.py                # 任务创建 API
      routes_match.py               # 匹配 API
      routes_simulate.py            # 全流程模拟 API
      routes_ws.py                  # WebSocket 流程事件 API
    core/
      config.py                     # 环境变量和应用配置
      database.py                   # SQLAlchemy 数据库连接和表初始化
      neo4j_client.py               # Neo4j 同步客户端
      redis_client.py               # Redis 客户端
    models/
      resource.py                   # 资源 ORM 模型
      task.py                       # 任务 ORM 模型
      match.py                      # 匹配结果 ORM 模型
    schemas/
      resource_schema.py            # 资源输入输出结构
      task_schema.py                # 任务输入输出结构
      match_schema.py               # 匹配结果结构
    services/
      resource_service.py           # 资源生成、缓存、持久化
      task_service.py               # 任务生成、创建、查询
      graph_service.py              # NetworkX 图构建和 Neo4j 同步
      matching_service.py           # 匹配主流程、GNN 编码、结果保存
      scoring_service.py            # 候选子图评分服务
      websocket_service.py          # WebSocket 连接和广播
    algorithms/
      graph_builder.py              # 资源图和边关系构建
      feature_builder.py            # 节点/边/任务特征构建
      feature_encoder.py            # 资源特征编码
      gnn_encoder.py                # 异构图 GNN 编码，PyG 不可用时有 fallback
      task_encoder.py               # 任务特征编码
      matcher_model.py              # 任务-资源匹配模型
      beam_search.py                # 候选子图搜索
      rule_filter.py                # 规则过滤
      score.py                      # 容量、性能、拓扑、成本评分
    mock/
      mock_resource_generator.py    # 模拟资源生成
      mock_task_generator.py        # 模拟任务生成
      mock_topology_generator.py    # 模拟拓扑边生成
    utils/
      id_generator.py               # ID 生成
      normalizer.py                 # 数值归一化工具
      pydantic_compat.py            # Pydantic v1/v2 兼容工具
  scripts/
    train_matcher.py                # 训练脚本
    infer_matcher.py                # 推理脚本
  tests/
    test_resource_graph.py
    test_matching.py
    test_feature_builder.py
    test_feature_encoder.py
    test_gnn_encoder.py
  models/
    matcher_checkpoint.pt
  Dockerfile
  docker-compose.yml
  requirements.txt
  .env.example
```

## 后端当前流程

### 1. 资源生成

`resource_service.generate_snapshot()` 调用 mock 生成器，生成 CPU、GPU、FPGA、MEMORY、STORAGE、NIC、SWITCH 等资源节点，以及资源之间的拓扑边。

相关文件：

- `backend/app/services/resource_service.py`
- `backend/app/mock/mock_resource_generator.py`
- `backend/app/mock/mock_topology_generator.py`

### 2. 构建资源图

资源节点和边会被 `graph_service` 转成 NetworkX 图，并可同步到 Neo4j。

相关文件：

- `backend/app/services/graph_service.py`
- `backend/app/algorithms/graph_builder.py`
- `backend/app/core/neo4j_client.py`

### 3. 生成或接收任务

任务可以通过 `/api/tasks` 创建，也可以在 `/api/simulate` 中由 `task_service.generate_task()` 自动生成。

相关文件：

- `backend/app/services/task_service.py`
- `backend/app/mock/mock_task_generator.py`
- `backend/app/schemas/task_schema.py`

### 4. 特征构建和 GNN 编码

`feature_builder` 会把资源、边和任务转成数值特征。`gnn_encoder` 使用 PyTorch Geometric 的 `HeteroConv`/`GATConv` 编码异构资源图；如果 PyG 不可用，会走 fallback 投影路径。

相关文件：

- `backend/app/algorithms/feature_builder.py`
- `backend/app/algorithms/feature_encoder.py`
- `backend/app/algorithms/gnn_encoder.py`
- `backend/app/algorithms/task_encoder.py`

### 5. 搜索候选子图

`BeamSearchSubgraphFinder` 在资源图中搜索候选资源子图，`RuleFilter` 负责规则约束过滤。

相关文件：

- `backend/app/algorithms/beam_search.py`
- `backend/app/algorithms/rule_filter.py`

### 6. 评分和 Top-1 输出

候选子图会计算容量、性能、拓扑和成本分数，最后输出 Top-1。

核心公式：

```text
S(t,k) = alpha * Mcap(t,k) + beta * Mperf(t,k) + gamma * Mtopo(t,k) - lambda * Cost(k)
```

默认权重：

```text
alpha = 0.35
beta = 0.35
gamma = 0.20
lambda = 0.10
```

相关文件：

- `backend/app/algorithms/score.py`
- `backend/app/services/scoring_service.py`
- `backend/app/services/matching_service.py`

### 7. WebSocket 推送流程事件

`/api/simulate` 会按步骤广播流水线事件到 `/ws/pipeline`。

当前事件：

```text
step_1_collecting_resource
step_2_building_resource_graph
step_3_extracting_task_requirement
step_4_encoding_resource_graph
step_5_searching_candidate_subgraph
step_6_validating_match_result
finished
```

相关文件：

- `backend/app/api/routes_simulate.py`
- `backend/app/api/routes_ws.py`
- `backend/app/services/websocket_service.py`

## API 列表

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/health` | 健康检查 |
| GET | `/metrics` | Prometheus 指标 |
| GET | `/api/resources` | 获取当前资源列表 |
| GET | `/api/resource-graph` | 获取资源图快照 |
| POST | `/api/tasks` | 创建任务 |
| POST | `/api/match` | 创建任务并执行匹配 |
| GET | `/api/match/{task_id}` | 查询指定任务的匹配结果 |
| POST | `/api/simulate` | 生成资源、任务并执行完整模拟流程 |
| WS | `/ws/pipeline` | 接收流程步骤事件 |

## 前端结构

```text
hetero_gnn/
  HeterogeneousResourceMappingPage.tsx  # 核心页面和交互逻辑
  src/
    main.tsx                            # React 挂载入口
    App.tsx                             # 页面入口组件
    index.css                           # Tailwind 和全局样式
  package.json                          # 前端依赖和脚本
  package-lock.json                     # 锁定依赖版本
  vite.config.ts                        # Vite 配置
  tailwind.config.js                    # Tailwind 扫描配置
  postcss.config.js                     # PostCSS 配置
  tsconfig.json
  tsconfig.app.json
  index.html
```

## 常用命令汇总

```bash
# 后端依赖
pip install -r requirements.txt

# 后端开发服务
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 后端测试
cd backend
pytest tests/ -v

# Docker Compose
cd backend
copy .env.example .env
docker compose up --build

# 前端依赖
cd hetero_gnn
npm install

# 前端开发服务
cd hetero_gnn
npm run dev

# 前端构建
cd hetero_gnn
npm run build
```

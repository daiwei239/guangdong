# Semi-Real Backend

面向“异构算力资源描述与多模式任务映射”的第二阶段后端。

当前阶段目标：

- 生成异构资源节点与资源边
- 在内存中构建 `NetworkX` 资源图
- 生成任务需求画像
- 使用规则筛选 + Beam Search 搜索候选资源子网
- 通过规则评分输出 Top-1 结果
- 为后续接入 `PyTorch Geometric / DGL / HeteroGNN` 预留清晰的编码与训练结构

当前阶段不做真实 GNN 训练调度闭环，不接 Slurm/Kubernetes。

## 新增 Feature Encoder

### 为什么需要 Feature Encoder

资源图里同时存在：

- `CPU`
- `GPU`
- `FPGA`
- `MEMORY`
- `STORAGE`
- `NIC`
- `SWITCH`

这些节点的原始属性维度和语义并不一致，不能简单拼接成同一个固定向量后直接送进 GNN。

例如：

- CPU 更关注 `cores / frequency / queue_length`
- GPU 更关注 `memory_total / fp16_tflops / interconnect`
- STORAGE 更关注 `throughput / iops / latency`
- NIC 更关注 `bandwidth / rdma / packet_loss`

因此这里引入“类型专属 Feature Encoder”：

`原始资源属性 -> Feature Builder -> ResourceFeatureEncoder -> 统一 hidden_dim -> GNN -> 子图表示`

它解决的是“不同资源类型输入维度不一致”的问题，不直接替代当前规则评分公式。

## 当前整体流程

### 规则主流程

`资源生成 -> 资源图构建 -> 候选子网搜索 -> 规则评分 -> 验证 -> API 输出`

当前在线流程中，`step_4_encoding_resource_graph` 已经真实执行资源图编码：

- 全图先构造成 `HeteroData`
- 调用 `ResourceGraphEncoder` 生成全图级 embedding
- 在候选子网搜索后，对每个 candidate subgraph 再生成 `z_subgraph`
- 这些编码结果当前作为内部辅助工件保留，不改变现有 REST 返回结构

### 模型增强流程

`原始资源属性 -> Feature Encoder -> GNN -> z_subgraph -> 训练模型评分 / 辅助规则评分`

当前版本里：

- `/api/simulate`
- `/api/match`

仍然保持原有返回格式。

规则最终分仍然使用：

```text
S(t,k)= alpha * Mcap(t,k) + beta * Mperf(t,k) + gamma * Mtopo(t,k) - lambda * Cost(k)
```

默认权重：

- `alpha = 0.35`
- `beta = 0.35`
- `gamma = 0.20`
- `lambda = 0.10`

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
      beam_search.py
      feature_builder.py
      feature_encoder.py
      gnn_encoder.py
      matcher_model.py
      rule_filter.py
      score.py
      task_encoder.py
    api/
    mock/
    utils/
  scripts/
    train_matcher.py
    infer_matcher.py
  tests/
  docker-compose.yml
  Dockerfile
  requirements.txt
  README.md
```

## Feature Builder 与输入维度

`app/algorithms/feature_builder.py` 定义了每类资源的原始特征构造逻辑，并统一归一化到 `0~1`。

默认输入维度：

```python
RESOURCE_INPUT_DIMS = {
    "CPU": 6,
    "GPU": 10,
    "FPGA": 8,
    "MEMORY": 5,
    "STORAGE": 6,
    "NIC": 6,
    "SWITCH": 5,
}
```

示例：

- CPU: `cores_norm, frequency_norm, utilization, queue_length_norm, power_norm, available_flag`
- GPU: `memory_total_norm, memory_free_norm, fp16_tflops_norm, fp32_tflops_norm, utilization, temperature_norm, power_norm, interconnect_score, queue_length_norm, available_flag`
- FPGA: `logic_units_norm, dsp_blocks_norm, bram_norm, reconfig_time_norm, utilization, power_norm, temperature_norm, available_flag`

缺失字段会自动回落到默认值，避免编码报错。

## GNN 编码结构

当前资源图编码器已经从“Feature Encoder + 普通 GAT”升级为“Feature Encoder + 异构关系感知 GNN”：

- 保留 `CPU / GPU / FPGA / MEMORY / STORAGE / NIC / SWITCH` 等节点类型
- 保留 `SAME_HOST / SAME_RACK / LOW_LATENCY_LINK / SHARES_MEMORY / COMPETES_BANDWIDTH / CONNECTED_TO / SCHEDULING_DEPENDENCY` 等边类型
- 使用 `edge_attr` 表示带宽、时延、拥塞、可靠性和边权重
- 使用 `HeteroConv` 为不同关系类型配置不同 GNN 参数
- 使用任务感知池化生成候选资源子网表示 `z_subgraph`

### ResourceFeatureEncoder

位置：

- [app/algorithms/feature_encoder.py](D:/DDocuments/guangdong/backend/app/algorithms/feature_encoder.py)

职责：

- 每类节点使用独立的 `Linear / MLP`
- 将不同输入维度映射到统一 `hidden_dim`
- 输出 `x_dict`，兼容 `PyG HeteroData`

### ResourceGraphEncoder

位置：

- [app/algorithms/gnn_encoder.py](D:/DDocuments/guangdong/backend/app/algorithms/gnn_encoder.py)

流程：

```text
raw_x_dict
  -> ResourceFeatureEncoder
  -> encoded_x_dict
  -> edge_index_dict + edge_attr_dict
  -> HeteroConv / relation-aware GATConv
  -> node_embeddings
  -> subgraph pooling
  -> z_subgraph
```

当前实现支持：

- `torch_geometric` 可用时走真实异构图 `HeteroConv + GATConv`
- 每种关系类型单独维护一套图卷积参数
- 自动为正向边补充 `REV_` 反向边
- `torch_geometric` 不可用时退化为 Feature Encoder + 类型投影 + 池化 fallback

### 边属性设计

当前统一使用 5 维边属性：

```text
[bandwidth_norm, latency_score, congestion_score, reliability_norm, weight]
```

含义：

- `bandwidth_norm`：越大越好
- `latency_score`：由时延归一化后反转得到，越大越好
- `congestion_score`：由拥塞归一化后反转得到，越大越好
- `reliability_norm`：越大越好
- `weight`：综合边权重

如果原始边缺失这些字段，会使用默认值兜底。

### 任务感知池化

`pool_subgraph(x_dict, task_type)` 现在支持两种模式：

- `task_type is None`：对现有节点类型做平均池化
- `task_type` 有值：先对每种节点类型做 mean pooling，再按任务类型权重加权求和

这样 `z_subgraph` 会显式体现不同任务对 `GPU / NIC / STORAGE / SWITCH` 等资源类型的偏好差异。

## 任务编码器与匹配模型

### TaskEncoder

位置：

- [app/algorithms/task_encoder.py](D:/DDocuments/guangdong/backend/app/algorithms/task_encoder.py)

负责将任务需求向量编码到固定 `hidden_dim`。

### TaskResourceMatcher

位置：

- [app/algorithms/matcher_model.py](D:/DDocuments/guangdong/backend/app/algorithms/matcher_model.py)

结构：

```text
candidate_subgraph(HeteroData)
  -> ResourceGraphEncoder
  -> z_subgraph

task_vec
  -> TaskEncoder
  -> z_task

concat(z_subgraph, z_task)
  -> MLP scorer
  -> model_score
```

这个模型用于后续训练或辅助评分。

当前项目中：

- 保留原规则评分逻辑
- 不删除现有 API
- 不让 GNN 直接吃原始异构特征

## 规则评分

规则评分仍在：

- [app/algorithms/score.py](D:/DDocuments/guangdong/backend/app/algorithms/score.py)

保留函数：

- `compute_capacity_score()`
- `compute_performance_score()`
- `compute_topology_score()`
- `compute_cost()`
- `compute_final_score()`

模型输出的 `z_subgraph` 目前仅预留给后续增强使用，例如：

- 辅助 `compute_performance_score`
- 辅助 `compute_topology_score`
- 辅助 `compute_cost`

当前不会强制替代规则评分。



## 本地环境

推荐：

- Python `3.11+`
- Conda 或虚拟环境



## 安装依赖

基础依赖：

```bash
pip install -r requirements.txt
```

## 本机连接 Docker 中的数据库

如果你是在本机直接运行 `uvicorn`，而 PostgreSQL / Neo4j 在 Docker 里，建议使用 `.env` 配置本机路由：

```env
DATABASE_URL=postgresql+psycopg://guangdong_user:guangdong_pass@localhost:5432/guangdong_resource_mapping
NEO4J_ENABLED=true
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=guangdong_pass
```

项目里已提供模板：

- [\.env.example](D:/DDocuments/guangdong/backend/.env.example)

这种场景下不要使用 `postgres` / `neo4j` 作为主机名，那是给 Docker 容器内部互联用的。

## Docker Compose 变量化配置

`docker-compose.yml` 里的动态项已经提取到环境变量中，包括：

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_PORT`
- `NEO4J_USER`
- `NEO4J_PASSWORD`
- `NEO4J_HTTP_PORT`
- `NEO4J_BOLT_PORT`
- `REDIS_PORT`
- `BACKEND_PORT`

也就是说，后续如果你要改数据库名、账号、密码或端口，优先修改 `.env`，不需要再直接改 `docker-compose.yml`。

如果环境里没有 `torch` / `torch_geometric`，可按你的 CUDA 版本安装，例如：

```bash
pip install torch
pip install torch-geometric
```

说明：

- 当前仓库对 `torch_geometric` 做了 fallback 设计
- 完整的异构关系感知 GNN 需要安装 `torch_geometric`
- 没有 PyG 时，训练与图编码能力会退化为简化路径

## 本地启动

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Docker 启动

```bash
docker compose up --build
```

## 测试

基础链路测试：

```bash
pytest tests/test_resource_graph.py tests/test_matching.py -v
```

编码器测试：

```bash
pytest tests/test_feature_encoder.py tests/test_gnn_encoder.py -v
```

## 训练与推理示例

训练示例：

```bash
python scripts/train_matcher.py
```

推理示例：

```bash
python scripts/infer_matcher.py
```

`train_matcher.py` 展示：

- mock 训练样本构造
- `HeteroData` 候选子图编码
- `TaskEncoder + ResourceGraphEncoder + MLP scorer`
- `BCEWithLogitsLoss`
- 优化器更新 Feature Encoder / GNN / TaskEncoder / scorer 全部参数

`infer_matcher.py` 展示：

- 输入一个任务需求
- 输入多个候选资源子网
- 对每个候选子网进行 `Feature Encoder + GNN` 编码
- 输出 `model_score`
- 同时保留 `rule_final_score`
- 对候选结果进行排序

## Prometheus

`/metrics` 已预留：

- `resource_node_count`
- `resource_edge_count`
- `match_request_total`
- `match_latency_seconds`
- `candidate_subgraph_count`
- `top1_score`

示例抓取配置：

```yaml
scrape_configs:
  - job_name: semi-real-backend
    static_configs:
      - targets: ["localhost:8000"]
```

## 如果后续新增资源特征

需要同步更新：

1. `feature_builder`
2. `input_dims`
3. 训练数据构造
4. 模型重新训练

这样可以保持：

- 原始特征定义
- Feature Encoder 输入维度
- 训练样本
- 推理行为

始终一致。

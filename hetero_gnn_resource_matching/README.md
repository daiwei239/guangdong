# Heterogeneous GNN Resource Matching

这是一个基于 PyTorch Geometric 的“异构算力资源与多模式任务映射”原型系统。系统用 `HeteroData` 表示 CPU、GPU、FPGA、MEMORY、STORAGE、NIC、SWITCH 组成的全局资源图，用 HGTConv 编码资源拓扑，再将候选资源子网 embedding 与任务需求向量融合，输出任务到候选资源子网的匹配分数。

## 项目目标

给定多模式任务的算力、显存/内存、存储、网络、能耗和 QoS 需求，系统生成候选资源子网，使用任务条件化异构 GNN 排序，输出 Top-N 候选、Top-1 最优候选、匹配分数和规则验证结果。

## 数据格式

资源节点位于 `data/raw/resources.json`，每个节点包含：

```json
{
  "id": "gpu_000",
  "type": "gpu",
  "node_id": "host_000",
  "rack_id": "rack_00",
  "switch_id": "switch_000",
  "features": {"fp32_tflops": 60, "vram_gb": 80, "available": 1}
}
```

拓扑边位于 `data/raw/edges.json`，使用 PyG 异构边三元组所需字段：

```json
{
  "source": "gpu_000",
  "target": "nic_000",
  "source_type": "gpu",
  "target_type": "nic",
  "relation": "pcie_connect"
}
```

任务位于 `data/raw/tasks.json`，候选、标签和 split 位于 `data/processed/`。

## 资源图建模

`graph_builder.py` 将 JSON 转换为 PyG `HeteroData`：

- `data["cpu"].x`
- `data["gpu"].x`
- `data["fpga"].x`
- `data["memory"].x`
- `data["storage"].x`
- `data["nic"].x`
- `data["switch"].x`

边使用三元组，例如 `("gpu", "pcie_connect", "nic")` 和反向边 `("nic", "pcie_connect", "gpu")`。

## 任务需求向量

`task_vectorizer.py` 将任务转为固定维度向量：

- `task_type` one-hot
- `dominant_mode` one-hot
- 算力、显存、CPU 核数、内存、存储带宽、网络带宽、延迟、功耗、deadline、priority
- `prefer_same_node`、`prefer_low_load`、`prefer_low_energy`、`need_rdma`

任务需求不作为图节点输入，只进入 `TaskEncoder`。

## GNN 模型结构

`model.py` 的主模型是 `TaskConditionedResourceMatcher`：

1. `ResourceHGTEncoder`: 使用 `HGTConv` 编码全局异构资源图。
2. `TaskEncoder`: MLP 编码任务需求向量。
3. `CandidatePooler`: 对候选子网内节点 embedding 做 mean pooling。
4. 融合 `[subgraph_emb, task_emb, subgraph_emb * task_emb, abs(subgraph_emb - task_emb)]`。
5. MLP 输出 logits 和 sigmoid matching score。

规则只用于候选粗筛、伪标签生成和最终验证，不替代 GNN 排序。

## 生成合成数据

```bash
python data/synthetic/generate_synthetic_data.py
```

可选参数：

```bash
python data/synthetic/generate_synthetic_data.py --train 1000 --val 200 --test 200 --max-candidates 20
```

## 训练

```bash
python -m resource_mapping.step_04_candidate_gnn_matching.train --config configs/default.yaml
```

训练使用 BCE + pairwise ranking loss，并保存最佳模型到：

```text
outputs/checkpoints/best_model.pt
```

## 推理

```bash
python -m resource_mapping.step_05_ranking_verification.infer --config configs/default.yaml --checkpoint outputs/checkpoints/best_model.pt --task_id task_0001 --top_k 5
```

结果写入：

```text
outputs/topk_results.json
```

输出包含 Top-1 子网、Top-N 候选、GNN 分数和 `ResourceVerifier` 的容量、性能、拓扑、QoS 验证结果。

## 评估

```bash
python -m resource_mapping.step_05_ranking_verification.evaluate --config configs/default.yaml --checkpoint outputs/checkpoints/best_model.pt
```

输出 `outputs/evaluation.json`，指标包括 Top-1、Top-5、MRR、QoS 满足率、平均 GNN 推理时间、约束满足率、AUC、Precision、Recall、F1。

## 可视化报告

评估和推理完成后可以生成一个静态 HTML 报告：

```bash
python -m resource_mapping.step_05_ranking_verification.visualize --config configs/default.yaml
```

报告写入：

```text
outputs/evaluation_report.html
```

报告包含评估流程、资源图规模、数据划分、指标卡片、指标柱状图、Top-K 候选排名、Top-1 子网节点清单和规则验证结果。

## 交互式演示页面

训练出 `outputs/checkpoints/best_model.pt` 后，可以启动一个本地 Web 页面，直接输入任务需求并查看候选子网生成、GNN 打分排序和规则验证结果：

```bash
python -m resource_mapping.step_05_ranking_verification.web_demo --config configs/default.yaml --port 8008
```

浏览器打开：

```text
http://127.0.0.1:8008
```

页面会把用户输入的任务需求编码成任务向量，生成候选资源子网，调用 HGT-GNN 对候选子网打分，然后展示 Top-K 资源映射结果。

## 测试

```bash
pytest
```

测试覆盖：

- `HeteroData` 节点类型和边类型构建
- 候选子网生成
- 任务向量固定维度和 NaN 检查
- HGT 模型 forward
- 需求验证满足/不满足场景

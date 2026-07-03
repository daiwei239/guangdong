# Resource State Data Pipeline

本仓库当前实现的是一个三层资源状态数据 pipeline：

1. 输入层：读取实时资源状态数据。
2. 处理层：清洗并归一化资源指标。
3. 输出层：生成标准化 JSON 输出。

旧的任务匹配、GNN、资源图、Beam Search、评分、数据库持久化结构已经从当前 pipeline 中移除。

## Run

```bash
cd backend
python scripts/run_pipeline.py --input path/to/ResourceState.json
```

输出到文件：

```bash
python scripts/run_pipeline.py --input path/to/ResourceState.json --output outputs/normalized.json
```

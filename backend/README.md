# Backend

当前后端是一个三层资源状态数据 pipeline，不再包含任务匹配、图构建、GNN、Beam Search、评分或数据库持久化结构。

## Pipeline Layers

1. 输入层：`app/input/`
   - `resource_input.py` 从资源状态 JSON 中读取原始数据。
   - 校验基础结构并补齐时间戳、链路追踪号。

2. 处理层：`app/process/`
   - `normalizer.py` 将资源指标转换为 0 到 1 区间。
   - 布尔值转为 `1.0` 或 `0.0`。
   - 保留静态属性和拓扑边，供输出层拆分业务对象。

3. 输出层：`app/output/`
   - `resource_profile.py` 定义 `ResourceProfile` 输出。
   - `resource_state.py` 定义 `ResourceState` 输出。
   - `resource_topology.py` 定义 `ResourceTopology` 输出。
   - `resource_output.py` 汇总并写出三个 JSON 文件。

## Message Envelope

三个输出文件都采用统一消息结构：

```json
{
  "schema_version": "1.0",
  "message_id": "MSG-20260703-000001",
  "message_type": "ResourceProfile",
  "source_module": "Module-2.1-ResourceSensing",
  "target_module": ["Module-2.2-ResourceProcessing"],
  "timestamp": "2026-07-03T10:30:00+08:00",
  "trace_id": "TRACE-R20260703-000001",
  "payload": {}
}
```

## Output Files

使用 `--output-dir` 会生成三个文件：

```text
ResourceProfile.json
ResourceState.json
ResourceTopology.json
```

## Main Entry

```bash
python scripts/run_pipeline.py --input path/to/ResourceInput.json --output-dir outputs/
```

兼容旧参数名：

```bash
python scripts/run_pipeline.py --resources path/to/ResourceInput.json --output-dir outputs/
```

也可以写一个合并预览文件：

```bash
python scripts/run_pipeline.py --input path/to/ResourceInput.json --output combined.json
```

## Kafka realtime input

Kafka sits before the 2.1 input layer:

```text
resource data sources -> Kafka topics -> KafkaInputAdapter -> StateAggregator -> process -> output
```

Default topics:

```text
resource.management_config
resource.agent_collect
resource.realtime_monitor
resource.device_plugin
resource.topology_probe
resource.scheduler_queue
resource.asset_ops
resource.analytics_history
```

Use `node_id` as the Kafka message key. Message values should use the `ResourceEvent` JSON shape:

```json
{
  "timestamp": "2026-05-18T10:32:00+08:00",
  "trace_id": "TRACE-R20260518-000001",
  "node_id": "N-C01-0001",
  "attributes": {},
  "metrics": {}
}
```

Run one Kafka-backed pipeline batch:

```bash
python scripts/run_pipeline.py --kafka --max-messages 100 --output-dir outputs/
```

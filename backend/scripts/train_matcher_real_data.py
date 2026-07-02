from __future__ import annotations

import argparse
import math
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import pandas as pd
import torch
from torch import nn


# backend/scripts/train_matcher_real_data.py -> backend/
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.algorithms.feature_builder import (  # noqa: E402
    RESOURCE_INPUT_DIMS,
    TASK_INPUT_DIM,
    build_mock_heterodata_from_resources,
    build_task_feature_tensor,
)
from app.algorithms.matcher_model import TaskResourceMatcher  # noqa: E402
from app.schemas.resource_schema import ResourceEdgeRead, ResourceNodeRead  # noqa: E402
from app.schemas.task_schema import TaskProfileRead  # noqa: E402


# 说明：
# 这份脚本用于把当前三份真实/半真实数据先接入现有模型训练流程。
# 目前数据中只有 task、真实分配 server、server 内 CPU/GPU/NIC 组件，
# 没有完整 CPU/MEMORY/NIC 静态规格和动态图拓扑，所以这里采用“弱监督 + 规则补全”的方式：
# 1. 真实被分配的 server 作为正样本；
# 2. 从其他 server 随机采样负样本；
# 3. 为每个 server 补一个 MEMORY 节点，让候选子图接近现在代码里的 CPU/GPU/MEMORY/NIC 结构；
# 4. GPU 静态规格根据 observed_gpu_spec 做一个近似映射；
# 5. 训练目标是二分类：当前 task 与当前 candidate server/subgraph 是否匹配。


GPU_SPEC_TABLE: Dict[str, Dict[str, float | str]] = {
    "A10": {"memory_total": 24, "fp16_tflops": 125, "fp32_tflops": 31, "interconnect": "PCIe"},
    "A30": {"memory_total": 24, "fp16_tflops": 165, "fp32_tflops": 10, "interconnect": "PCIe"},
    "A100": {"memory_total": 80, "fp16_tflops": 312, "fp32_tflops": 19.5, "interconnect": "NVLink"},
    "A800": {"memory_total": 80, "fp16_tflops": 312, "fp32_tflops": 19.5, "interconnect": "NVLink"},
    "H20": {"memory_total": 96, "fp16_tflops": 296, "fp32_tflops": 44, "interconnect": "NVLink"},
    "H20-141GB": {"memory_total": 141, "fp16_tflops": 296, "fp32_tflops": 44, "interconnect": "NVLink"},
    "H800": {"memory_total": 80, "fp16_tflops": 700, "fp32_tflops": 60, "interconnect": "NVLink"},
    "L20": {"memory_total": 48, "fp16_tflops": 120, "fp32_tflops": 30, "interconnect": "PCIe"},
    "XPU-A": {"memory_total": 32, "fp16_tflops": 120, "fp32_tflops": 30, "interconnect": "PCIe"},
    "XPU-B": {"memory_total": 48, "fp16_tflops": 160, "fp32_tflops": 40, "interconnect": "PCIe"},
    "XPU-C": {"memory_total": 64, "fp16_tflops": 220, "fp32_tflops": 55, "interconnect": "PCIe"},
    "XPU-D": {"memory_total": 80, "fp16_tflops": 260, "fp32_tflops": 65, "interconnect": "NVLink"},
    "XPU-E": {"memory_total": 96, "fp16_tflops": 300, "fp32_tflops": 75, "interconnect": "NVLink"},
}


def read_parquet_compat(path: Path) -> pd.DataFrame:
    """兼容读取 parquet：优先 pandas，失败时直接用 pyarrow 读取。"""
    try:
        return pd.read_parquet(path)
    except Exception:
        try:
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise RuntimeError(
                "读取 parquet 需要 pyarrow。请先执行：pip install pyarrow"
            ) from exc
        return pd.DataFrame(pq.read_table(path).to_pylist())


def safe_float(value, default: float = 0.0) -> float:
    """把 None/NaN/字符串安全转换成 float。"""
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except TypeError:
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_bool(value, default: bool = False) -> bool:
    """把 pandas/numpy/object 里的布尔值安全转换成 bool。"""
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except TypeError:
        pass
    if isinstance(value, str):
        return value.lower() in {"true", "1", "yes", "y"}
    return bool(value)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def stable_int(text: str, mod: int) -> int:
    """根据字符串生成稳定整数，避免每次运行拓扑上下文变化太大。"""
    return sum(ord(ch) for ch in str(text)) % mod


def task_type_from_row(row: pd.Series) -> str:
    """把真实 job_type 粗略映射成当前系统使用的中文任务类型。"""
    job_type = str(row.get("job_type", "unknown"))
    model_type = str(row.get("model_type", "unknown"))

    if job_type == "training":
        return "计算密集型"
    if job_type == "online_inference":
        return "通信密集型"
    if job_type == "offline_inference":
        return "计算密集型"
    if model_type in {"genai", "cv", "embedding"}:
        return "计算密集型"
    return "混合型"


def priority_to_int(priority_class: str) -> int:
    if priority_class == "HP":
        return 3
    if priority_class == "LP":
        return 1
    return 2


def build_task_profile(row: pd.Series) -> TaskProfileRead:
    """把 task_input 的一行转换成当前代码里的 TaskProfileRead。"""
    gpu_request = safe_float(row.get("gpu_request"), 1.0)
    gpu_count = max(1, int(math.ceil(gpu_request)))
    priority_class = str(row.get("priority_class", "Other"))
    priority = priority_to_int(priority_class)
    task_type = task_type_from_row(row)
    is_genai = safe_bool(row.get("is_genai"), False)
    job_type = str(row.get("job_type", "unknown"))

    # 这些是初版映射，不是最终业务规则。
    # 目的是先让真实 task 输入进入现有 14 维 task encoder。
    cpu_cores = 8 + 4 * gpu_count
    fp16_tflops = (120 if is_genai else 60) * gpu_count
    memory_gb = 64 * gpu_count if is_genai else 32 * gpu_count
    network_bandwidth = 100.0 if job_type == "online_inference" else 40.0
    latency_ms = 2.0 if job_type == "online_inference" or priority_class == "HP" else 8.0
    qos_deadline_sec = 60.0 if priority_class == "HP" else 300.0

    return TaskProfileRead(
        task_id=str(row["task_id"]),
        task_type=task_type,
        dag_nodes=[],
        compute_req={
            "cpu_cores": cpu_cores,
            "gpu_count": gpu_count,
            "fp16_tflops": fp16_tflops,
        },
        memory_req={
            "capacity_gb": memory_gb,
        },
        storage_req={
            "capacity_tb": 0.0,
            "throughput_gbps": 0.0,
        },
        network_req={
            "bandwidth_gbps": network_bandwidth,
            "latency_ms": latency_ms,
        },
        energy_limit=5000.0,
        qos_deadline_sec=qos_deadline_sec,
        priority=priority,
        constraints={
            "min_gpu_memory_gb": 24.0 * gpu_count,
            "min_storage_throughput_gbps": 0.0,
            "max_network_latency_ms": latency_ms,
            "max_resource_utilization": 95.0,
            "prefer_low_latency": job_type == "online_inference",
            "prefer_same_rack": priority_class == "HP",
        },
    )


def gpu_spec_attrs(gpu_spec: str | None) -> Dict:
    """根据 observed_gpu_spec 返回 GPU 静态属性；未知型号使用保守默认值。"""
    spec = str(gpu_spec or "UNKNOWN")
    attrs = dict(GPU_SPEC_TABLE.get(spec, {}))
    if not attrs:
        attrs = {
            "memory_total": 48,
            "fp16_tflops": 120,
            "fp32_tflops": 30,
            "interconnect": "PCIe",
        }
    attrs["model"] = spec
    return attrs


def topo_context_from_server(server_id: str) -> Dict:
    """从 server_id 构造稳定的拓扑上下文。"""
    rack_index = stable_int(server_id, 16) + 1
    cluster_index = stable_int(server_id, 3) + 1
    zone_index = stable_int(server_id, 2) + 1
    network_tier = 1 if rack_index <= 8 else 2
    hop_level = 1 + stable_int(server_id[::-1], 4)

    return {
        "server_id": server_id,
        "rack_id": f"rack-{rack_index}",
        "cluster_id": f"cluster-{cluster_index}",
        "zone_id": f"zone-{zone_index}",
        "network_tier": network_tier,
        "hop_level": hop_level,
    }


def dynamic_state_from_row(row: pd.Series | None, positive: bool) -> Dict:
    """根据调度观测信息构造动态状态；负样本没有观测时使用默认状态。"""
    if row is None:
        return {
            "utilization": 65.0,
            "memory_free": 32.0,
            "queue_length": 8,
            "power_watt": 300.0,
            "temperature": 60.0,
            "packet_loss": 0.01,
            "congestion": 0.3,
            "available": True,
        }

    schedule_delay = safe_float(row.get("schedule_delay_sec"), 0.0)
    ready_delay = safe_float(row.get("ready_delay_sec"), 0.0)
    schedule_status = safe_bool(row.get("schedule_status"), True)
    ready_status = safe_bool(row.get("ready_status"), True)

    # delay 越大，认为队列和利用率越高。
    delay_signal = math.log1p(max(schedule_delay, 0.0) + max(ready_delay, 0.0))
    utilization = clamp(20.0 + delay_signal * 8.0, 5.0, 95.0)
    queue_length = int(clamp(delay_signal * 2.0, 0.0, 32.0))

    return {
        "utilization": utilization,
        "memory_free": 64.0 if positive else 32.0,
        "queue_length": queue_length,
        "power_watt": 220.0 + utilization * 3.0,
        "temperature": 35.0 + utilization * 0.45,
        "packet_loss": 0.002 if positive else 0.02,
        "congestion": clamp(utilization / 120.0, 0.0, 0.95),
        "available": bool(schedule_status and ready_status) if positive else True,
    }


def build_server_subgraph(
    server_id: str,
    gpu_spec: str | None,
    row: pd.Series | None,
    positive: bool,
) -> Tuple[List[ResourceNodeRead], List[ResourceEdgeRead]]:
    """为一个 server 构造 CPU/GPU/MEMORY/NIC 候选子图。"""
    now = datetime.utcnow()
    topo = topo_context_from_server(server_id)
    dyn = dynamic_state_from_row(row, positive=positive)

    cpu_id = f"cpu_{server_id}"
    gpu_id = f"gpu_{server_id}"
    mem_id = f"mem_{server_id}"
    nic_id = f"nic_{server_id}"

    resources = [
        ResourceNodeRead(
            id=cpu_id,
            name=cpu_id,
            type="CPU",
            cluster_id=topo["cluster_id"],
            host_id=server_id,
            topo_context=topo,
            static_attrs={"cores": 64, "frequency": 3.2, "architecture": "x86_64"},
            dynamic_state=dyn,
            semantic_tags=["general_compute"],
            created_at=now,
            updated_at=now,
        ),
        ResourceNodeRead(
            id=gpu_id,
            name=gpu_id,
            type="GPU",
            cluster_id=topo["cluster_id"],
            host_id=server_id,
            topo_context=topo,
            static_attrs=gpu_spec_attrs(gpu_spec),
            dynamic_state=dyn,
            semantic_tags=["accelerator", "ai"],
            created_at=now,
            updated_at=now,
        ),
        ResourceNodeRead(
            id=mem_id,
            name=mem_id,
            type="MEMORY",
            cluster_id=topo["cluster_id"],
            host_id=server_id,
            topo_context=topo,
            static_attrs={"capacity_gb": 512, "bandwidth_gbps": 400},
            dynamic_state=dyn,
            semantic_tags=["memory_pool"],
            created_at=now,
            updated_at=now,
        ),
        ResourceNodeRead(
            id=nic_id,
            name=nic_id,
            type="NIC",
            cluster_id=topo["cluster_id"],
            host_id=server_id,
            topo_context=topo,
            static_attrs={"bandwidth_gbps": 200, "latency_ms": 0.8, "rdma_enabled": True},
            dynamic_state=dyn,
            semantic_tags=["network", "rdma"],
            created_at=now,
            updated_at=now,
        ),
    ]

    edge_specs = [
        ("cpu_gpu", cpu_id, gpu_id, "SAME_HOST", 200.0, 0.3, 0.9),
        ("cpu_mem", cpu_id, mem_id, "SHARES_MEMORY", 400.0, 0.2, 0.95),
        ("gpu_mem", gpu_id, mem_id, "SHARES_MEMORY", 400.0, 0.25, 0.95),
        ("cpu_nic", cpu_id, nic_id, "CONNECTED_TO", 200.0, 0.8, 0.8),
        ("gpu_nic", gpu_id, nic_id, "LOW_LATENCY_LINK", 200.0, 0.8, 0.8),
    ]

    edges = [
        ResourceEdgeRead(
            id=f"{prefix}_{server_id}",
            source=source,
            target=target,
            relation_type=relation_type,
            bandwidth_gbps=bandwidth,
            latency_ms=latency,
            weight=weight,
        )
        for prefix, source, target, relation_type, bandwidth, latency, weight in edge_specs
    ]

    return resources, edges


def build_server_gpu_profile(merged: pd.DataFrame) -> Dict[str, str]:
    """统计每个 server 最常见的 observed_gpu_spec，供负样本构造使用。"""
    profile: Dict[str, str] = {}
    for server_id, group in merged.groupby("server_id"):
        mode = group["observed_gpu_spec"].dropna().astype(str).mode()
        profile[str(server_id)] = str(mode.iloc[0]) if not mode.empty else "UNKNOWN"
    return profile


def load_merged_data(data_dir: Path, max_tasks: int | None = None) -> pd.DataFrame:
    """加载并合并三份数据。"""
    task_path = data_dir / "task_input.parquet"
    allocation_path = data_dir / "task_allocation_result.parquet"
    components_path = data_dir / "task_server_components.csv"

    task_df = read_parquet_compat(task_path)
    alloc_df = read_parquet_compat(allocation_path)
    comp_df = pd.read_csv(components_path)

    # 当前数据里有少量重复 task_id。先保留第一条，保证一条 task 对应一个训练样本。
    task_df = task_df.drop_duplicates("task_id", keep="first")
    alloc_df = alloc_df.drop_duplicates("task_id", keep="first")
    comp_df = comp_df.drop_duplicates("task_id", keep="first")

    merged = task_df.merge(alloc_df, on="task_id", how="inner")
    merged = merged.merge(comp_df, on="task_id", how="inner")

    # 正样本至少需要有已选择的 server。
    merged = merged[merged["selected_server_id"].notna()].copy()

    if max_tasks is not None and max_tasks > 0:
        merged = merged.head(max_tasks).copy()

    return merged.reset_index(drop=True)


def make_training_samples(
    merged: pd.DataFrame,
    negative_per_task: int,
    seed: int,
) -> List[Tuple[object, torch.Tensor, torch.Tensor]]:
    """构造二分类训练样本：(候选子图, 任务向量, 标签)。"""
    rng = random.Random(seed)
    server_gpu_profile = build_server_gpu_profile(merged)
    server_ids = sorted(server_gpu_profile.keys())

    samples = []
    for _, row in merged.iterrows():
        task = build_task_profile(row)
        task_vec = build_task_feature_tensor(task)

        # 正样本：真实分配的 server。
        selected_server_id = str(row["selected_server_id"])
        selected_gpu_spec = str(row.get("observed_gpu_spec", server_gpu_profile.get(selected_server_id, "UNKNOWN")))
        pos_resources, pos_edges = build_server_subgraph(
            server_id=selected_server_id,
            gpu_spec=selected_gpu_spec,
            row=row,
            positive=True,
        )
        pos_data = build_mock_heterodata_from_resources(pos_resources, pos_edges)
        samples.append((pos_data, task_vec, torch.tensor([[1.0]], dtype=torch.float32)))

        # 负样本：随机选择其他 server。
        negative_pool = [server_id for server_id in server_ids if server_id != selected_server_id]
        if not negative_pool:
            continue

        for negative_server_id in rng.sample(negative_pool, k=min(negative_per_task, len(negative_pool))):
            neg_gpu_spec = server_gpu_profile.get(negative_server_id, "UNKNOWN")
            neg_resources, neg_edges = build_server_subgraph(
                server_id=negative_server_id,
                gpu_spec=neg_gpu_spec,
                row=None,
                positive=False,
            )
            neg_data = build_mock_heterodata_from_resources(neg_resources, neg_edges)
            samples.append((neg_data, task_vec, torch.tensor([[0.0]], dtype=torch.float32)))

    rng.shuffle(samples)
    return samples


def evaluate(model: TaskResourceMatcher, samples: List[Tuple[object, torch.Tensor, torch.Tensor]]) -> Dict[str, float]:
    """简单评估 accuracy 和平均 loss，方便先确认训练能跑通。"""
    if not samples:
        return {"loss": 0.0, "accuracy": 0.0}

    criterion = nn.BCEWithLogitsLoss()
    model.eval()
    total_loss = 0.0
    correct = 0

    with torch.no_grad():
        for data, task_vec, label in samples:
            logit, _, _ = model(data, task_vec)
            loss = criterion(logit, label)
            total_loss += float(loss.item())

            pred = (torch.sigmoid(logit) >= 0.5).float()
            correct += int((pred == label).all().item())

    return {
        "loss": total_loss / len(samples),
        "accuracy": correct / len(samples),
    }


def train(args: argparse.Namespace) -> None:
    random.seed(args.seed)
    torch.manual_seed(args.seed)

    data_dir = Path(args.data_dir)
    merged = load_merged_data(data_dir=data_dir, max_tasks=args.max_tasks)
    samples = make_training_samples(
        merged=merged,
        negative_per_task=args.negative_per_task,
        seed=args.seed,
    )

    if not samples:
        raise RuntimeError("没有构造出训练样本，请检查三份数据是否能按 task_id 合并。")

    split_index = int(len(samples) * args.train_ratio)
    train_samples = samples[:split_index]
    val_samples = samples[split_index:] or samples[: max(1, min(100, len(samples)))]

    model = TaskResourceMatcher(
        input_dims=RESOURCE_INPUT_DIMS,
        task_dim=TASK_INPUT_DIM,
        hidden_dim=args.hidden_dim,
        out_dim=args.out_dim,
    )

    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    criterion = nn.BCEWithLogitsLoss()

    print(
        {
            "merged_tasks": len(merged),
            "train_samples": len(train_samples),
            "val_samples": len(val_samples),
            "negative_per_task": args.negative_per_task,
        }
    )

    model.train()
    for epoch in range(args.epochs):
        random.shuffle(train_samples)
        total_loss = 0.0

        for data, task_vec, label in train_samples:
            optimizer.zero_grad()
            logit, _, _ = model(data, task_vec)
            loss = criterion(logit, label)
            loss.backward()
            optimizer.step()
            total_loss += float(loss.item())

        train_loss = total_loss / max(len(train_samples), 1)
        val_metrics = evaluate(model, val_samples)
        print(
            {
                "epoch": epoch + 1,
                "train_loss": round(train_loss, 4),
                "val_loss": round(val_metrics["loss"], 4),
                "val_accuracy": round(val_metrics["accuracy"], 4),
            }
        )

    models_dir = PROJECT_ROOT / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    checkpoint_path = Path(args.output)
    if not checkpoint_path.is_absolute():
        checkpoint_path = PROJECT_ROOT / checkpoint_path
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "resource_encoder_state_dict": model.resource_encoder.state_dict(),
            "resource_encoder_edge_types": list(model.resource_encoder.configured_edge_types),
            "task_encoder_state_dict": model.task_encoder.state_dict(),
            "scorer_state_dict": model.scorer.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "epoch": args.epochs,
            "loss": train_loss,
            "training_data": {
                "source": "real_task_allocation_data",
                "merged_tasks": len(merged),
                "train_samples": len(train_samples),
                "val_samples": len(val_samples),
                "negative_per_task": args.negative_per_task,
            },
        },
        checkpoint_path,
    )
    print({"saved_checkpoint": str(checkpoint_path)})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="用真实 task allocation 初步训练 matcher。")
    parser.add_argument("--data-dir", default=str(PROJECT_ROOT / "data" / "real"), help="三份数据所在目录")
    parser.add_argument("--output", default="models/matcher_checkpoint.pt", help="checkpoint 输出位置")
    parser.add_argument("--max-tasks", type=int, default=2000, help="先用前 N 个 task 试跑；设为 0 表示全量")
    parser.add_argument("--negative-per-task", type=int, default=2, help="每个正样本采样几个负样本")
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--hidden-dim", type=int, default=64)
    parser.add_argument("--out-dim", type=int, default=64)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if args.max_tasks == 0:
        args.max_tasks = None

    return args


if __name__ == "__main__":
    train(parse_args())

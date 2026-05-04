import random
from datetime import datetime
from typing import Dict, List

from app.schemas.task_schema import TaskProfileRead
from app.utils.id_generator import generate_id


class MockTaskGenerator:
    TASK_TYPES = ["计算密集型", "数据密集型", "通信密集型", "混合型"]

    def generate_task_profile(self) -> TaskProfileRead:
        task_type = random.choice(self.TASK_TYPES)
        return TaskProfileRead(
            task_id=generate_id("task"),
            task_type=task_type,
            dag_nodes=self._dag_nodes(task_type),
            compute_req=self._compute_req(task_type),
            memory_req={"capacity_gb": random.choice([128, 256, 384, 512])},
            storage_req={
                "capacity_tb": random.choice([2, 4, 8, 12]),
                "throughput_gbps": random.choice([10, 20, 40]),
            },
            network_req={
                "bandwidth_gbps": random.choice([25, 50, 100, 200]),
                "latency_ms": round(random.uniform(0.3, 3.5), 2),
            },
            energy_limit=random.choice([1200, 1800, 2400, 3000]),
            qos_deadline_sec=random.choice([30, 60, 120, 180]),
            priority=random.randint(1, 5),
            constraints=self._constraints(task_type),
            created_at=datetime.utcnow(),
        )

    def _dag_nodes(self, task_type: str) -> List[Dict]:
        stages = {
            "计算密集型": ["preprocess", "compute", "aggregate"],
            "数据密集型": ["ingest", "shuffle", "persist"],
            "通信密集型": ["dispatch", "sync", "reduce"],
            "混合型": ["load", "train", "exchange", "store"],
        }
        return [{"node_id": "{0}-{1}".format(task_type, idx), "stage": stage} for idx, stage in enumerate(stages[task_type], start=1)]

    def _compute_req(self, task_type: str) -> Dict:
        profile = {
            "计算密集型": {"cpu_cores": 32, "gpu_count": 4, "fp16_tflops": 220},
            "数据密集型": {"cpu_cores": 16, "gpu_count": 1, "fp16_tflops": 60},
            "通信密集型": {"cpu_cores": 24, "gpu_count": 2, "fp16_tflops": 100},
            "混合型": {"cpu_cores": 32, "gpu_count": 2, "fp16_tflops": 140},
        }
        return profile[task_type]

    def _constraints(self, task_type: str) -> Dict:
        base = {
            "min_gpu_memory_gb": random.choice([16, 24, 40]),
            "min_network_bandwidth_gbps": random.choice([25, 50, 100]),
            "max_network_latency_ms": round(random.uniform(0.5, 3.0), 2),
            "min_storage_throughput_gbps": random.choice([10, 20, 40]),
            "prefer_same_rack": random.choice([True, False]),
            "prefer_low_latency": random.choice([True, False]),
        }
        if task_type == "通信密集型":
            base["prefer_low_latency"] = True
            base["max_network_latency_ms"] = round(random.uniform(0.5, 1.5), 2)
        return base

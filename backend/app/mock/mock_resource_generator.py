import random
from datetime import datetime
from typing import Dict, List

from app.schemas.resource_schema import ResourceNodeRead
from app.utils.id_generator import generate_id


class MockResourceGenerator:
    RESOURCE_COUNTS = {
        "CPU": 6,
        "GPU": 10,
        "FPGA": 4,
        "MEMORY": 6,
        "STORAGE": 4,
        "NIC": 4,
        "SWITCH": 2,
    }

    def generate_resources(self) -> List[ResourceNodeRead]:
        resources = []
        for resource_type, count in self.RESOURCE_COUNTS.items():
            for index in range(count):
                resources.append(self._build_resource(resource_type, index))
        return resources

    def _build_resource(self, resource_type: str, index: int) -> ResourceNodeRead:
        cluster_id = "cluster-{0}".format(random.randint(1, 3))
        host_id = "host-{0}".format(random.randint(1, 12))
        now = datetime.utcnow()
        return ResourceNodeRead(
            id=generate_id(resource_type.lower()),
            name="{0}-{1}".format(resource_type.lower(), index + 1),
            type=resource_type,
            cluster_id=cluster_id,
            host_id=host_id,
            static_attrs=self._static_attrs(resource_type),
            dynamic_state=self._dynamic_state(resource_type),
            semantic_tags=self._semantic_tags(resource_type),
            created_at=now,
            updated_at=now,
        )

    def _static_attrs(self, resource_type: str) -> Dict:
        if resource_type == "CPU":
            return {
                "cores": random.choice([16, 24, 32, 48, 64]),
                "frequency": round(random.uniform(2.4, 4.0), 2),
                "architecture": random.choice(["x86_64", "ARM64"]),
            }
        if resource_type == "GPU":
            return {
                "model": random.choice(["A100", "H100", "L40S", "RTX6000"]),
                "memory_total": random.choice([24, 40, 48, 80]),
                "fp16_tflops": random.choice([60, 120, 180, 260]),
                "interconnect": random.choice(["PCIe", "NVLink"]),
            }
        if resource_type == "FPGA":
            return {
                "model": random.choice(["XCU250", "Agilex", "Versal"]),
                "logic_units": random.randint(600000, 3000000),
                "dsp_blocks": random.randint(2000, 12000),
            }
        if resource_type == "MEMORY":
            return {
                "capacity_gb": random.choice([128, 256, 512, 1024]),
                "bandwidth_gbps": random.choice([100, 200, 400]),
            }
        if resource_type == "STORAGE":
            return {
                "capacity_tb": random.choice([4, 8, 16, 32]),
                "throughput_gbps": random.choice([10, 20, 40]),
                "latency_ms": round(random.uniform(0.2, 3.0), 2),
            }
        if resource_type == "NIC":
            return {
                "bandwidth_gbps": random.choice([25, 50, 100, 200]),
                "latency_ms": round(random.uniform(0.1, 1.2), 2),
                "rdma_enabled": random.choice([True, False]),
            }
        return {
            "ports": random.choice([24, 32, 48]),
            "bandwidth_gbps": random.choice([100, 200, 400]),
            "latency_ms": round(random.uniform(0.05, 0.4), 2),
        }

    def _dynamic_state(self, resource_type: str) -> Dict:
        memory_free = random.choice([16, 32, 64, 128, 256, 512])
        if resource_type == "GPU":
            memory_free = random.choice([8, 16, 24, 40, 60, 80])
        return {
            "utilization": round(random.uniform(5, 90), 2),
            "memory_free": memory_free,
            "queue_length": random.randint(0, 20),
            "power_watt": round(random.uniform(80, 450), 2),
            "temperature": round(random.uniform(30, 80), 2),
            "available": random.random() > 0.12,
        }

    def _semantic_tags(self, resource_type: str) -> List[str]:
        base = {
            "CPU": ["general_compute", "batch"],
            "GPU": ["accelerator", "parallel"],
            "FPGA": ["streaming", "custom_logic"],
            "MEMORY": ["memory_pool", "high_bandwidth"],
            "STORAGE": ["persistent", "throughput"],
            "NIC": ["network", "rdma"],
            "SWITCH": ["fabric", "topology"],
        }
        return base[resource_type]

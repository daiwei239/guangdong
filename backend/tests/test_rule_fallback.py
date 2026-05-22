from types import SimpleNamespace

import networkx as nx

from app.algorithms.rule_filter import RuleFilter


def make_task(
    task_type="计算密集型",
    cpu_cores=8,
    memory_gb=32,
    bandwidth_gbps=50,
    min_gpu_memory_gb=16,
    max_utilization=90,
    max_latency_ms=10,
):
    """构造一个最小任务对象，只包含 RuleFilter 会用到的字段。"""
    return SimpleNamespace(
        task_id="task_test_rule_fallback",
        task_type=task_type,
        compute_req={"cpu_cores": cpu_cores},
        memory_req={"capacity_gb": memory_gb},
        network_req={"bandwidth_gbps": bandwidth_gbps},
        constraints={
            "min_gpu_memory_gb": min_gpu_memory_gb,
            "max_resource_utilization": max_utilization,
            "max_network_latency_ms": max_latency_ms,
        },
    )


def make_resource(
    resource_id,
    resource_type,
    available=True,
    utilization=20,
    static_attrs=None,
):
    """构造一个最小资源对象，只包含 RuleFilter 会用到的字段。"""
    return SimpleNamespace(
        id=resource_id,
        type=resource_type,
        static_attrs=static_attrs or {},
        dynamic_state={
            "available": available,
            "utilization": utilization,
        },
        topo_context={},
    )


def make_candidate(subgraph_id, nodes, final_score):
    """构造一个最小候选子图对象，只包含回退逻辑会用到的字段。"""
    return SimpleNamespace(
        subgraph_id=subgraph_id,
        nodes=nodes,
        final_score=final_score,
    )


def build_connected_graph(node_ids, latency_ms=2):
    """构造一个连通图，保证测试重点放在规则验证和回退上。"""
    graph = nx.Graph()
    for node_id in node_ids:
        graph.add_node(node_id)

    for left, right in zip(node_ids[:-1], node_ids[1:]):
        graph.add_edge(left, right, latency_ms=latency_ms, bandwidth_gbps=100)

    return graph


def test_validate_candidate_subgraph_passes_when_all_hard_rules_satisfied():
    """候选子图满足资源类型、容量、带宽、利用率和连通性时，规则验证应该通过。"""
    task = make_task()

    resources = [
        make_resource("gpu_ok", "GPU", static_attrs={"memory_total": 24, "fp16_tflops": 100}),
        make_resource("cpu_ok", "CPU", static_attrs={"cores": 16}),
        make_resource("mem_ok", "MEMORY", static_attrs={"capacity_gb": 64}),
        make_resource("nic_ok", "NIC", static_attrs={"bandwidth_gbps": 100}),
    ]
    graph = build_connected_graph([resource.id for resource in resources])

    is_valid, reasons = RuleFilter().validate_candidate_subgraph(
        task=task,
        resources=resources,
        graph=graph,
    )

    assert is_valid is True
    assert reasons == []


def test_validate_candidate_subgraph_fails_when_candidate_violates_hard_rules():
    """候选子图缺少必要资源或容量不足时，规则验证应该失败并返回原因。"""
    task = make_task()

    resources = [
        make_resource("gpu_bad", "GPU", static_attrs={"memory_total": 8, "fp16_tflops": 100}),
        make_resource("mem_bad", "MEMORY", static_attrs={"capacity_gb": 16}),
    ]
    graph = build_connected_graph([resource.id for resource in resources])

    is_valid, reasons = RuleFilter().validate_candidate_subgraph(
        task=task,
        resources=resources,
        graph=graph,
    )

    assert is_valid is False
    assert any("NIC/SWITCH" in reason for reason in reasons)
    assert any("GPU memory" in reason for reason in reasons)
    assert any("Memory capacity" in reason for reason in reasons)


def test_select_with_rule_fallback_skips_invalid_high_score_and_selects_valid_lower_score():
    """最高分候选失败时，系统应该记录失败原因，并回退选择后面第一个合法候选。"""
    task = make_task()

    resources = [
        make_resource("gpu_bad", "GPU", static_attrs={"memory_total": 8, "fp16_tflops": 100}),
        make_resource("cpu_bad", "CPU", static_attrs={"cores": 16}),
        make_resource("mem_bad", "MEMORY", static_attrs={"capacity_gb": 64}),
        make_resource("nic_bad", "NIC", static_attrs={"bandwidth_gbps": 100}),
        make_resource("gpu_ok", "GPU", static_attrs={"memory_total": 24, "fp16_tflops": 100}),
        make_resource("cpu_ok", "CPU", static_attrs={"cores": 16}),
        make_resource("mem_ok", "MEMORY", static_attrs={"capacity_gb": 64}),
        make_resource("nic_ok", "NIC", static_attrs={"bandwidth_gbps": 100}),
    ]
    resources_by_id = {resource.id: resource for resource in resources}
    graph = build_connected_graph([resource.id for resource in resources])

    high_score_invalid = make_candidate(
        subgraph_id="candidate_high_score_invalid",
        nodes=["gpu_bad", "cpu_bad", "mem_bad", "nic_bad"],
        final_score=95.0,
    )
    lower_score_valid = make_candidate(
        subgraph_id="candidate_lower_score_valid",
        nodes=["gpu_ok", "cpu_ok", "mem_ok", "nic_ok"],
        final_score=88.0,
    )

    selected, logs = RuleFilter().select_with_rule_fallback(
        task=task,
        candidates=[high_score_invalid, lower_score_valid],
        resources_by_id=resources_by_id,
        graph=graph,
    )

    assert selected.subgraph_id == "candidate_lower_score_valid"

    assert len(logs) == 2
    assert logs[0]["subgraph_id"] == "candidate_high_score_invalid"
    assert logs[0]["is_valid"] is False
    assert any("GPU memory" in reason for reason in logs[0]["reasons"])

    assert logs[1]["subgraph_id"] == "candidate_lower_score_valid"
    assert logs[1]["is_valid"] is True
    assert logs[1]["reasons"] == []


def test_select_with_rule_fallback_returns_none_when_all_candidates_fail():
    """所有候选都失败时，回退函数应该返回 None，并保留每个候选的失败日志。"""
    task = make_task(min_gpu_memory_gb=40)

    resources = [
        make_resource("gpu_1", "GPU", static_attrs={"memory_total": 8}),
        make_resource("cpu_1", "CPU", static_attrs={"cores": 16}),
        make_resource("mem_1", "MEMORY", static_attrs={"capacity_gb": 64}),
        make_resource("nic_1", "NIC", static_attrs={"bandwidth_gbps": 100}),
        make_resource("gpu_2", "GPU", static_attrs={"memory_total": 16}),
        make_resource("cpu_2", "CPU", static_attrs={"cores": 16}),
        make_resource("mem_2", "MEMORY", static_attrs={"capacity_gb": 64}),
        make_resource("nic_2", "NIC", static_attrs={"bandwidth_gbps": 100}),
    ]
    resources_by_id = {resource.id: resource for resource in resources}
    graph = build_connected_graph([resource.id for resource in resources])

    candidates = [
        make_candidate("candidate_fail_1", ["gpu_1", "cpu_1", "mem_1", "nic_1"], 95.0),
        make_candidate("candidate_fail_2", ["gpu_2", "cpu_2", "mem_2", "nic_2"], 90.0),
    ]

    selected, logs = RuleFilter().select_with_rule_fallback(
        task=task,
        candidates=candidates,
        resources_by_id=resources_by_id,
        graph=graph,
    )

    assert selected is None
    assert len(logs) == 2
    assert all(log["is_valid"] is False for log in logs)
    assert all(any("GPU memory" in reason for reason in log["reasons"]) for log in logs)

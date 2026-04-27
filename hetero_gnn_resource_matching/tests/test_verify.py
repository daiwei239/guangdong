from resource_mapping.verify import ResourceVerifier


def test_verify_satisfied_and_unsatisfied() -> None:
    from conftest import sample_candidate, sample_edges, sample_resources, sample_task

    verifier = ResourceVerifier(sample_resources(), sample_edges())
    ok = verifier.verify(sample_task(), sample_candidate())
    assert ok["capacity_satisfied"]
    assert ok["performance_satisfied"]
    assert ok["topology_satisfied"]
    bad_task = sample_task()
    bad_task["requirements"] = dict(bad_task["requirements"])
    bad_task["requirements"]["min_gpu_memory_gb"] = 1000
    bad = verifier.verify(bad_task, sample_candidate())
    assert not bad["capacity_satisfied"]
    assert "capacity:gpu_memory" in bad["violations"]

from resource_mapping.candidate_generator import CandidateGenerator


def test_candidate_generator_returns_candidate() -> None:
    from conftest import sample_edges, sample_resources, sample_task

    candidates = CandidateGenerator(sample_resources(), sample_edges()).generate(sample_task(), max_candidates=5)
    assert len(candidates) >= 1
    assert candidates[0]["task_id"] == "task_0000"

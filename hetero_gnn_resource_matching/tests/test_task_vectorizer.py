import numpy as np

from resource_mapping.task_vectorizer import TaskVectorizer


def test_task_vectorizer_fixed_dim_no_nan() -> None:
    from conftest import sample_task

    vectorizer = TaskVectorizer()
    v1 = vectorizer.transform_one(sample_task())
    v2 = vectorizer.transform_one(sample_task())
    assert v1.shape == v2.shape
    assert v1.shape[0] == vectorizer.dim
    assert not np.isnan(v1).any()

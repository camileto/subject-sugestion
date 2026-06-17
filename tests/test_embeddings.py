from app.services.embeddings import _cosine_similarity


def test_cosine_similarity_identical_vectors():
    assert _cosine_similarity([1, 0, 0], [1, 0, 0]) == 1.0


def test_cosine_similarity_orthogonal_vectors():
    assert _cosine_similarity([1, 0], [0, 1]) == 0.0


def test_cosine_similarity_opposite_vectors():
    assert _cosine_similarity([1, 0], [-1, 0]) == -1.0

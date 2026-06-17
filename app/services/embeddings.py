import numpy as np
from openai import OpenAI

from ..config import EMBEDDING_MODEL


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    a_arr, b_arr = np.array(a), np.array(b)
    return float(np.dot(a_arr, b_arr) / (np.linalg.norm(a_arr) * np.linalg.norm(b_arr)))


def max_similarity_to_history(client: OpenAI, candidate: str, history: list[str]) -> float:
    """Highest cosine similarity between `candidate` and any subject in
    `history`, computed via real embeddings instead of asking the LLM to
    self-estimate a similarity percentage (which it can't do reliably)."""
    if not history:
        return 0.0
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=[candidate, *history])
    vectors = [item.embedding for item in response.data]
    candidate_vec, history_vecs = vectors[0], vectors[1:]
    return max(_cosine_similarity(candidate_vec, h) for h in history_vecs)

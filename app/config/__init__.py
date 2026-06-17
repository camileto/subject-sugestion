import os

CHAT_MODEL = os.environ.get("CHAT_MODEL", "gpt-4o-mini")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")

# Variants whose subject is at least this similar (cosine similarity on
# embeddings) to one already sent to the customer are dropped, since
# asking the LLM to self-police a similarity percentage in the prompt is
# not reliable.
SIMILARITY_THRESHOLD = float(os.environ.get("SIMILARITY_THRESHOLD", "0.92"))

# A customer's own rate for a trigger only overrides the global fallback once
# there are at least this many sends — below that, one lucky/unlucky send
# would otherwise dominate a global rate built on far more data.
MIN_PERSONAL_SAMPLE_SIZE = int(os.environ.get("MIN_PERSONAL_SAMPLE_SIZE", "3"))

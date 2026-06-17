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

CALENDARIFIC_API_KEY = os.environ.get("CALENDARIFIC_API_KEY")
CALENDARIFIC_BASE_URL = "https://calendarific.com/api/v2/holidays"

# How far ahead to look for an upcoming occasion (Christmas, Black Friday,
# Mother's/Father's Day...) worth mentioning in a subject line.
OCCASION_LOOKAHEAD_DAYS = int(os.environ.get("OCCASION_LOOKAHEAD_DAYS", "30"))

# A given country/year's holiday calendar essentially never changes after
# publication, so a long cache TTL keeps usage well inside Calendarific's
# free tier (1,000 requests/day) no matter how many subject requests come in.
OCCASION_CACHE_TTL_SECONDS = int(os.environ.get("OCCASION_CACHE_TTL_SECONDS", "86400"))

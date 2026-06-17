from fastapi import FastAPI, HTTPException

from .clients.llm_client import generate_variants
from .clients.openai_client import get_client
from .config import CHAT_MODEL, MIN_PERSONAL_SAMPLE_SIZE, SIMILARITY_THRESHOLD
from .models import SubjectRequest, SubjectResponse, SubjectVariant
from .prompts import build_messages
from .services.embeddings import max_similarity_to_history
from .services.stats import compute_trigger_rates, compute_trigger_sample_sizes, resolve_rate

app = FastAPI(
    title="Subject Suggestion API",
    description=(
        "Suggests email subject lines personalized to a customer's own open "
        "history, using OpenAI structured outputs and embedding-based "
        "duplicate detection."
    ),
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/subjects", response_model=SubjectResponse)
def suggest_subjects(request: SubjectRequest) -> SubjectResponse:
    client = get_client()

    trigger_rates = compute_trigger_rates(request.sent_subjects)
    trigger_sample_sizes = compute_trigger_sample_sizes(request.sent_subjects)
    messages = build_messages(request, trigger_rates)
    raw_variants = generate_variants(client, messages, model=CHAT_MODEL)

    history_subjects = [s.subject for s in request.sent_subjects]
    variants: list[SubjectVariant] = []
    for raw in raw_variants:
        similarity = max_similarity_to_history(client, raw.subject, history_subjects)
        if similarity >= SIMILARITY_THRESHOLD:
            continue
        rate, rate_metric, rate_source = resolve_rate(
            raw.trigger,
            trigger_rates,
            trigger_sample_sizes,
            request.global_trigger_rates,
            request.metric_priority,
            MIN_PERSONAL_SAMPLE_SIZE,
        )
        variants.append(
            SubjectVariant(
                subject=raw.subject,
                trigger=raw.trigger,
                rationale=raw.rationale,
                similarity_to_history=round(similarity, 3),
                estimated_rate=rate,
                estimated_rate_metric=rate_metric,
                estimated_rate_source=rate_source,
            )
        )

    if not variants:
        raise HTTPException(
            status_code=502,
            detail="Could not generate subject suggestions distinct enough from the send history",
        )

    return SubjectResponse(customer_id=request.customer.user_id, variants=variants)

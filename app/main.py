import logging
from datetime import date

from fastapi import FastAPI, HTTPException

from .clients.llm_client import generate_variants
from .clients.openai_client import get_client
from .config import (
    CHAT_MODEL,
    CLAUDE_MODEL,
    GEMINI_MODEL,
    MIN_PERSONAL_SAMPLE_SIZE,
    OCCASION_LOOKAHEAD_DAYS,
    SIMILARITY_THRESHOLD,
)
from .models import SubjectRequest, SubjectResponse, SubjectVariant
from .prompts import build_messages
from .services.embeddings import max_similarity_to_history
from .services.occasions import get_upcoming_occasions
from .services.stats import compute_trigger_rates, compute_trigger_sample_sizes, resolve_rate

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Subject Suggestion API",
    description=(
        "Suggests email subject lines personalized to a customer's own open "
        "history, using structured LLM outputs (OpenAI, Anthropic, or "
        "Gemini — caller's choice) and embedding-based duplicate detection."
    ),
    version="0.2.0",
)

_PROVIDER_MODELS = {
    "openai": CHAT_MODEL,
    "anthropic": CLAUDE_MODEL,
    "gemini": GEMINI_MODEL,
}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/subjects", response_model=SubjectResponse)
def suggest_subjects(request: SubjectRequest) -> SubjectResponse:
    try:
        embeddings_client = get_client()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    trigger_rates = compute_trigger_rates(request.sent_subjects)
    trigger_sample_sizes = compute_trigger_sample_sizes(request.sent_subjects)

    upcoming_occasions: list[dict] = []
    if request.country:
        try:
            upcoming_occasions = get_upcoming_occasions(
                request.country,
                date.today(),
                OCCASION_LOOKAHEAD_DAYS,
                request.gift_occasion_lead_time_days,
            )
        except Exception:
            # Calendarific being down/misconfigured shouldn't block subject
            # generation — seasonal framing is a nice-to-have, not the core feature.
            logger.warning("Failed to fetch upcoming occasions for country=%s", request.country, exc_info=True)

    messages = build_messages(request, trigger_rates, upcoming_occasions)
    try:
        raw_variants = generate_variants(
            request.provider, messages, model=_PROVIDER_MODELS[request.provider]
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    history_subjects = [s.subject for s in request.sent_subjects]
    variants: list[SubjectVariant] = []
    for raw in raw_variants:
        similarity = max_similarity_to_history(embeddings_client, raw.subject, history_subjects)
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
                preheader=raw.preheader,
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

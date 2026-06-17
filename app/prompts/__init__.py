import json

from ..models import SubjectRequest

VALID_TRIGGERS = [
    "personalization",
    "urgency",
    "scarcity",
    "social_proof",
    "curiosity",
    "loss_aversion",
    "offer",
    "humor",
    "question",
]

SYSTEM_PROMPT = f"""You are an expert email marketing copywriter specialized in subject lines.

Rules:
- Generate subject lines in the requested language.
- Keep subjects concise: ideally under 50 characters, never over 70.
- Avoid spammy patterns: no ALL CAPS, no excessive punctuation, no "free" \
unless the product is actually free.
- Only reference a discount or promotion if the product data explicitly \
includes a promotional price lower than the full price. Never invent an offer.
- Each variant must declare exactly one trigger from this list: \
{", ".join(VALID_TRIGGERS)}.
- Personalize with the customer's name when available, naturally \
(write the actual name, not a "[name]" placeholder).
- Never repeat a subject the customer has already received, and vary the \
wording across the variants you return in this same response.
- Judge what has historically worked best per trigger using \
"trigger_rates_for_this_customer", reading metrics in the order given by \
"metric_priority" (e.g. conversion before click before open) — a trigger \
that converts is a better choice than one that merely gets opened. If this \
customer has no data for a trigger, you may use \
"trigger_rates_global_fallback" (rates across all customers) as a secondary \
signal, same metric priority order; if neither is available, use the \
product context and pick the trigger that best fits it.
- Don't let every variant default to the single best-known trigger: include \
at least one variant that explores a different trigger, so real open/click \
data for this customer can accumulate on more than one trigger over time.
- For each variant, briefly justify the trigger choice in "rationale" \
(one sentence).
"""


def build_messages(request: SubjectRequest, trigger_rates: dict[str, dict[str, float]]) -> list[dict]:
    customer = request.customer
    opened_examples = [s.subject for s in request.sent_subjects if s.opened][:5]
    recent_subjects = [s.subject for s in request.sent_subjects][-10:]

    context = {
        "customer": customer.model_dump(exclude_none=True),
        "products": [p.model_dump(exclude_none=True) for p in request.products],
        "trigger_rates_for_this_customer": trigger_rates,
        "trigger_rates_global_fallback": request.global_trigger_rates,
        "metric_priority": request.metric_priority,
        "subjects_this_customer_previously_opened": opened_examples,
        "subjects_recently_sent_avoid_repeating": recent_subjects,
        "language": request.language,
        "num_variants_requested": request.num_variants,
    }

    user_prompt = (
        "Generate subject line suggestions based on the following data:\n\n"
        + json.dumps(context, ensure_ascii=False, indent=2)
    )

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

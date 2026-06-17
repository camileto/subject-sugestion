from collections import defaultdict

from ..models import RateMetric, SentSubject

METRIC_FIELDS: dict[RateMetric, str] = {
    "conversion": "converted",
    "click": "clicked",
    "open": "opened",
}


def compute_trigger_rates(sent_subjects: list[SentSubject]) -> dict[str, dict[RateMetric, float]]:
    """Real open/click/conversion rate per trigger, each as a fraction of
    everything sent with that trigger to this customer. Replaces the static
    market-wide percentage table and the LLM-guessed rate used in earlier
    designs — these numbers are either grounded in actual data or absent,
    never invented."""
    totals: dict[str, int] = defaultdict(int)
    hits: dict[str, dict[RateMetric, int]] = defaultdict(lambda: {m: 0 for m in METRIC_FIELDS})
    for item in sent_subjects:
        totals[item.trigger] += 1
        for metric, field in METRIC_FIELDS.items():
            if getattr(item, field):
                hits[item.trigger][metric] += 1
    return {
        trigger: {metric: round(count / total, 3) for metric, count in hits[trigger].items()}
        for trigger, total in totals.items()
        if total > 0
    }


def compute_trigger_sample_sizes(sent_subjects: list[SentSubject]) -> dict[str, int]:
    """How many times each trigger was sent to this customer — used to
    decide whether their personal rate has enough data to be trusted over
    the global fallback."""
    counts: dict[str, int] = defaultdict(int)
    for item in sent_subjects:
        counts[item.trigger] += 1
    return dict(counts)


def resolve_rate(
    trigger: str,
    personal_rates: dict[str, dict[RateMetric, float]],
    personal_sample_sizes: dict[str, int],
    global_rates: dict[str, dict[RateMetric, float]],
    metric_priority: list[RateMetric],
    min_personal_sample_size: int,
) -> tuple[float | None, RateMetric | None, str | None]:
    """Walks metric_priority (e.g. conversion before click before open) and,
    for each metric, prefers this customer's own data over the cross-customer
    fallback — but only once that customer has enough sends of this trigger
    to trust it; below that, one lucky/unlucky send would otherwise dominate
    a global rate built on far more data. A higher-priority metric from
    either source wins over a lower-priority metric, since the caller's
    priority order reflects which signal is closest to real business value."""
    has_enough_personal_data = personal_sample_sizes.get(trigger, 0) >= min_personal_sample_size
    for metric in metric_priority:
        if has_enough_personal_data and metric in personal_rates.get(trigger, {}):
            return personal_rates[trigger][metric], metric, "customer_history"
        if metric in global_rates.get(trigger, {}):
            return global_rates[trigger][metric], metric, "global_history"
    return None, None, None

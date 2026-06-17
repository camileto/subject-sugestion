from app.models import SentSubject
from app.services.stats import compute_trigger_rates, compute_trigger_sample_sizes, resolve_rate


def test_compute_trigger_rates_open_click_conversion():
    sent = [
        SentSubject(subject="A", trigger="urgency", opened=True, clicked=True, converted=True),
        SentSubject(subject="B", trigger="urgency", opened=False, clicked=False, converted=False),
        SentSubject(subject="C", trigger="curiosity", opened=True, clicked=False, converted=False),
    ]
    rates = compute_trigger_rates(sent)
    assert rates["urgency"] == {"open": 0.5, "click": 0.5, "conversion": 0.5}
    assert rates["curiosity"] == {"open": 1.0, "click": 0.0, "conversion": 0.0}


def test_compute_trigger_rates_empty():
    assert compute_trigger_rates([]) == {}


def test_compute_trigger_sample_sizes():
    sent = [
        SentSubject(subject="A", trigger="urgency", opened=True),
        SentSubject(subject="B", trigger="urgency", opened=False),
        SentSubject(subject="C", trigger="curiosity", opened=True),
    ]
    assert compute_trigger_sample_sizes(sent) == {"urgency": 2, "curiosity": 1}


def test_resolve_rate_prefers_personal_over_global_when_sample_is_enough():
    rate, metric, source = resolve_rate(
        "urgency",
        {"urgency": {"conversion": 0.5}},
        {"urgency": 3},
        {"urgency": {"conversion": 0.2}},
        metric_priority=["conversion", "click", "open"],
        min_personal_sample_size=3,
    )
    assert (rate, metric, source) == (0.5, "conversion", "customer_history")


def test_resolve_rate_falls_back_to_global_when_personal_sample_too_small():
    # Only 1 send of this trigger for this customer — below the threshold of 3,
    # so a noisy single-send rate shouldn't override the better-sampled global rate.
    rate, metric, source = resolve_rate(
        "urgency",
        {"urgency": {"conversion": 0.0}},
        {"urgency": 1},
        {"urgency": {"conversion": 0.2}},
        metric_priority=["conversion", "click", "open"],
        min_personal_sample_size=3,
    )
    assert (rate, metric, source) == (0.2, "conversion", "global_history")


def test_resolve_rate_falls_back_to_global_for_same_metric():
    rate, metric, source = resolve_rate(
        "urgency",
        {},
        {},
        {"urgency": {"conversion": 0.2}},
        metric_priority=["conversion", "click", "open"],
        min_personal_sample_size=3,
    )
    assert (rate, metric, source) == (0.2, "conversion", "global_history")


def test_resolve_rate_falls_through_to_lower_priority_metric():
    # No conversion data anywhere for this trigger, but click data exists.
    rate, metric, source = resolve_rate(
        "urgency",
        {"urgency": {"click": 0.4}},
        {"urgency": 5},
        {"urgency": {"conversion": 0.1}},
        metric_priority=["conversion", "click", "open"],
        min_personal_sample_size=3,
    )
    assert (rate, metric, source) == (0.1, "conversion", "global_history")


def test_resolve_rate_none_when_no_data_anywhere():
    rate, metric, source = resolve_rate(
        "urgency", {}, {}, {}, metric_priority=["conversion", "click", "open"], min_personal_sample_size=3
    )
    assert (rate, metric, source) == (None, None, None)

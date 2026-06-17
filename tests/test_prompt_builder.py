from app.models import CustomerProfile, Product, SentSubject, SubjectRequest
from app.prompts import build_messages


def _sample_request() -> SubjectRequest:
    return SubjectRequest(
        customer=CustomerProfile(user_id="123", name="Maria"),
        products=[Product(name="Tênis Runner", price_full=300, price_promo=240)],
        sent_subjects=[
            SentSubject(subject="Maria, seu tênis te espera", trigger="curiosity", opened=True),
            SentSubject(subject="Última chance no seu carrinho", trigger="urgency", opened=False),
        ],
    )


def test_build_messages_has_system_and_user_roles():
    messages = build_messages(_sample_request(), trigger_rates={"curiosity": {"open": 1.0}})
    roles = [m["role"] for m in messages]
    assert roles == ["system", "user"]


def test_build_messages_includes_opened_history_in_user_prompt():
    messages = build_messages(_sample_request(), trigger_rates={})
    user_content = messages[1]["content"]
    assert "Maria, seu tênis te espera" in user_content
    assert "Tênis Runner" in user_content

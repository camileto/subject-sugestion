from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CustomerProfile(BaseModel):
    user_id: str
    name: str | None = None
    age: int | None = None
    gender: Literal["m", "f", "other"] | None = None


class Product(BaseModel):
    name: str
    category: str | None = None
    brand: str | None = None
    price_full: float | None = None
    price_promo: float | None = None
    stock_quantity: int | None = None


class SentSubject(BaseModel):
    subject: str
    trigger: str
    opened: bool
    clicked: bool = False
    converted: bool = False
    sent_at: datetime | None = None


RateMetric = Literal["conversion", "click", "open"]


class SubjectRequest(BaseModel):
    customer: CustomerProfile
    products: list[Product] = Field(..., min_length=1)
    sent_subjects: list[SentSubject] = []
    global_trigger_rates: dict[str, dict[RateMetric, float]] = {}
    metric_priority: list[RateMetric] = ["conversion", "click", "open"]
    country: str | None = Field(default=None, description="ISO-3166 country code, e.g. BR, US")
    num_variants: int = Field(default=3, ge=1, le=5)
    language: str = "pt-BR"


class SubjectVariant(BaseModel):
    subject: str
    trigger: str
    rationale: str
    similarity_to_history: float
    estimated_rate: float | None = None
    estimated_rate_metric: RateMetric | None = None
    estimated_rate_source: Literal["customer_history", "global_history"] | None = None


class SubjectResponse(BaseModel):
    customer_id: str
    variants: list[SubjectVariant]

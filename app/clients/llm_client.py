from openai import OpenAI
from pydantic import BaseModel


class RawVariant(BaseModel):
    subject: str
    trigger: str
    rationale: str


class RawVariantList(BaseModel):
    variants: list[RawVariant]


def generate_variants(client: OpenAI, messages: list[dict], model: str) -> list[RawVariant]:
    """Uses OpenAI structured outputs (response_format=pydantic model) so the
    response is guaranteed to match the schema — no manual/defensive JSON
    parsing needed on the way out."""
    completion = client.beta.chat.completions.parse(
        model=model,
        messages=messages,
        response_format=RawVariantList,
        temperature=0.9,
    )
    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise RuntimeError("The model did not return structured output")
    return parsed.variants

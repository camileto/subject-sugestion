# subject-sugestion

A FastAPI service that suggests email marketing subject lines, personalized
to each customer's own open/click history, using the OpenAI API.

## Design decisions

A few choices here are deliberate reactions to common pitfalls in this kind
of LLM-powered copywriting tool:

- **No invented numbers.** The API never asks the LLM to "estimate" a rate —
  that's a number the model has no real basis for. `estimated_rate` is always
  a real, computed average of open, click, or conversion (whichever the
  caller's `metric_priority` ranks highest and actually has data, reported in
  `estimated_rate_metric`). It prefers this customer's own history
  (`estimated_rate_source: "customer_history"`) once there are at least
  `MIN_PERSONAL_SAMPLE_SIZE` sends of that trigger — below that, one
  lucky/unlucky send would otherwise outweigh a much better-sampled number —
  falling back to the cross-customer rate from the caller's
  `global_trigger_rates` (`"global_history"`), or `null` if neither exists.
  It's never a market research benchmark — those numbers come from a
  different audience, product, language and sender reputation, and open-rate
  benchmarks specifically have been further distorted industry-wide since
  Apple Mail Privacy Protection started auto-opening tracking pixels.
- **No LLM self-policing of similarity.** Asking a language model to judge
  "is this subject more than 80% similar to one I already sent?" doesn't
  work reliably — it's not something it can compute. This service generates
  several candidates, embeds them (`text-embedding-3-small`), and drops any
  candidate whose cosine similarity to a previously sent subject crosses
  `SIMILARITY_THRESHOLD`. That's an actual computation, not a guess.
- **Structured outputs, not prompt-engineered JSON.** The LLM call uses
  OpenAI's structured outputs (Pydantic response format), so the response is
  guaranteed to match the schema. No defensive "is this a string or an
  object?" parsing on the way out.
- **Personalization comes from real history, not generic copywriting trivia.**
  The prompt includes the specific subjects this customer has opened before
  and this customer's own per-trigger open rates — not a static market-wide
  benchmark table. The fewer generic instructions in the prompt, the more
  attention the model has for the actual customer data.
- **No blanket ban on mentioning discounts.** A subject can reference a
  promotion only if the product data actually includes a promotional price
  lower than the full price — driven by the data, not an absolute rule that
  fights against the "offer" trigger.

## API

### `POST /api/v1/subjects`

Request body:

```json
{
  "customer": {
    "user_id": "123",
    "name": "Maria",
    "age": 29,
    "gender": "f"
  },
  "products": [
    {
      "name": "Tênis Runner",
      "category": "fitness",
      "brand": "Acme",
      "price_full": 300,
      "price_promo": 240,
      "stock_quantity": 4
    }
  ],
  "sent_subjects": [
    {
      "subject": "Maria, seu tênis te espera",
      "trigger": "curiosity",
      "opened": true,
      "clicked": false,
      "converted": false
    }
  ],
  "global_trigger_rates": {
    "curiosity": {"open": 0.34, "click": 0.12, "conversion": 0.04},
    "loss_aversion": {"open": 0.41, "click": 0.2, "conversion": 0.09}
  },
  "metric_priority": ["conversion", "click", "open"],
  "num_variants": 3,
  "language": "pt-BR"
}
```

`global_trigger_rates` is optional: a cross-customer rate per trigger and
metric, computed by the caller (this service is stateless and has no
database of its own) — used only as a fallback when this specific customer
doesn't have enough sends of a given trigger yet. `metric_priority` is also
optional and defaults to `["conversion", "click", "open"]` — conversion is
the metric closest to real business value, so it's preferred whenever data
for it exists; open rate is the noisiest signal and only used as a last
resort.

Response:

```json
{
  "customer_id": "123",
  "variants": [
    {
      "subject": "Maria, ainda dá tempo de levar o Runner",
      "trigger": "loss_aversion",
      "rationale": "Builds on a discount that's about to disappear, similar to what previously worked for this customer.",
      "similarity_to_history": 0.41,
      "estimated_rate": 0.09,
      "estimated_rate_metric": "conversion",
      "estimated_rate_source": "global_history"
    }
  ]
}
```

## Running locally

```bash
pip install -r requirements.txt
cp .env.example .env
# edit .env with your OpenAI API key

set -a; source .env; set +a
uvicorn app.main:app --reload
```

Docs available at `http://localhost:8000/docs`.

## Running with Docker

```bash
cp .env.example .env
# edit .env with your OpenAI API key

docker build -t subject-sugestion .
docker run --rm -p 8000:8000 --env-file .env subject-sugestion
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Tests cover the deterministic logic (open-rate stats, cosine similarity,
prompt construction) without calling the OpenAI API.

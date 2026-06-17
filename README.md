# subject-sugestion

A FastAPI service that suggests email marketing subject lines, personalized
to each customer's own open/click/conversion history and (optionally)
upcoming local holidays and commercial dates, using the OpenAI API.

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
- **No invented holidays, either.** Seasonal subject lines ("don't miss it
  this Christmas") need a real upcoming date, and LLMs are unreliable at
  recalling exactly when a country-specific commercial date like Black
  Friday or Mother's Day falls in a given year. So this service resolves
  `country` against the Calendarific API and only ever hands the model
  dates that API actually returned — never lets it guess a holiday or date
  on its own.

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
      "name": "Runner Sneakers",
      "category": "fitness",
      "brand": "Acme",
      "price_full": 300,
      "price_promo": 240,
      "stock_quantity": 4
    }
  ],
  "sent_subjects": [
    {
      "subject": "Maria, your sneakers are waiting",
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
  "language": "en"
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

#### `language`

Free-form string, not validated or restricted by the API — it's passed
straight to the LLM as the language to write the subject lines in, so
anything the model itself can write well in works. Examples:

| Code | Language |
|------|----------|
| `en` | English |
| `pt-BR` | Portuguese (Brazil) |
| `es` | Spanish |
| `fr` | French |
| `de` | German |
| `it` | Italian |

There's no fixed list enforced in code — these are just examples of values
that work well, not a guarantee of support.

#### `country`

Optional ISO-3166 country code (e.g. `BR`, `US`). When set, the service
looks up real upcoming dates — official holidays and commercial
observances like Black Friday, Mother's/Father's Day, Valentine's Day —
from the [Calendarific](https://calendarific.com/) API, within
`OCCASION_LOOKAHEAD_DAYS` (default 30) of today. Results are cached in
memory per country/year for `OCCASION_CACHE_TTL_SECONDS` (default 24h),
since a calendar barely changes after publication — this keeps usage far
under Calendarific's free tier (1,000 requests/day) regardless of traffic.

The LLM is told about these dates as real facts ("Christmas is in 12 days")
and is instructed to use one only when it has a genuine thematic connection
to the product's category — a gift occasion fits something people buy as a
gift, a civic date like Independence Day only fits products actually tied
to that theme — rather than referencing whatever's chronologically closest.
It's still never allowed to invent a holiday or date that wasn't actually
returned by the API, for the same reason it's never allowed to invent an
open rate.

If `country` is omitted, or the Calendarific call fails for any reason
(missing `CALENDARIFIC_API_KEY`, network error, rate limit), subject
generation proceeds normally with no seasonal framing — this is a
nice-to-have enrichment, never a hard dependency.

The occasion cache is in-memory, per process: it resets on restart and
isn't shared across multiple workers/replicas. That's fine at this volume
(each one independently stays well under Calendarific's 1,000 requests/day
free tier), but if this ever runs at a scale where that matters, swap it
for a shared store like Redis.

Response:

```json
{
  "customer_id": "123",
  "variants": [
    {
      "subject": "Maria, there's still time to grab the Runner",
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
# (optional) add a free Calendarific API key if you want to use "country"

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

Tests cover the deterministic logic (rate stats, cosine similarity, prompt
construction, occasion windowing/caching) without calling the OpenAI or
Calendarific APIs.

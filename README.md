# email-subject-suggestion

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
- **Preheader isn't an afterthought.** Inbox apps (Gmail, Outlook...) show a
  preview snippet next to the subject, pulled from the start of the email
  body unless something better is supplied — usually template boilerplate
  if no one bothers. Each variant comes with a `preheader` generated
  alongside its `subject`, written to complement it rather than repeat it,
  since the two work together to earn the open.

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

Response:

```json
{
  "customer_id": "123",
  "variants": [
    {
      "subject": "Maria, there's still time to grab the Runner",
      "preheader": "The promo price disappears soon — yours is still in stock.",
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

The fields below break down each part of the request body in more detail.

`global_trigger_rates` is optional: a cross-customer rate per trigger and
metric, computed by the caller (this service is stateless and has no
database of its own) — used only as a fallback when this specific customer
doesn't have enough sends of a given trigger yet. `metric_priority` is also
optional and defaults to `["conversion", "click", "open"]` — conversion is
the metric closest to real business value, so it's preferred whenever data
for it exists; open rate is the noisiest signal and only used as a last
resort.

#### `email_type`

Optional free-form string describing the behavioral context this email is
part of. Unlike `trigger`, it's not picked by the model — you tell it what
flow this send belongs to, and it changes how much purchase intent the
copy assumes:

| Value | When to use |
|-------|-------------|
| `abandoned_cart` | Added to cart, didn't check out |
| `browse_abandonment` | Viewed the product, didn't add to cart |
| `back_in_stock` | A product they wanted is available again |
| `price_drop` | A product they viewed/saved just got cheaper |
| `win_back` | Inactive customer, hasn't opened/bought in a while |
| `post_purchase_upsell` | Already bought, offering a complement/upgrade |
| `replenishment` | Consumable product, likely time to reorder |
| `welcome` | New subscriber/customer, first touch |
| `standard_campaign` | Generic broadcast, no behavioral trigger |

These are suggestions, not an enforced enum — same philosophy as
`language`. The difference it makes is real: the same perfume with no
checkout produced *"Sarah, complete your cart for Velvet Bloom!"* for
`abandoned_cart` versus *"Still thinking about Velvet Bloom?"* for
`browse_abandonment` — the first assumes near-purchase intent, the second
doesn't, because the underlying behavior is genuinely different.

#### `customer.age` / `customer.gender`

Both optional. When provided, they're passed straight to the LLM as part
of the customer context and do influence the copy it writes — not just
whether the name is used, but tone and angle. For example, the same
anti-aging cream produced *"Revitalize Your Skin Tonight"* for a 19-year-old
and *"Rediscover Youthful Skin Today"* for a 58-year-old, without any
explicit instruction asking for that difference.

That's a deliberate trade-off worth knowing about: there's no prompt rule
telling the model *how* to use age/gender (unlike every other signal in
this service, which is tightly controlled), so the effect is real but
unguided — closer to "the model's own judgment" than to a tested feature.
Omit either field if you'd rather personalization come only from the name
and real send history.

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

**Black Friday / Cyber Monday.** Calendarific only tags these under the
`US` country bucket, even though the date itself is the same worldwide
(Brazil included). So for any other country, this service also checks the
real `US` entry for these two specific names and borrows it — never
re-derives the date with its own formula, and never overrides a
country's own entry if Calendarific ever adds one.

**Lead time is enforced in code, not by prompt.** A subject offering a
Mother's Day gift the day before Mother's Day is useless — shipping won't
make it. The first version of this rule just told the LLM not to do that,
and `gpt-4o-mini` followed it inconsistently — testing it side by side
with `gpt-4o` showed the same gap, just smaller, so the fix isn't "use a
better model." `gift_occasion_lead_time_days` (default `2`) is enforced
in [services/occasions.py](app/services/occasions.py) instead: any
gift-giving occasion (Christmas, Mother's/Father's Day, Valentine's)
closer than that is dropped from `upcoming_occasions` before the LLM ever
sees it, so there's nothing left for it to misuse. Shopping events
(Black Friday, Cyber Monday) are exempt — the day of is exactly when
they're useful, since the event itself is the peak moment, not a delivery
deadline.

**Example.** A BBQ product, requested a few days before Father's Day:

```json
{
  "customer": {"user_id": "us-001", "name": "Jake"},
  "products": [
    {"name": "Grill Master BBQ Set", "category": "home", "price_full": 180, "price_promo": 140, "stock_quantity": 15}
  ],
  "sent_subjects": [],
  "country": "US",
  "num_variants": 3,
  "language": "en"
}
```

```json
{
  "customer_id": "us-001",
  "variants": [
    {"subject": "Jake, Get Your BBQ Set for $140!", "trigger": "offer", "...": "..."},
    {"subject": "Only 15 Grill Master Sets Left!", "trigger": "scarcity", "...": "..."},
    {"subject": "Father's Day is Coming! Perfect BBQ Gift!", "trigger": "curiosity", "...": "..."}
  ]
}
```

The same product requested for a country/date with no occasion in range —
or a product with no thematic fit to whatever occasion is upcoming, like a
perfume in that same window — gets no seasonal variant at all; the model
isn't required to use one just because the field is present.

Two more real outputs, showing the anticipation/urgency split described
above:

| Occasion | `days_until` | Subject | Preheader |
|---|---|---|---|
| Christmas | 18 (anticipation) | *"Don't miss out on Velvet Bloom for Christmas!"* | *"Grab this stunning perfume before the holiday rush."* |
| Black Friday | 0 (shopping event, day-of urgency) | *"Last Chance for Black Friday Headphones!"* | *"Our wireless headphones are going fast at a great price."* |

Note the Christmas one only happens because `days_until=18` clears the
`gift_occasion_lead_time_days` default of `2` — closer than that, this
exact occasion would never have reached the model in the first place.

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

docker build -t email-subject-suggestion .
docker run --rm -p 8000:8000 --env-file .env email-subject-suggestion
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Tests cover the deterministic logic (rate stats, cosine similarity, prompt
construction, occasion windowing/caching) without calling the OpenAI or
Calendarific APIs.

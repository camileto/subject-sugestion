import time
from datetime import date, timedelta

from ..clients.calendarific_client import fetch_holidays
from ..config import OCCASION_CACHE_TTL_SECONDS

# Calendarific bundles every US state's own proclamation of the same holiday
# (e.g. 30+ separate "Juneteenth" entries, one per state) plus UN/worldwide
# awareness days that aren't useful marketing angles. Keeping only
# nationwide entries of these two types is what's left over: real national
# holidays and the commercial observances (Black Friday, Mother's/Father's
# Day, Valentine's Day...) that are actually worth referencing in a subject.
_RELEVANT_TYPES = {"National holiday", "Observance"}

_cache: dict[tuple[str, int], tuple[float, list[dict]]] = {}


def _get_holidays_cached(country: str, year: int) -> list[dict]:
    cached = _cache.get((country, year))
    now = time.monotonic()
    if cached and now - cached[0] < OCCASION_CACHE_TTL_SECONDS:
        return cached[1]
    holidays = fetch_holidays(country, year)
    _cache[(country, year)] = (now, holidays)
    return holidays


def get_upcoming_occasions(country: str, reference_date: date, lookahead_days: int) -> list[dict]:
    """Real, computed occasions within the window — never invented by the
    LLM. Calendarific covers both official holidays and commercial
    observances (Black Friday, Mother's/Father's Day, Valentine's Day),
    which is what makes it useful here beyond pure public-holiday APIs."""
    end_date = reference_date + timedelta(days=lookahead_days)
    years_needed = {reference_date.year, end_date.year}

    seen_names_by_date: set[tuple[str, str]] = set()
    occasions = []
    for year in years_needed:
        for holiday in _get_holidays_cached(country, year):
            if holiday.get("locations") != "All" or not _RELEVANT_TYPES.intersection(holiday.get("type", [])):
                continue
            holiday_date = date.fromisoformat(holiday["date"]["iso"][:10])
            if not (reference_date <= holiday_date <= end_date):
                continue
            key = (holiday["name"], holiday_date.isoformat())
            if key in seen_names_by_date:
                continue
            seen_names_by_date.add(key)
            occasions.append(
                {
                    "name": holiday["name"],
                    "date": holiday_date.isoformat(),
                    "days_until": (holiday_date - reference_date).days,
                }
            )
    return sorted(occasions, key=lambda o: o["days_until"])

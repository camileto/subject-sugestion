import httpx

from ..config import CALENDARIFIC_API_KEY, CALENDARIFIC_BASE_URL


def fetch_holidays(country: str, year: int) -> list[dict]:
    """One real HTTP call to Calendarific for a country/year. Kept isolated
    so the caching layer never has to know about HTTP — tests monkeypatch
    this function instead of mocking the network."""
    if not CALENDARIFIC_API_KEY:
        raise RuntimeError("CALENDARIFIC_API_KEY environment variable is not set")
    response = httpx.get(
        CALENDARIFIC_BASE_URL,
        params={"api_key": CALENDARIFIC_API_KEY, "country": country, "year": year},
        timeout=5.0,
    )
    response.raise_for_status()
    return response.json()["response"]["holidays"]

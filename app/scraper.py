import httpx
import re
from bs4 import BeautifulSoup
from typing import Optional

RAWG_BASE = "https://api.rawg.io/api"
PSN_SEARCH = "https://store.playstation.com/en-gb/search/{slug}"


async def fetch_ps5_games(api_key: str, page_size: int = 40, pages: int = 5) -> list[dict]:
    """Fetch PS5 games from RAWG, newest first. Returns normalized game dicts."""
    games: list[dict] = []
    async with httpx.AsyncClient(timeout=30) as client:
        for page in range(1, pages + 1):
            resp = await client.get(f"{RAWG_BASE}/games", params={
                "key": api_key,
                "platforms": 187,      # 187 = PS5
                "ordering": "-released",
                "page_size": page_size,
                "page": page,
            })
            resp.raise_for_status()
            data = resp.json()
            for r in data.get("results", []):
                games.append(_normalize_rawg_game(r))
            if not data.get("next"):
                break
    return games


async def fetch_game_tags(api_key: str, rawg_id: str) -> list[str]:
    """Fetch detailed tags for a single game from RAWG."""
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.get(f"{RAWG_BASE}/games/{rawg_id}", params={"key": api_key})
            resp.raise_for_status()
            data = resp.json()
            return [t["slug"] for t in data.get("tags", [])]
        except (httpx.HTTPError, KeyError):
            return []


async def search_rawg_game(api_key: str, query: str) -> list[dict]:
    """Search RAWG for a game by name. Used for preferences page autocomplete."""
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.get(f"{RAWG_BASE}/games", params={
                "key": api_key,
                "search": query,
                "page_size": 8,
            })
            resp.raise_for_status()
            data = resp.json()
            return [
                {
                    "rawg_id": str(r["id"]),
                    "title": r["name"],
                    "cover_url": r.get("background_image", ""),
                    "tags": [],  # fetched separately if user selects
                }
                for r in data.get("results", [])
            ]
        except httpx.HTTPError:
            return []


async def get_psn_price(psn_url: str) -> Optional[float]:
    """
    Scrape current EUR price from a PSN Store product page.
    Returns None if unavailable or scraping fails.
    """
    if not psn_url:
        return None
    headers = {"User-Agent": "Mozilla/5.0 (compatible; PS5Radar/1.0)"}
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        try:
            resp = await client.get(psn_url, headers=headers)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            # PSN Store uses data-qa attributes; try multiple selectors
            for selector in [
                "[data-qa='mfeCtaMain#offer0#finalPrice']",
                ".psw-t-title-m",
                "span[data-testid='price']",
            ]:
                el = soup.select_one(selector)
                if el:
                    text = el.get_text(strip=True)
                    match = re.search(r"[\d]+[.,][\d]{2}", text)
                    if match:
                        return float(match.group().replace(",", "."))
            return None
        except (httpx.RequestError, httpx.HTTPStatusError):
            return None


def build_psn_url(slug: str) -> str:
    return f"https://store.playstation.com/en-gb/product/{slug}"


def build_ign_url(slug: str) -> str:
    return f"https://www.ign.com/games/{slug}"


def _normalize_rawg_game(r: dict) -> dict:
    slug = r.get("slug", "")
    return {
        "id": str(r["id"]),
        "title": r["name"],
        "cover_url": r.get("background_image", ""),
        "genres": [g["slug"] for g in r.get("genres", [])],
        "tags": [],  # populated separately via fetch_game_tags
        "perspective": "unknown",
        "rawg_rating": r.get("rating", 0),
        "metacritic": r.get("metacritic"),
        "psn_price_eur": None,
        "psn_url": build_psn_url(slug),
        "ign_url": build_ign_url(slug),
        "match_score": 0,
    }

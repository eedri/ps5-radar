import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from app.scraper import fetch_ps5_games, fetch_game_tags, get_psn_price

MOCK_RAWG_LIST = {
    "results": [
        {
            "id": 12345,
            "name": "Test Game",
            "background_image": "https://media.rawg.io/cover.jpg",
            "rating": 4.2,
            "metacritic": 81,
            "genres": [{"slug": "action"}, {"slug": "adventure"}],
            "slug": "test-game",
            "released": "2024-11-15",
        }
    ],
    "next": None,
}

MOCK_RAWG_DETAIL = {
    "id": 12345,
    "tags": [
        {"slug": "third-person"},
        {"slug": "open-world"},
        {"slug": "story-rich"},
    ],
}

@pytest.mark.asyncio
async def test_fetch_ps5_games_returns_normalized_list():
    with patch("app.scraper.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = MOCK_RAWG_LIST
        mock_client.get.return_value = mock_resp

        games = await fetch_ps5_games(api_key="test-key", page_size=1)

    assert len(games) == 1
    g = games[0]
    assert g["id"] == "12345"
    assert g["title"] == "Test Game"
    assert g["rawg_rating"] == 4.2
    assert g["metacritic"] == 81
    assert "action" in g["genres"]


@pytest.mark.asyncio
async def test_fetch_game_tags_returns_tag_slugs():
    with patch("app.scraper.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = MOCK_RAWG_DETAIL
        mock_client.get.return_value = mock_resp

        tags = await fetch_game_tags(api_key="test-key", rawg_id="12345")

    assert "third-person" in tags
    assert "open-world" in tags


@pytest.mark.asyncio
async def test_get_psn_price_returns_none_on_error():
    with patch("app.scraper.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client.get.side_effect = httpx.RequestError("timeout")

        price = await get_psn_price("https://store.playstation.com/nonexistent")

    assert price is None

import pytest
import pytest_asyncio
import aiosqlite
import os
from app.database import init_db, upsert_game, get_all_games, set_user_status, get_user_status, add_liked_game, remove_liked_game, get_liked_games, get_new_games, update_all_scores, remove_user_status

TEST_DB = "/tmp/test_radar.db"

@pytest_asyncio.fixture
async def db():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    await init_db(TEST_DB)
    yield TEST_DB
    os.remove(TEST_DB)

@pytest.mark.asyncio
async def test_init_db_creates_tables(db):
    async with aiosqlite.connect(db) as conn:
        cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in await cursor.fetchall()}
    assert {"games", "user_library", "liked_games", "email_log"}.issubset(tables)

@pytest.mark.asyncio
async def test_upsert_and_get_game(db):
    game = {
        "id": "rawg-123",
        "title": "Test Game",
        "cover_url": "https://example.com/cover.jpg",
        "genres": ["action", "adventure"],
        "tags": ["third-person", "open-world"],
        "perspective": "third-person",
        "rawg_rating": 4.5,
        "metacritic": 85,
        "psn_price_eur": 39.99,
        "psn_url": "https://store.playstation.com/test",
        "ign_url": "https://ign.com/test",
        "match_score": 75,
    }
    await upsert_game(db, game)
    games = await get_all_games(db)
    assert len(games) == 1
    assert games[0]["title"] == "Test Game"
    assert games[0]["rawg_rating"] == 4.5

@pytest.mark.asyncio
async def test_set_and_get_user_status(db):
    game = {
        "id": "rawg-456", "title": "G2", "cover_url": "", "genres": [], "tags": [],
        "perspective": "unknown", "rawg_rating": 3.0, "metacritic": None,
        "psn_price_eur": None, "psn_url": "", "ign_url": "", "match_score": 50,
    }
    await upsert_game(db, game)
    await set_user_status(db, "rawg-456", "played")
    status = await get_user_status(db, "rawg-456")
    assert status == "played"

@pytest.mark.asyncio
async def test_liked_games_roundtrip(db):
    liked = {"rawg_id": "rawg-789", "title": "God of War", "cover_url": "", "tags": ["third-person", "action"]}
    await add_liked_game(db, liked)
    games = await get_liked_games(db)
    assert len(games) == 1
    assert games[0]["title"] == "God of War"
    await remove_liked_game(db, "rawg-789")
    games = await get_liked_games(db)
    assert len(games) == 0

@pytest.mark.asyncio
async def test_get_new_games(db):
    game = {
        "id": "new-game", "title": "New Game", "cover_url": "", "genres": [], "tags": [],
        "perspective": "unknown", "rawg_rating": 4.0, "metacritic": None,
        "psn_price_eur": None, "psn_url": "", "ign_url": "", "match_score": 60,
    }
    await upsert_game(db, game)
    new = await get_new_games(db, days=7)
    assert any(g["id"] == "new-game" for g in new)

@pytest.mark.asyncio
async def test_upsert_overwrites_existing(db):
    game = {
        "id": "rawg-123", "title": "Original", "cover_url": "", "genres": [], "tags": [],
        "perspective": "unknown", "rawg_rating": 3.0, "metacritic": None,
        "psn_price_eur": None, "psn_url": "", "ign_url": "", "match_score": 40,
    }
    await upsert_game(db, game)
    game["title"] = "Updated"
    game["rawg_rating"] = 4.5
    await upsert_game(db, game)
    games = await get_all_games(db)
    assert len(games) == 1
    assert games[0]["title"] == "Updated"
    assert games[0]["rawg_rating"] == 4.5

@pytest.mark.asyncio
async def test_update_all_scores(db):
    game = {
        "id": "g1", "title": "G1", "cover_url": "", "genres": [], "tags": [],
        "perspective": "unknown", "rawg_rating": 4.0, "metacritic": None,
        "psn_price_eur": None, "psn_url": "", "ign_url": "", "match_score": 0,
    }
    await upsert_game(db, game)
    await update_all_scores(db, {"g1": 88})
    games = await get_all_games(db)
    assert games[0]["match_score"] == 88

@pytest.mark.asyncio
async def test_remove_user_status(db):
    game = {
        "id": "g2", "title": "G2", "cover_url": "", "genres": [], "tags": [],
        "perspective": "unknown", "rawg_rating": 3.5, "metacritic": None,
        "psn_price_eur": None, "psn_url": "", "ign_url": "", "match_score": 50,
    }
    await upsert_game(db, game)
    await set_user_status(db, "g2", "played")
    await remove_user_status(db, "g2")
    status = await get_user_status(db, "g2")
    assert status is None

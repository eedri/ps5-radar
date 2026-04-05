import pytest
import os
from httpx import AsyncClient, ASGITransport
from app.main import create_app

TEST_DB = "/tmp/test_routes.db"
os.environ.setdefault("RAWG_API_KEY", "test")
os.environ.setdefault("RESEND_API_KEY", "test")
os.environ.setdefault("RESEND_FROM_EMAIL", "test@test.com")
os.environ.setdefault("ALERT_EMAIL", "test@test.com")
os.environ["DATABASE_URL"] = TEST_DB

@pytest.fixture(autouse=True)
def clean_db():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

@pytest.mark.asyncio
async def test_index_returns_200():
    from app.database import init_db
    await init_db(TEST_DB)
    app = create_app(TEST_DB)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/")
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_new_page_returns_200():
    from app.database import init_db
    await init_db(TEST_DB)
    app = create_app(TEST_DB)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/new")
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_library_returns_200():
    from app.database import init_db
    await init_db(TEST_DB)
    app = create_app(TEST_DB)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/library")
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_preferences_returns_200():
    from app.database import init_db
    await init_db(TEST_DB)
    app = create_app(TEST_DB)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/preferences")
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_set_library_status_redirects():
    from app.database import init_db, upsert_game
    await init_db(TEST_DB)
    await upsert_game(TEST_DB, {
        "id": "g1", "title": "Test", "cover_url": "", "genres": [], "tags": [],
        "perspective": "unknown", "rawg_rating": 4.0, "metacritic": None,
        "psn_price_eur": None, "psn_url": "", "ign_url": "", "match_score": 70,
    })
    app = create_app(TEST_DB)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/library/set", data={"game_id": "g1", "status": "played"}, follow_redirects=False)
    assert resp.status_code == 303

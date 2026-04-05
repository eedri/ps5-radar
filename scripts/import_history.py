"""
One-time script to bulk-import play history into the radar DB.
Searches each title on RAWG, upserts it into games, marks it played.
"""
import asyncio
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

import httpx
import aiosqlite

DB = os.environ.get("DATABASE_URL", "radar.db")
API_KEY = os.environ["RAWG_API_KEY"]
RAWG_BASE = "https://api.rawg.io/api"

HISTORY = [
    "Star Wars Outlaws",
    "Sackboy: A Big Adventure",
    "Assassin's Creed Shadows",
    "SILENT HILL f",
    "Alan Wake 2",
    "SILENT HILL 2",
    "Outcast - A New Beginning",
    "Carmen Sandiego",
    "Marvel's Spider-Man: Miles Morales",
    "Disco Elysium",
    "Horizon Forbidden West",
    "God of War Ragnarök",
    "The Last of Us Part I",
    "Stray",
    "A Plague Tale: Innocence",
    "Yakuza: Like A Dragon",
    "The Last of Us Remastered",
    "Shadow of the Tomb Raider",
    "Horizon Zero Dawn",
    "Zombie Army 4: Dead War",
    "Remnant: From the Ashes",
    "Ratchet & Clank",
    "FINAL FANTASY VII REMAKE",
    "Concrete Genie",
    "Just Cause 4",
    "Middle-earth: Shadow of War",
]


async def search_rawg(client: httpx.AsyncClient, title: str) -> dict | None:
    resp = await client.get(f"{RAWG_BASE}/games", params={
        "key": API_KEY,
        "search": title,
        "page_size": 3,
    })
    resp.raise_for_status()
    results = resp.json().get("results", [])
    if not results:
        return None
    return results[0]


async def upsert_and_mark_played(conn: aiosqlite.Connection, game: dict) -> None:
    today = date.today().isoformat()
    slug = game.get("slug", "")
    genres = json.dumps([g["slug"] for g in game.get("genres", [])])
    await conn.execute("""
        INSERT INTO games (id, title, cover_url, genres, tags, perspective,
            rawg_rating, metacritic, psn_price_eur, psn_url, ign_url,
            match_score, first_seen, last_updated)
        VALUES (?, ?, ?, ?, '[]', 'unknown', ?, ?, NULL, ?, ?, 0, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title=excluded.title,
            cover_url=excluded.cover_url,
            last_updated=excluded.last_updated
    """, (
        str(game["id"]), game["name"], game.get("background_image", ""),
        genres, game.get("rating", 0), game.get("metacritic"),
        f"https://store.playstation.com/en-gb/product/{slug}",
        f"https://www.ign.com/games/{slug}",
        today, today,
    ))
    await conn.execute("""
        INSERT INTO user_library (game_id, status)
        VALUES (?, 'played')
        ON CONFLICT(game_id) DO UPDATE SET status='played'
    """, (str(game["id"]),))


async def main():
    async with httpx.AsyncClient(timeout=15) as client:
        async with aiosqlite.connect(DB) as conn:
            for title in HISTORY:
                try:
                    result = await search_rawg(client, title)
                    if not result:
                        print(f"  NOT FOUND: {title}")
                        continue
                    await upsert_and_mark_played(conn, result)
                    print(f"  ✓ {title}  →  {result['name']} (id={result['id']})")
                except Exception as e:
                    print(f"  ERROR {title}: {e}")
                await asyncio.sleep(0.3)  # stay within RAWG rate limit
            await conn.commit()
    print("\nDone.")


asyncio.run(main())

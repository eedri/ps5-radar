"""
Run once to seed liked games from the user's anchor game list.
Usage: python seed_data.py
Requires RAWG_API_KEY in environment.
"""
import asyncio
import os
from dotenv import load_dotenv
from app.database import init_db, add_liked_game, get_all_games, get_liked_games, update_all_scores
from app.scraper import search_rawg_game, fetch_game_tags
from app.scorer import rescore_all

load_dotenv()

ANCHOR_GAMES = [
    "The Last of Us Part I",
    "Horizon Zero Dawn",
    "Days Gone",
    "Disco Elysium",
    "God of War",
    "Metal Gear Solid V The Phantom Pain",
    "Star Wars Outlaws",
    "Red Dead Redemption 2",
]


async def seed():
    db_path = os.environ.get("DATABASE_URL", "/data/radar.db")
    api_key = os.environ["RAWG_API_KEY"]
    await init_db(db_path)

    for title in ANCHOR_GAMES:
        print(f"Searching: {title}")
        results = await search_rawg_game(api_key, title)
        if not results:
            print(f"  Not found — skipping")
            continue
        r = results[0]
        tags = await fetch_game_tags(api_key, r["rawg_id"])
        liked = {"rawg_id": r["rawg_id"], "title": r["title"], "cover_url": r["cover_url"], "tags": tags}
        await add_liked_game(db_path, liked)
        print(f"  Added: {r['title']} | tags: {', '.join(tags[:5])}")

    # Re-score everything
    all_games = await get_all_games(db_path)
    liked_games = await get_liked_games(db_path)
    if all_games:
        scores = rescore_all(all_games, liked_games)
        await update_all_scores(db_path, scores)
        print(f"Re-scored {len(all_games)} games.")
    print("Seeding complete.")


if __name__ == "__main__":
    asyncio.run(seed())

"""
Migrates local DB data to the production Railway instance
using existing API endpoints — no special upload endpoint needed.

Steps:
  1. Push liked_games via POST /preferences/add
  2. Push user_library (played/wishlist) via POST /library/set
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

import httpx
import aiosqlite

LOCAL_DB = os.environ.get("DATABASE_URL", "radar.db")
PROD_URL = "https://ps5-radar-production.up.railway.app"
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "")


async def main():
    async with aiosqlite.connect(LOCAL_DB) as conn:
        conn.row_factory = aiosqlite.Row

        liked = await (await conn.execute("SELECT * FROM liked_games")).fetchall()
        library = await (await conn.execute("SELECT * FROM user_library")).fetchall()

    async with httpx.AsyncClient(timeout=60, follow_redirects=False) as client:

        # ── 1. Liked games ──────────────────────────────────────────────────
        print(f"\nPushing {len(liked)} liked games...")
        for row in liked:
            resp = await client.post(f"{PROD_URL}/preferences/add", json={
                "rawg_id": row["rawg_id"],
                "title": row["title"],
                "cover_url": row["cover_url"] or "",
            })
            status = "✓" if resp.status_code == 200 else f"✗ ({resp.status_code})"
            print(f"  {status} {row['title']}")
            await asyncio.sleep(0.5)  # RAWG rate limit (tags fetched server-side)

        # ── 2. Library (played / wishlist) ──────────────────────────────────
        print(f"\nPushing {len(library)} library entries...")
        for row in library:
            resp = await client.post(
                f"{PROD_URL}/library/set",
                data={"game_id": row["game_id"], "status": row["status"]},
            )
            # endpoint returns 303 redirect — that's success
            status = "✓" if resp.status_code in (200, 303) else f"✗ ({resp.status_code})"
            print(f"  {status} game_id={row['game_id']}  status={row['status']}")

    print("\nMigration complete.")
    print("Now trigger /admin/refresh on production to populate the games table.")


asyncio.run(main())

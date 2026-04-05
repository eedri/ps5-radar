import json
import aiosqlite
from datetime import date
from typing import Literal, Optional

async def init_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as conn:
        await conn.executescript("""
            CREATE TABLE IF NOT EXISTS games (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                cover_url TEXT,
                genres TEXT DEFAULT '[]',
                tags TEXT DEFAULT '[]',
                perspective TEXT DEFAULT 'unknown',
                rawg_rating REAL DEFAULT 0,
                metacritic INTEGER,
                psn_price_eur REAL,
                psn_url TEXT,
                ign_url TEXT,
                match_score INTEGER DEFAULT 0,
                first_seen DATE,
                last_updated DATE
            );

            CREATE TABLE IF NOT EXISTS user_library (
                game_id TEXT PRIMARY KEY,
                status TEXT NOT NULL CHECK(status IN ('played', 'wishlist')),
                added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS liked_games (
                rawg_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                cover_url TEXT,
                tags TEXT DEFAULT '[]',
                added_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS email_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                games_count INTEGER,
                top_game_id TEXT,
                status TEXT DEFAULT 'ok'
            );
        """)
        await conn.commit()


async def upsert_game(db_path: str, game: dict) -> None:
    today = date.today().isoformat()
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("""
            INSERT INTO games (id, title, cover_url, genres, tags, perspective,
                rawg_rating, metacritic, psn_price_eur, psn_url, ign_url,
                match_score, first_seen, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title,
                cover_url=excluded.cover_url,
                genres=excluded.genres,
                tags=excluded.tags,
                perspective=excluded.perspective,
                rawg_rating=excluded.rawg_rating,
                metacritic=excluded.metacritic,
                psn_price_eur=excluded.psn_price_eur,
                psn_url=excluded.psn_url,
                ign_url=excluded.ign_url,
                match_score=excluded.match_score,
                last_updated=excluded.last_updated
        """, (
            game["id"], game["title"], game.get("cover_url", ""),
            json.dumps(game.get("genres", [])), json.dumps(game.get("tags", [])),
            game.get("perspective", "unknown"), game.get("rawg_rating", 0),
            game.get("metacritic"), game.get("psn_price_eur"),
            game.get("psn_url", ""), game.get("ign_url", ""),
            game.get("match_score", 0), today, today,
        ))
        await conn.commit()


async def get_all_games(db_path: str, exclude_played: bool = False) -> list[dict]:
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        if exclude_played:
            cursor = await conn.execute("""
                SELECT g.* FROM games g
                WHERE g.id NOT IN (
                    SELECT game_id FROM user_library WHERE status = 'played'
                )
                ORDER BY match_score DESC
            """)
        else:
            cursor = await conn.execute("SELECT * FROM games ORDER BY match_score DESC")
        rows = await cursor.fetchall()
    return [_row_to_dict(row) for row in rows]


async def get_new_games(db_path: str, days: int = 7) -> list[dict]:
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute("""
            SELECT g.* FROM games g
            WHERE g.first_seen >= date('now', ?)
              AND g.id NOT IN (
                SELECT game_id FROM user_library WHERE status = 'played'
              )
            ORDER BY match_score DESC
        """, (f"-{days} days",))
        rows = await cursor.fetchall()
    return [_row_to_dict(row) for row in rows]


async def get_library(db_path: str) -> dict:
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute("""
            SELECT g.*, ul.status FROM games g
            JOIN user_library ul ON g.id = ul.game_id
            ORDER BY ul.added_at DESC
        """)
        rows = await cursor.fetchall()
    played = [_row_to_dict(r) for r in rows if r["status"] == "played"]
    wishlist = [_row_to_dict(r) for r in rows if r["status"] == "wishlist"]
    return {"played": played, "wishlist": wishlist}


async def set_user_status(db_path: str, game_id: str, status: Literal["played", "wishlist"]) -> None:
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("""
            INSERT INTO user_library (game_id, status)
            VALUES (?, ?)
            ON CONFLICT(game_id) DO UPDATE SET status=excluded.status, added_at=CURRENT_TIMESTAMP
        """, (game_id, status))
        await conn.commit()


async def remove_user_status(db_path: str, game_id: str) -> None:
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("DELETE FROM user_library WHERE game_id = ?", (game_id,))
        await conn.commit()


async def get_user_status(db_path: str, game_id: str) -> Optional[str]:
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            "SELECT status FROM user_library WHERE game_id = ?", (game_id,)
        )
        row = await cursor.fetchone()
    return row[0] if row else None


async def add_liked_game(db_path: str, game: dict) -> None:
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("""
            INSERT OR REPLACE INTO liked_games (rawg_id, title, cover_url, tags)
            VALUES (?, ?, ?, ?)
        """, (game["rawg_id"], game["title"], game.get("cover_url", ""),
              json.dumps(game.get("tags", []))))
        await conn.commit()


async def remove_liked_game(db_path: str, rawg_id: str) -> None:
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("DELETE FROM liked_games WHERE rawg_id = ?", (rawg_id,))
        await conn.commit()


async def get_liked_games(db_path: str) -> list[dict]:
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute("SELECT * FROM liked_games ORDER BY added_at DESC")
        rows = await cursor.fetchall()
    return [_row_to_dict(row) for row in rows]


async def update_all_scores(db_path: str, scores: dict[str, int]) -> None:
    """Update match_score for multiple games at once. scores = {game_id: score}"""
    async with aiosqlite.connect(db_path) as conn:
        await conn.executemany(
            "UPDATE games SET match_score = ? WHERE id = ?",
            [(score, gid) for gid, score in scores.items()]
        )
        await conn.commit()


async def log_email(db_path: str, games_count: int, top_game_id: str, status: str) -> None:
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            "INSERT INTO email_log (games_count, top_game_id, status) VALUES (?, ?, ?)",
            (games_count, top_game_id, status)
        )
        await conn.commit()


def _row_to_dict(row) -> dict:
    d = dict(row)
    for key in ("genres", "tags"):
        if key in d and isinstance(d[key], str):
            try:
                d[key] = json.loads(d[key])
            except (json.JSONDecodeError, TypeError):
                d[key] = []
    return d

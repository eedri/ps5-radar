import os
import logging
from datetime import date, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.database import (
    get_all_games, get_liked_games, upsert_game, update_all_scores,
    get_new_games, log_email,
)
from app.scraper import fetch_ps5_games, fetch_game_tags, get_psn_price
from app.scorer import rescore_all
from app.email_digest import send_digest

log = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def run_weekly_job(db_path: str) -> None:
    """Full pipeline: fetch → enrich → price → score → email."""
    log.info("Weekly job started")
    api_key = os.environ["RAWG_API_KEY"]

    # 1. Fetch new PS5 games from RAWG
    fetched = await fetch_ps5_games(api_key=api_key, page_size=40, pages=5)
    log.info(f"Fetched {len(fetched)} games from RAWG")

    # 2. Enrich with tags + PSN price, then upsert
    for game in fetched:
        game["tags"] = await fetch_game_tags(api_key, game["id"])
        game["psn_price_eur"] = await get_psn_price(game["psn_url"])
        await upsert_game(db_path, game)

    # 3. Re-score all games in DB
    all_games = await get_all_games(db_path)
    liked = await get_liked_games(db_path)
    scores = rescore_all(all_games, liked)
    await update_all_scores(db_path, scores)

    # 4. Build recommendation list (exclude played)
    recommended = await get_all_games(db_path, exclude_played=True)
    recommended = [g for g in recommended if g["match_score"] >= 20]
    recommended.sort(key=lambda g: g["match_score"], reverse=True)

    # 5. Determine new games (first seen in last 7 days)
    new_games = await get_new_games(db_path, days=7)
    new_ids = {g["id"] for g in new_games}

    # 6. Send email
    success = await send_digest(
        api_key=os.environ["RESEND_API_KEY"],
        from_email=os.environ["RESEND_FROM_EMAIL"],
        to_email=os.environ["ALERT_EMAIL"],
        games=recommended,
        new_game_ids=new_ids,
    )

    top_id = recommended[0]["id"] if recommended else ""
    status = "ok" if success else "failed"
    await log_email(db_path, len(recommended), top_id, status)
    log.info(f"Weekly job complete — email status: {status}")


def start_scheduler(db_path: str) -> None:
    scheduler.add_job(
        run_weekly_job,
        trigger=CronTrigger(day_of_week="sun", hour=9, minute=0),
        args=[db_path],
        id="weekly_radar",
        replace_existing=True,
    )
    scheduler.start()
    log.info("Scheduler started — weekly job every Sunday 09:00")

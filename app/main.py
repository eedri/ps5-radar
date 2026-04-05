import os
import logging
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.database import (
    init_db, get_all_games, get_new_games, get_library, get_game,
    set_user_status, remove_user_status, add_liked_game, remove_liked_game,
    get_liked_games, update_all_scores, get_user_status,
)
from app.scorer import build_tag_weights, rescore_all
from app.scraper import search_rawg_game, fetch_game_tags, fetch_game_detail
from app.scheduler import start_scheduler, run_weekly_job

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

def create_app(db_path: str | None = None) -> FastAPI:
    db = db_path or os.environ.get("DATABASE_URL", "/data/radar.db")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await init_db(db)
        if db_path is None:  # only start scheduler in production
            start_scheduler(db)
        yield

    app = FastAPI(lifespan=lifespan)

    static_dir = os.path.join(os.path.dirname(BASE_DIR), "static")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # ── Pages ──────────────────────────────────────────────────────────────

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        games = await get_all_games(db, exclude_played=True)
        games = [g for g in games if g["match_score"] >= 20]
        return templates.TemplateResponse(request, "index.html", {
            "games": games,
            "selected_genre": "All",
            "admin_secret": os.environ.get("ADMIN_SECRET", ""),
        })

    @app.get("/new", response_class=HTMLResponse)
    async def new_games(request: Request):
        games = await get_new_games(db, days=7)
        return templates.TemplateResponse(request, "new.html", {"games": games})

    @app.get("/library", response_class=HTMLResponse)
    async def library(request: Request):
        data = await get_library(db)
        return templates.TemplateResponse(request, "library.html", {
            "played": data["played"],
            "wishlist": data["wishlist"],
        })

    @app.get("/preferences", response_class=HTMLResponse)
    async def preferences(request: Request):
        liked = await get_liked_games(db)
        weights = build_tag_weights(liked) if liked else {}
        return templates.TemplateResponse(request, "preferences.html", {
            "liked_games": liked,
            "tag_weights": weights,
        })

    @app.get("/game/{game_id}", response_class=HTMLResponse)
    async def game_detail(request: Request, game_id: str):
        from fastapi import HTTPException
        game = await get_game(db, game_id)
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")
        api_key = os.environ.get("RAWG_API_KEY", "")
        detail = await fetch_game_detail(api_key, game_id)
        user_status = await get_user_status(db, game_id)
        return templates.TemplateResponse(request, "game.html", {
            "game": game,
            "detail": detail,
            "user_status": user_status,
        })

    # ── Library actions ────────────────────────────────────────────────────

    @app.post("/library/set")
    async def set_status(game_id: str = Form(...), status: str = Form(...)):
        if status not in ("played", "wishlist"):
            from fastapi import HTTPException
            raise HTTPException(status_code=422, detail="status must be 'played' or 'wishlist'")
        await set_user_status(db, game_id, status)
        return RedirectResponse("/", status_code=303)

    @app.post("/library/remove")
    async def remove_status(game_id: str = Form(...)):
        await remove_user_status(db, game_id)
        return RedirectResponse("/library", status_code=303)

    # ── Preferences actions ────────────────────────────────────────────────

    @app.get("/preferences/search")
    async def search_games(q: str):
        api_key = os.environ.get("RAWG_API_KEY", "")
        results = await search_rawg_game(api_key, q)
        return JSONResponse(results)

    class AddGameRequest(BaseModel):
        rawg_id: str
        title: str
        cover_url: str = ""

    @app.post("/preferences/add")
    async def add_liked(body: AddGameRequest):
        api_key = os.environ.get("RAWG_API_KEY", "")
        tags = await fetch_game_tags(api_key, body.rawg_id)
        liked = {
            "rawg_id": body.rawg_id,
            "title": body.title,
            "cover_url": body.cover_url,
            "tags": tags,
        }
        await add_liked_game(db, liked)
        # Re-score all games
        all_games = await get_all_games(db)
        liked_games = await get_liked_games(db)
        scores = rescore_all(all_games, liked_games)
        await update_all_scores(db, scores)
        return JSONResponse({"ok": True})

    @app.post("/preferences/remove")
    async def remove_liked(rawg_id: str = Form(...)):
        await remove_liked_game(db, rawg_id)
        all_games = await get_all_games(db)
        liked_games = await get_liked_games(db)
        scores = rescore_all(all_games, liked_games)
        await update_all_scores(db, scores)
        return RedirectResponse("/preferences", status_code=303)

    # ── Admin ──────────────────────────────────────────────────────────────

    @app.post("/admin/refresh")
    async def manual_refresh(request: Request):
        secret = os.environ.get("ADMIN_SECRET", "")
        if secret and request.headers.get("X-Admin-Secret") != secret:
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="Forbidden")
        await run_weekly_job(db)
        return JSONResponse({"ok": True, "message": "Refresh complete"})

    return app


app = create_app()

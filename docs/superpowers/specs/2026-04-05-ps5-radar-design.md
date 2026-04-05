# PS5 Radar — Design Spec
**Date:** 2026-04-05  
**Status:** Approved

---

## Overview

A personal PS5 game recommendation dashboard — a web app + weekly email digest — that scores new PS5 games against the user's taste profile and surfaces the best matches. Games the user has already played are excluded from recommendations. The user can manage their preference profile by adding liked games, which auto-tunes the scoring engine.

---

## Architecture

**Pattern:** Single-service monolith  
**Language:** Python 3.12  
**Framework:** FastAPI + Jinja2 (server-side rendered HTML)  
**Scheduler:** APScheduler (runs inside the FastAPI process)  
**Storage:** SQLite on a Railway persistent volume  
**Email:** Resend API  
**Deployment:** Railway (GitHub push-to-deploy), public `*.up.railway.app` URL  

```
┌─────────────────────────────────────────────────────┐
│                  Railway Service                    │
│                                                     │
│  FastAPI app                                        │
│  ├── Web UI (Jinja2, mobile-responsive)             │
│  ├── REST endpoints (mark played, preferences)      │
│  └── APScheduler                                    │
│       └── Weekly job (Sunday 09:00)                 │
│            ├── RAWG API → fetch new PS5 games       │
│            ├── PSN Store scraper → prices           │
│            ├── Scoring engine → match scores        │
│            └── Resend → email digest                │
│                                                     │
│  SQLite (persistent volume)                         │
│  ├── games                                          │
│  ├── user_library                                   │
│  ├── liked_games                                    │
│  └── email_log                                      │
└─────────────────────────────────────────────────────┘
```

---

## Data Sources

| Source | Purpose | Method |
|--------|---------|--------|
| RAWG.io API (free) | Game metadata: title, cover art, genres, tags, RAWG rating, Metacritic score, release date | HTTP API (key required) |
| PSN Store | Current EUR price per game | BeautifulSoup scraper |
| IGN / GameSpot | Review URLs | Constructed from game slug (no scraping) |

---

## Database Schema

### `games`
| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | RAWG game ID |
| title | TEXT | |
| cover_url | TEXT | |
| genres | TEXT | JSON array of genre strings |
| tags | TEXT | JSON array of RAWG tag slugs |
| perspective | TEXT | `third-person`, `first-person`, `top-down`, `unknown` |
| rawg_rating | REAL | 0–5 |
| metacritic | INTEGER | 0–100, nullable |
| psn_price_eur | REAL | nullable |
| psn_url | TEXT | |
| ign_url | TEXT | Constructed from slug |
| match_score | INTEGER | 0–100, computed |
| first_seen | DATE | |
| last_updated | DATE | |

### `user_library`
| Column | Type | Notes |
|--------|------|-------|
| game_id | TEXT FK | → games.id |
| status | TEXT | `played` or `wishlist` |
| added_at | DATETIME | |
| notes | TEXT | optional |

### `liked_games`
| Column | Type | Notes |
|--------|------|-------|
| rawg_id | TEXT PK | RAWG game ID (no FK — liked games may not be in `games` table) |
| title | TEXT | |
| cover_url | TEXT | |
| tags | TEXT | JSON array of RAWG tag slugs, fetched at add time |
| added_at | DATETIME | |

Games in `liked_games` are used to derive the user's preference tag weights. Adding or removing a liked game triggers a full re-score. Stored independently of `games` because pre-seeded anchor games (older PS4 titles) may never appear in the PS5-filtered RAWG fetch.

### `email_log`
| Column | Type | Notes |
|--------|------|-------|
| sent_at | DATETIME | |
| games_count | INTEGER | |
| top_game_id | TEXT | |
| status | TEXT | `ok` or `failed` |

---

## Scoring Engine

Match score is computed per game on a 0–100 scale.

### Algorithm

```
score = clamp(base_score + genre_boosts - penalties, 0, 100)
```

**Base score (max 40 pts)**
- RAWG rating: `(rating / 5.0) * 20` → 0–20 pts (linear, e.g. 4.0 → 16 pts, 5.0 → 20 pts)
- Metacritic: `(score / 100.0) * 20` → 0–20 pts (linear, e.g. 80 → 16 pts, 100 → 20 pts)
- If Metacritic is null, use 0 for that component

**Genre / tag boosts (max +40 pts)**
- `third-person` → +15
- `action-adventure` → +10
- `open-world` → +8
- `story-rich` / `narrative` → +7
- `stealth` → +5
- `rpg` / `character-progression` → +5

**Penalties (max −40 pts)**
- `first-person` → −20
- `soulslike` / `roguelike` → −15
- `racing` → −15
- `simulation` → −10
- `sports` → −10

**Dynamic boost from liked games**  
When the user adds liked games, the engine analyzes their RAWG tags, counts frequency across all liked games, and derives a weighted tag map. For each tag, `dynamic_boost = (tag_count / total_liked_games) * 20` (capped at 20 pts per tag). These dynamic values **replace** the static boost values for matching tags; tags not covered by liked games fall back to the static defaults above.

**Exclusion rules (game never shown)**
- `user_library.status = 'played'` for this game
- Final score < 20

Games are sorted descending by match score.

---

## Web UI

**Tech:** FastAPI + Jinja2 templates + plain CSS (no JS framework)  
**Responsive:** Mobile-first, single-column on mobile, 3-column grid on desktop  
**Theme:** Dark

### Pages

| Route | Description |
|-------|-------------|
| `GET /` | Main radar — all recommended games, sorted by match score |
| `GET /new` | Games first seen in the last 7 days |
| `GET /library` | User's played games and wishlist |
| `GET /preferences` | Manage liked games, view derived tag weights |

### Game Card (shows on `/` and `/new`)
- Cover art
- Title
- Match score badge (color: green ≥80, indigo ≥60, gray <60)
- Genre tags
- RAWG star rating + Metacritic score
- PSN price (EUR)
- Links: IGN Review, PSN Store
- Buttons: "Mark as Played", "Add to Wishlist"

### Filter Bar
Chips for: All, Action, Open World, Narrative, Stealth, RPG  
Sort: Match Score (default), Rating, Price

---

## Weekly Job (APScheduler)

Runs every Sunday at 09:00 server time.

**Steps:**
1. Fetch PS5 games from RAWG API (paginated, sorted by release date, up to 200 games per run)
2. For each game not already in DB (or not updated in last 7 days): save/update in `games`
3. Scrape PSN Store for current price for each game
4. Re-score all games using current liked_games weights
5. Compose HTML email digest: top 20 games by match score, highlighting any new this week
6. Send via Resend API
7. Write to `email_log`

The job can also be triggered manually via `POST /admin/refresh` (no auth required — private Railway deployment).

---

## Email Digest

**Provider:** Resend (free tier: 3,000/month, 100/day)  
**Sender:** configured via `RESEND_FROM_EMAIL` env var  
**Recipient:** `ALERT_EMAIL` env var  
**Schedule:** Weekly, Sunday 09:00  
**Format:** Rich HTML email

**Email content:**
- Header: date, total games scored, count new this week, top match score
- "New this week" banner listing new game titles
- Top 20 game rows: cover art, title, match score (+ NEW badge if first seen this week), genres, RAWG rating, Metacritic, PSN price, links to IGN + PSN Store + dashboard
- CTA button: "Open PS5 Radar Dashboard"
- Footer: link to preferences page, unsubscribe note

---

## Preferences Page

- Search box: user types a game name → autocomplete via RAWG search API
- Selecting a game adds it to `liked_games`, triggers re-score
- Liked games list shows title, cover, tags; each has a remove button
- Tag weight visualization: shows derived boost values for top tags

Pre-seeded with user's existing anchor games:
- The Last of Us, Horizon Zero Dawn, Days Gone, Disco Elysium, God of War, Metal Gear Solid, Star Wars Outlaws, Red Dead Redemption 2

---

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `RAWG_API_KEY` | RAWG.io free API key |
| `RESEND_API_KEY` | Resend email API key |
| `RESEND_FROM_EMAIL` | Sender address (e.g. `radar@yourdomain.com`) |
| `ALERT_EMAIL` | Recipient for weekly digest |
| `DATABASE_URL` | Path to SQLite file (default: `/data/radar.db`) |
| `TZ` | Timezone for scheduler (e.g. `Europe/Jerusalem`) |

---

## Project Structure

```
ps5-radar/
├── app/
│   ├── main.py              # FastAPI app, routes
│   ├── scheduler.py         # APScheduler setup, weekly job
│   ├── scraper.py           # RAWG API client + PSN price scraper
│   ├── scorer.py            # Match scoring engine
│   ├── email_digest.py      # Resend email composer + sender
│   ├── database.py          # SQLite init, query helpers
│   └── templates/
│       ├── base.html
│       ├── index.html
│       ├── new.html
│       ├── library.html
│       └── preferences.html
├── static/
│   └── style.css
├── docs/
│   └── superpowers/specs/
│       └── 2026-04-05-ps5-radar-design.md
├── Dockerfile
├── railway.toml
├── requirements.txt
└── .gitignore
```

---

## Deployment Steps (Railway)

1. Push repo to GitHub
2. Create new Railway project → "Deploy from GitHub repo"
3. Add a persistent volume mounted at `/data`
4. Set environment variables in Railway dashboard
5. Railway auto-builds from `Dockerfile` on every push to `main`
6. Access app at the generated `*.up.railway.app` URL

---

## Out of Scope

- User authentication (single-user personal tool)
- Multiple user profiles
- Game trailers / video embeds
- Notifications beyond email (push, SMS)
- Price history tracking

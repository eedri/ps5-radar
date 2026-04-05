import resend
from datetime import date
from typing import Optional

def build_email_html(games: list[dict], new_game_ids: set[str]) -> str:
    today = date.today().strftime("%-d %b %Y")
    new_titles = [g["title"] for g in games if g["id"] in new_game_ids]
    new_banner = ""
    if new_titles:
        joined = " · ".join(new_titles[:5])
        new_banner = f"""
        <div style="background:#1e3a2e;border-left:3px solid #10b981;padding:0.75rem 1.25rem;font-size:0.85rem;color:#34d399;margin-bottom:1rem">
            🆕 New this week: <strong>{joined}</strong>
        </div>"""

    cards_html = ""
    for g in games[:20]:
        badge_color = "#10b981" if g["match_score"] >= 80 else "#6366f1" if g["match_score"] >= 60 else "#64748b"
        new_flag = " 🆕" if g["id"] in new_game_ids else ""
        metacritic_str = f"Metacritic: {g['metacritic']}" if g.get("metacritic") else ""
        price_str = f"€{g['psn_price_eur']:.2f}" if g.get("psn_price_eur") else "Price N/A"
        genres_str = ", ".join(g.get("genres", [])[:3]).title()
        cover = g.get("cover_url", "")
        cover_html = f'<img src="{cover}" width="80" height="80" style="object-fit:cover;border-radius:4px">' if cover else '<div style="width:80px;height:80px;background:#1e293b;border-radius:4px"></div>'

        cards_html += f"""
        <div style="background:#1e293b;border-radius:10px;display:flex;gap:1rem;overflow:hidden;margin-bottom:0.75rem;padding:0.75rem">
            {cover_html}
            <div style="flex:1">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:0.3rem">
                    <span style="font-weight:700;font-size:1rem;color:#e2e8f0">{g['title']}</span>
                    <span style="background:{badge_color};color:white;font-size:0.7rem;padding:0.15rem 0.5rem;border-radius:99px;white-space:nowrap">{g['match_score']} match{new_flag}</span>
                </div>
                <div style="font-size:0.75rem;color:#64748b;margin-bottom:0.4rem">{genres_str}</div>
                <div style="font-size:0.75rem;color:#94a3b8;margin-bottom:0.5rem">⭐ {g.get('rawg_rating', 0):.1f} RAWG &nbsp; {metacritic_str} &nbsp; <span style="color:#34d399;font-weight:700">{price_str}</span></div>
                <div style="display:flex;gap:0.5rem;flex-wrap:wrap">
                    <a href="{g.get('ign_url','')}" style="background:#6366f1;color:white;font-size:0.7rem;padding:0.2rem 0.6rem;border-radius:4px;text-decoration:none">IGN Review →</a>
                    <a href="{g.get('psn_url','')}" style="background:#334155;color:#94a3b8;font-size:0.7rem;padding:0.2rem 0.6rem;border-radius:4px;text-decoration:none">PSN Store →</a>
                </div>
            </div>
        </div>"""

    top_score = games[0]["match_score"] if games else 0
    total = len(games)
    new_count = len(new_game_ids)

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#0f172a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
<div style="max-width:640px;margin:0 auto;padding:1rem">
    <div style="background:linear-gradient(135deg,#1a1a3e,#2d1b69);padding:2rem;border-radius:12px;text-align:center;margin-bottom:1rem">
        <div style="font-size:1.8rem;font-weight:800;color:#e2e8f0">🎮 PS5 Radar</div>
        <div style="font-size:0.85rem;color:#94a3b8;margin-top:0.3rem">Weekly Digest — {today}</div>
        <div style="display:flex;justify-content:center;gap:2rem;margin-top:1rem;font-size:0.8rem">
            <span style="color:#10b981">✅ {total} games scored</span>
            <span style="color:#6366f1">🆕 {new_count} new</span>
            <span style="color:#f59e0b">🔥 Top: {top_score}</span>
        </div>
    </div>
    {new_banner}
    {cards_html}
    <a href="#" style="display:block;background:#6366f1;color:white;text-align:center;padding:1rem;border-radius:10px;text-decoration:none;font-weight:600;font-size:0.95rem;margin-top:1rem">Open PS5 Radar Dashboard →</a>
    <div style="text-align:center;font-size:0.7rem;color:#334155;margin-top:1rem;padding-top:1rem;border-top:1px solid #1e293b">
        Sent weekly every Sunday
    </div>
</div>
</body></html>"""


async def send_digest(
    api_key: str,
    from_email: str,
    to_email: str,
    games: list[dict],
    new_game_ids: set[str],
) -> bool:
    """Send weekly digest email. Returns True on success."""
    resend.api_key = api_key
    html = build_email_html(games, new_game_ids)
    today = date.today().strftime("%-d %b %Y")
    try:
        resend.Emails.send({
            "from": from_email,
            "to": [to_email],
            "subject": f"🎮 PS5 Radar — Weekly Digest {today}",
            "html": html,
        })
        return True
    except Exception:
        return False

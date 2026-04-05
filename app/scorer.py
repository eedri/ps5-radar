from collections import Counter

# Static base weights — replaced per-tag by dynamic weights when liked games exist
STATIC_BOOSTS: dict[str, float] = {
    "third-person": 15.0,
    "action-adventure": 10.0,
    "open-world": 8.0,
    "story-rich": 7.0,
    "narrative": 7.0,
    "stealth": 5.0,
    "rpg": 5.0,
    "character-customization": 3.0,
    "atmospheric": 3.0,
    "cinematic": 3.0,
}

PENALTIES: dict[str, float] = {
    "first-person": 20.0,
    "soulslike": 15.0,
    "roguelike": 15.0,
    "roguelite": 15.0,
    "racing": 15.0,
    "simulation": 10.0,
    "sports": 10.0,
    "massively-multiplayer": 5.0,
}


def build_tag_weights(liked_games: list[dict]) -> dict[str, float]:
    """
    Derive boost weights from liked games' tags.
    For each tag: dynamic_boost = (count / total_liked) * 20, capped at 20.
    Tags not covered by liked games fall back to STATIC_BOOSTS.
    """
    if not liked_games:
        return dict(STATIC_BOOSTS)

    all_tags: list[str] = []
    for game in liked_games:
        all_tags.extend(game.get("tags", []))

    counts = Counter(all_tags)
    total = len(liked_games)
    dynamic: dict[str, float] = {}
    for tag, count in counts.items():
        dynamic[tag] = min((count / total) * 20.0, 20.0)

    # Merge: dynamic overrides static for matching tags; static fills the rest
    merged = dict(STATIC_BOOSTS)
    merged.update(dynamic)
    return merged


def compute_score(game: dict, tag_weights: dict[str, float]) -> int:
    """Compute 0-100 match score for a single game."""
    rawg = game.get("rawg_rating") or 0.0
    meta = game.get("metacritic")

    base = (rawg / 5.0) * 20.0
    base += ((meta / 100.0) * 20.0) if meta is not None else 0.0

    tags = set(game.get("tags", []))
    genres = set(game.get("genres", []))
    all_labels = tags | genres

    boost = sum(tag_weights.get(label, 0.0) for label in all_labels)
    penalty = sum(PENALTIES.get(label, 0.0) for label in all_labels)

    raw = base + boost - penalty
    return max(0, min(100, round(raw)))


def rescore_all(games: list[dict], liked_games: list[dict]) -> dict[str, int]:
    """Return {game_id: score} for all games given current liked games."""
    weights = build_tag_weights(liked_games)
    return {game["id"]: compute_score(game, weights) for game in games}

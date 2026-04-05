import pytest
from app.scorer import compute_score, build_tag_weights, rescore_all

STATIC_WEIGHTS = build_tag_weights([])  # no liked games → pure static

def test_third_person_action_adventure_scores_high():
    game = {
        "rawg_rating": 4.5, "metacritic": 88,
        "tags": ["third-person", "action-adventure", "open-world", "story-rich"],
        "genres": ["action", "adventure"],
    }
    score = compute_score(game, STATIC_WEIGHTS)
    assert score >= 75

def test_first_person_penalized():
    game = {
        "rawg_rating": 4.8, "metacritic": 95,
        "tags": ["first-person", "shooter"],
        "genres": ["shooter"],
    }
    score = compute_score(game, STATIC_WEIGHTS)
    assert score < 50

def test_soulslike_penalized():
    game = {
        "rawg_rating": 4.9, "metacritic": 96,
        "tags": ["soulslike", "third-person"],
        "genres": ["rpg"],
    }
    score = compute_score(game, STATIC_WEIGHTS)
    assert score < 60

def test_score_clamped_0_to_100():
    game = {
        "rawg_rating": 5.0, "metacritic": 100,
        "tags": ["third-person", "action-adventure", "open-world", "story-rich", "stealth", "rpg"],
        "genres": [],
    }
    score = compute_score(game, STATIC_WEIGHTS)
    assert 0 <= score <= 100

def test_score_floored_at_0():
    game = {
        "rawg_rating": 0.5, "metacritic": 20,
        "tags": ["first-person", "soulslike", "racing", "simulation"],
        "genres": [],
    }
    score = compute_score(game, STATIC_WEIGHTS)
    assert score == 0

def test_dynamic_weights_from_liked_games():
    liked = [
        {"tags": ["third-person", "narrative", "stealth"]},
        {"tags": ["third-person", "narrative", "open-world"]},
        {"tags": ["third-person", "action-adventure"]},
    ]
    weights = build_tag_weights(liked)
    # third-person appears in all 3 → should have high boost
    assert weights.get("third-person", 0) >= weights.get("stealth", 0)

def test_null_metacritic_handled():
    game = {
        "rawg_rating": 4.0, "metacritic": None,
        "tags": ["third-person"], "genres": [],
    }
    score = compute_score(game, STATIC_WEIGHTS)
    assert score >= 0

def test_rescore_all_returns_dict():
    games = [
        {"id": "g1", "rawg_rating": 4.5, "metacritic": 85, "tags": ["third-person"], "genres": []},
        {"id": "g2", "rawg_rating": 3.0, "metacritic": 60, "tags": ["first-person"], "genres": []},
    ]
    scores = rescore_all(games, [])
    assert "g1" in scores
    assert "g2" in scores
    assert scores["g1"] > scores["g2"]

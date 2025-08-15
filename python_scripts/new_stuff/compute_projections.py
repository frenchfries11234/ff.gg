#!/usr/bin/env python3
import os
from datetime import datetime, timezone
from pymongo import MongoClient

# --- CONFIG ---
MONGO_URI       = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME         = "fantasy_football"
COLLECTION_NAME = "players"

SCORING_PROFILES = {
    "espn_ppr": {
        "player_pass_yds": 0.04, "player_pass_tds": 4.0,
        "player_rush_yds": 0.10, "player_rush_tds": 6.0,
        "player_receptions": 1.0, "player_reception_yds": 0.10, "player_reception_tds": 6.0,
    },
    "espn_half": {
        "player_pass_yds": 0.04, "player_pass_tds": 4.0,
        "player_rush_yds": 0.10, "player_rush_tds": 6.0,
        "player_receptions": 0.5, "player_reception_yds": 0.10, "player_reception_tds": 6.0,
    },
    "espn_std": {
        "player_pass_yds": 0.04, "player_pass_tds": 4.0,
        "player_rush_yds": 0.10, "player_rush_tds": 6.0,
        "player_receptions": 0.0, "player_reception_yds": 0.10, "player_reception_tds": 6.0,
    },
}

def to_float(x):
    try: return float(x)
    except Exception: return 0.0

def compute_points(projections: dict, weights: dict) -> float:
    total = 0.0
    for key, w in weights.items():
        total += to_float(projections.get(key, 0.0)) * w
    return round(total, 2)

def build_fantasy_from_projections(projections: dict) -> dict:
    return {k: compute_points(projections, w) for k, w in SCORING_PROFILES.items()}

def backfill():
    client = MongoClient(MONGO_URI)
    coll   = client[DB_NAME][COLLECTION_NAME]

    # --- quick diagnostics ---
    total_docs = coll.count_documents({})
    distinct_positions = coll.distinct("position")
    print(f"Total docs: {total_docs}")
    print(f"Distinct 'position' values: {distinct_positions}")

    # Case-insensitive filter for QB/RB/WR/TE
    pos_filter = {"position": {"$regex": "^(QB|RB|WR|TE)$", "$options": "i"}}
    filtered_count = coll.count_documents(pos_filter)
    if filtered_count == 0:
        print("No docs matched the position filter. Falling back to scanning all players.")
        pos_filter = {}  # fallback

    cursor = coll.find(pos_filter, {"_id": 1, "name": 1, "espn_id": 1, "games": 1})
    scanned_players = 0
    updated_games   = 0

    for doc in cursor:
        _id   = doc["_id"]
        games = doc.get("games", [])
        if not games:
            scanned_players += 1
            continue

        to_set = {}
        for i, g in enumerate(games):
            if not isinstance(g, dict):
                continue
            projections = g.get("projections")
            if not projections:
                continue

            fantasy = g.get("fantasy", {}) or {}
            # if already has all three, skip
            already = all(k in fantasy for k in SCORING_PROFILES.keys())
            if already:
                continue

            new_vals = build_fantasy_from_projections(projections)
            fantasy.update(new_vals)
            to_set[f"games.{i}.fantasy"] = fantasy
            to_set[f"games.{i}.fantasy_updated_at"] = datetime.now(timezone.utc).isoformat()
            updated_games += 1

        if to_set:
            coll.update_one({"_id": _id}, {"$set": to_set})

        scanned_players += 1

    print(f"Players scanned: {scanned_players}")
    print(f"Games updated with fantasy totals: {updated_games}")

if __name__ == "__main__":
    backfill()

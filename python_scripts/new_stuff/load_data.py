#!/usr/bin/env python3
import os
import json
from collections import defaultdict
from pymongo import MongoClient

# ——— CONFIG ———
MONGO_URI       = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME         = "fantasy_football"
COLLECTION_NAME = "players"
DATA_DIR        = "data/nfl"   # folder containing individual game JSON files

# Which positions are valid for each prop key
POSITIONS_BY_PROP = {
    "player_pass_yds":      ["QB"],
    "player_pass_tds":      ["QB"],
    "player_rush_yds":      ["QB", "RB"],
    "player_rush_tds":      ["QB", "RB"],
    "player_receptions":    ["RB", "WR", "TE"],
    "player_reception_yds": ["RB", "WR", "TE"],
    "player_reception_tds": ["RB", "WR", "TE"],
}

TEAM_NORMALIZE = {"WAS": "WSH", "JAC": "JAX"}
def norm_team(t):
    if not t: return t
    return TEAM_NORMALIZE.get(str(t).upper(), str(t).upper())

def compute_ev(line: float, odds_over: float, odds_under: float) -> float:
    p_over  = 1.0 / float(odds_over)
    p_under = 1.0 / float(odds_under)
    total   = p_over + p_under
    p_over /= total
    p_under/= total
    return round(p_over * (line + 0.5) + p_under * (line - 0.5), 2)

def update_players_with_games_from_dir(data_dir: str):
    client       = MongoClient(MONGO_URI)
    players_coll = client[DB_NAME][COLLECTION_NAME]

    # Build name index: name_lower → list of {espn_id, team, position}
    name_index = defaultdict(list)
    for doc in players_coll.find(
        {"position": {"$in": ["QB", "RB", "WR", "TE"]}},
        {"espn_id": 1, "name": 1, "team": 1, "position": 1}
    ):
        name_index[doc["name"].lower()].append({
            "espn_id": doc["espn_id"],
            "team":    norm_team(doc.get("team")),
            "position":doc.get("position"),
        })

    def resolve_for_prop(player_name: str, prop_key: str, home_abbr: str, away_abbr: str):
        """
        Resolve a single espn_id for THIS prop only, using:
        - exact name match (case-insensitive)
        - team in {home, away}
        - position ∈ POSITIONS_BY_PROP[prop_key]
        Returns espn_id or None if ambiguous/unknown.
        """
        cands = name_index.get(player_name.lower(), [])
        if not cands:
            return None
        teams = {norm_team(home_abbr), norm_team(away_abbr)}
        allowed_pos = set(POSITIONS_BY_PROP.get(prop_key, []))
        filtered = [c for c in cands if c["team"] in teams and c["position"] in allowed_pos]
        if len(filtered) == 1:
            return filtered[0]["espn_id"]
        # If still ambiguous, skip (don’t attach to multiple)
        if len(filtered) > 1:
            print(f"⚠️ Ambiguous '{player_name}' for {prop_key} in {teams}: {filtered}")
        return None

    # Walk each game file
    for fname in os.listdir(data_dir):
        if not fname.lower().endswith(".json"):
            continue
        path = os.path.join(data_dir, fname)
        with open(path, "r") as f:
            game = json.load(f)

        base_info = {
            "game_id":       game["id"],
            "commence_time": game["commence_time"],
            "home_team":     norm_team(game["home_team"]),
            "away_team":     norm_team(game["away_team"]),
        }

        # Collect projections keyed by resolved espn_id
        ev_by_player_id = defaultdict(dict)

        # Use only DraftKings (or drop this if you want all books)
        dk = next((b for b in game.get("bookmakers", []) if b.get("key") == "draftkings"), None)
        if not dk:
            continue

        for market in dk.get("markets", []):
            prop_key = market.get("key")
            if not prop_key:
                continue

            # Build over/under per *name* for this prop
            sides = defaultdict(lambda: {"over": None, "under": None, "line": None})
            for outcome in market.get("outcomes", []):
                side = str(outcome.get("name", "")).lower()   # "over"/"under"
                name = outcome.get("description")
                if not name:
                    continue
                sides[name]["line"]  = outcome.get("point")
                sides[name][side]    = outcome.get("price")

            # For each name with both sides, resolve to espn_id for THIS prop
            for name, sd in sides.items():
                if sd["over"] and sd["under"] and sd["line"] is not None:
                    espn_id = resolve_for_prop(
                        name, prop_key, base_info["home_team"], base_info["away_team"]
                    )
                    if not espn_id:
                        continue
                    ev = compute_ev(sd["line"], sd["over"], sd["under"])
                    ev_by_player_id[espn_id][prop_key] = ev

        # Upsert one record per resolved espn_id
        for espn_id, props in ev_by_player_id.items():
            record = {**base_info, "projections": props}
            gid = record["game_id"]

            res = players_coll.update_one(
                {"espn_id": espn_id, "games.game_id": gid},
                {"$set": {
                    "games.$.projections":     props,
                    "games.$.commence_time":   record["commence_time"],
                    "games.$.home_team":       record["home_team"],
                    "games.$.away_team":       record["away_team"],
                }}
            )
            if res.matched_count:
                print(f"✓ Updated espn_id={espn_id} for game {gid}")
            else:
                players_coll.update_one(
                    {"espn_id": espn_id},
                    {"$push": {"games": record}}
                )
                print(f"+ Inserted espn_id={espn_id} for game {gid}")

if __name__ == "__main__":
    update_players_with_games_from_dir(DATA_DIR)
    print("Done updating player documents from directory.")

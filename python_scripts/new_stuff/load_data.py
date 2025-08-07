#!/usr/bin/env python3
import os
import json
from datetime import datetime, timezone
from collections import defaultdict
from pymongo import MongoClient

# ——— CONFIG ———
MONGO_URI       = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME         = "fantasy_football"
COLLECTION_NAME = "players"
DATA_DIR        = "data/nfl"   # folder containing individual game JSON files

def compute_ev(line: float, odds_over: float, odds_under: float) -> float:
    """
    Compute expected value (projected stat) for a prop given decimal odds.
    EV = line + (p_over - p_under) * 0.5
    """
    p_over  = 1 / odds_over
    p_under = 1 / odds_under
    total   = p_over + p_under
    p_over  /= total
    p_under /= total
    return p_over * (line + 0.5) + p_under * (line - 0.5)

def update_players_with_games_from_dir(data_dir: str):
    client       = MongoClient(MONGO_URI)
    players_coll = client[DB_NAME][COLLECTION_NAME]

    # build a mapping from name → espn_id
    name_to_espn_id = {
        doc['name']: doc['espn_id']
        for doc in players_coll.find({}, {'name':1, 'espn_id':1})
    }

    for fname in os.listdir(data_dir):
        if not fname.lower().endswith(".json"):
            continue
        path = os.path.join(data_dir, fname)
        with open(path, "r") as f:
            game = json.load(f)

        # extract basic game info
        base_info = {
            "game_id":       game["id"],
            "commence_time": game["commence_time"],
            "home_team":     game["home_team"],
            "away_team":     game["away_team"]
        }

        # compile EV projections per player name
        player_props = defaultdict(dict)
        for bm in game.get("bookmakers", []):
            if bm.get("key") != "draftkings":
                continue
            for market in bm.get("markets", []):
                prop_key = market.get("key")
                sides = defaultdict(lambda: {"over": None, "under": None})
                for outcome in market.get("outcomes", []):
                    side = outcome["name"].lower()  # over or under
                    name = outcome["description"]
                    sides[name][side] = {
                        "line":  outcome["point"],
                        "price": outcome["price"]
                    }
                # compute EV if both sides exist
                for player_name, s in sides.items():
                    over = s["over"]
                    under = s["under"]
                    if over and under:
                        ev = compute_ev(over["line"], over["price"], under["price"])
                        player_props[player_name][prop_key] = round(ev, 2)

        # upsert each player's game record by espn_id
        for player_name, props in player_props.items():
            espn_id = name_to_espn_id.get(player_name)
            if not espn_id:
                continue

            record = {**base_info, "projections": props}
            game_id = record["game_id"]

            # 1) Try to update an existing game entry
            res = players_coll.update_one(
                {"espn_id": espn_id, "games.game_id": game_id},
                {"$set": {
                    "games.$.projections": props,
                    "games.$.commence_time": record["commence_time"],
                    "games.$.home_team": record["home_team"],
                    "games.$.away_team": record["away_team"],
                }}
            )

            if res.matched_count:
                print(f"Updated projections for {player_name} in game {game_id}")
            else:
                # 2) If no such game yet, push it
                players_coll.update_one(
                    {"espn_id": espn_id},
                    {"$push": {"games": record}}
                )
                print(f"Inserted new game for {player_name} → {game_id}")

if __name__ == "__main__":
    update_players_with_games_from_dir(DATA_DIR)
    print("Done updating player documents from directory.")

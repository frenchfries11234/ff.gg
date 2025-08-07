#!/usr/bin/env python3
import os
import random
import uuid
import json
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient

# ——— CONFIG ———
MONGO_URI         = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME           = "fantasy_football"
COLLECTION_NAME   = "players"
OUTPUT_DIR        = "data/nfl"   # ensure this exists

# Map each prop to the positions it applies to
positions_by_prop = {
    "player_pass_yds":     ["QB"],
    "player_pass_tds":     ["QB"],
    "player_rush_yds":     ["QB", "RB"],
    "player_rush_tds":     ["QB", "RB"],
    "player_receptions":   ["RB", "WR", "TE"],
    "player_reception_yds":["RB", "WR", "TE"],
    "player_reception_tds":["RB", "WR", "TE"],
}

def random_commence_time():
    base = datetime.now(timezone.utc) + timedelta(days=1)
    delta = timedelta(
        days=random.randint(0, 6),
        hours=random.randint(0, 23),
        minutes=random.choice([0, 15, 30, 45])
    )
    return (base + delta).strftime("%Y-%m-%dT%H:%M:%SZ")

def generate_fake_nfl_slate(num_games=16):
    client = MongoClient(MONGO_URI)
    players = client[DB_NAME][COLLECTION_NAME]

    # Prepare 16 random matchups
    teams = [
        "ARI","ATL","BAL","BUF","CAR","CHI","CIN","CLE",
        "DAL","DEN","DET","GB","HOU","IND","JAX","KC",
        "LV","LAC","LAR","MIA","MIN","NE","NO","NYG",
        "NYJ","PHI","PIT","SEA","SF","TB","TEN","WAS"
    ]
    random.shuffle(teams)
    slate = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for _ in range(num_games):
        away = teams.pop()
        home = teams.pop()
        markets = []

        for prop, allowed_positions in positions_by_prop.items():
            outcomes = []
            # fetch only players of the right position AND on home/away team
            pool = []
            for pos in allowed_positions:
                docs = players.find({
                    "position": pos,
                    "team": {"$in": [home, away]}
                }, {"name":1})
                pool.extend(d["name"] for d in docs)
            if not pool:
                continue

            for player in pool:
                # generate a line
                line = round(
                    random.uniform(200, 350) if "yds" in prop else random.uniform(0.5, 3.5),
                    1
                )
                price_over  = round(random.uniform(1.5, 3.0), 2)
                price_under = round(random.uniform(1.5, 3.0), 2)
                outcomes.extend([
                    {"name":"Over",  "description":player, "point":line, "price":price_over},
                    {"name":"Under", "description":player, "point":line, "price":price_under},
                ])

            markets.append({
                "key":         prop,
                "last_update": now,
                "outcomes":    outcomes
            })

        slate.append({
            "id":            str(uuid.uuid4()),
            "sport_key":     "americanfootball_nfl",
            "sport_nice":    "NFL",
            "commence_time": random_commence_time(),
            "home_team":     home,
            "away_team":     away,
            "bookmakers": [
                {
                    "key":         "draftkings",
                    "title":       "DraftKings",
                    "last_update": now,
                    "markets":     markets
                }
            ]
        })

    return slate

if __name__ == "__main__":
    fake_slate = generate_fake_nfl_slate()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for idx, game in enumerate(fake_slate):
        path = os.path.join(OUTPUT_DIR, f"data{idx}.json")
        with open(path, "w") as f:
            json.dump(game, f, indent=2)
    print(f"Generated {len(fake_slate)} games in '{OUTPUT_DIR}'")

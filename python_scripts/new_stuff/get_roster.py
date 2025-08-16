#!/usr/bin/env python3
import os
import json
import requests
from pymongo import MongoClient, UpdateOne

# ——— CONFIG ———
SEASON            = int(os.getenv("SEASON", 2025))
ESPN_PLAYERS_URL  = (
    "https://lm-api-reads.fantasy.espn.com/apis/v3/"
    "games/ffl/seasons/{season}/players"
)
ESPN_TEAM_URL     = (
    "http://sports.core.api.espn.com/v2/sports/football/"
    "leagues/nfl/seasons/{season}/teams/{team_id}?lang=en&region=us"
)
MONGO_URI         = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME           = "fantasy_football"
COLLECTION_NAME   = "players"
TEAMS_COLL_NAME = "teams"

# ESPN position ID → fantasy position
POSITION_MAP = {
    0: "DEF", 1: "QB", 2: "RB", 3: "WR",
    4: "TE", 5: "K", 6: "P", 7: "DL",
    8: "LB", 9: "DB", 10: "LS"
}

# Only valid NFL team IDs (1–32)
VALID_TEAM_IDS = set(range(1, 35))
VALID_TEAM_IDS.remove(31)
VALID_TEAM_IDS.remove(32)

def fetch_espn_players(season: int):
    url = ESPN_PLAYERS_URL.format(season=season)
    params = {"view": "players_wl", "scoringPeriodId": 0}
    headers = {
        "X-Fantasy-Filter": json.dumps({
            "filterActive": {"value": True},
            "players":      {"limit": 2000}
        }),
        "User-Agent": "Mozilla/5.0"
    }
    resp = requests.get(url, params=params, headers=headers)
    resp.raise_for_status()
    return resp.json()

def fetch_team_info(season: int, team_ids: set):
    info = {}
    for tid in team_ids:
        resp = requests.get(
            ESPN_TEAM_URL.format(season=season, team_id=tid)
        )
        if resp.ok:
            data = resp.json()
            abbrev = data.get("abbreviation", "UNK")
            logo = next(
                (logo_item.get("href")
                 for logo_item in data.get("logos", [])
                 if "primary_logo_on_primary_color" in logo_item.get("rel", [])),
                None
            )
            info[tid] = {"abbrev": abbrev, "logo": logo}
        else:
            info[tid] = {"abbrev": "UNK", "logo": None}
            
        client = MongoClient(MONGO_URI)    
        teams_coll = client[DB_NAME][TEAMS_COLL_NAME]
        teams_coll.create_index([("season", 1), ("team_id", 1)], unique=True)
        ops: list[UpdateOne] = []
        ops.append(UpdateOne(
                {"season": season, "team_id": tid},
                {"$set": info[tid]},
                upsert=True
            ))
        if ops:
            teams_coll.bulk_write(ops)
            
    return info

def sync_players_to_mongo(season: int = SEASON):
    raw_players = fetch_espn_players(season)

    # Extract and filter valid team IDs only once
    team_ids = {
        (p.get("team", {}).get("id") or p.get("proTeamId"))
        for p in raw_players
    }
    team_ids = {tid for tid in team_ids
                if isinstance(tid, int) and tid in VALID_TEAM_IDS}

    # Fetch team abbrevs & logos once
    team_info = fetch_team_info(season, team_ids)

    client = MongoClient(MONGO_URI)
    coll   = client[DB_NAME][COLLECTION_NAME]
    ops    = []

    for p in raw_players:
        espn_id = p.get("id")
        if espn_id is None:
            continue
        name    = p.get("fullName") or p.get("player", {}).get("fullName", "")
        pos     = POSITION_MAP.get(p.get("defaultPositionId", 0), "UNK")

        tid     = p.get("team", {}).get("id") or p.get("proTeamId")
        
        if not isinstance(tid, int) or tid == 0:
            continue
        tinfo   = team_info.get(tid, {"abbrev":"UNK","logo":None})

        set_fields = {
            "name":      name,
            "position":  pos,
            "team":      tinfo["abbrev"],
            "espn_link": f"https://www.espn.com/nfl/player/_/id/{espn_id}",
            "headshot_url": f"https://a.espncdn.com/i/headshots/nfl/players/full/{espn_id}.png"
        }
        set_on_insert = {"eligible": True}
        headshot = p.get("player", {}).get("headshot", {}).get("url")
        if headshot:
            set_on_insert["headshot_url"] = headshot

        ops.append(UpdateOne(
            {"espn_id": espn_id},
            {"$set": set_fields, "$setOnInsert": set_on_insert},
            upsert=True
        ))

    if ops:
        res = coll.bulk_write(ops)
        print(f"Upserted: {res.upserted_count}, Modified: {res.modified_count}")
    else:
        print("No players found to sync.")

if __name__ == "__main__":
    sync_players_to_mongo()

import requests
from dotenv import load_dotenv
from collections import defaultdict
import os
import json
import statsapi
import numpy as np

load_dotenv()
SPORT = "baseball_mlb" #"americanfootball_nfl"
TEAM_SIZE = 30
API_KEY = os.getenv("ODDS_API_KEY")

def get_sports():
    url = "https://api.the-odds-api.com/v4/sports"
    params = {"apiKey": API_KEY}

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print("Error fetching sports:", e)
        return []
    
def get_events(SPORT = "baseball_mlb"):
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/events"
    params = {"apiKey": API_KEY}

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print("Error fetching events:", e)
        return []
    
def get_odds(eventId, market):
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/events/{eventId}/odds"

    params = {"apiKey": API_KEY,
              'markets': market, #, player_rush_yds, player_reception_yds
              "regions": "us",
              #"bookmakers":"draftkings"
              }
    

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print("Error fetching odds:", e)
        return []

def parse_json(file, props, scores):
    with open(file, "r") as f:
        odds_data = json.load(f)

    game = f"{odds_data['home_team']} vs {odds_data['away_team']}"
    player_data = {}

    for bookmaker in odds_data.get("bookmakers", []):
        for market in bookmaker.get("markets", []):
            prop_key = market.get("key")
            if prop_key not in props:
                continue

            for outcome in market.get("outcomes", []):
                name = outcome["description"]
                line = outcome.get("point")
                price = outcome.get("price")

                if line is None or price is None:
                    continue

                player_data.setdefault(name, {}).setdefault(prop_key, {}).setdefault(line, {})[
                    "over" if "over" in outcome["name"].lower() else "under"
                ] = price

    results = []
    for name, prop_lines in player_data.items():
        stats = []
        expected_score = 0.0

        for i, prop in enumerate(props):
            evs = []
            line_group = prop_lines.get(prop, {})
            for ln, prices in line_group.items():
                if "over" in prices and "under" in prices:
                    p_over = 1 / prices["over"]
                    p_under = 1 / prices["under"]
                    total = p_over + p_under
                    p_over /= total
                    p_under /= total
                    ev = p_over * (ln + 0.5) + p_under * (ln - 0.5)
                    evs.append(ev)

            stat = round(sum(evs) / len(evs), 3) if evs else None
            stats.append(stat)
            expected_score += (stat if stat is not None else 0) * scores[i]

        results.append({
            "name": name,
            "stats": [game] + stats,
            "expected_score": round(expected_score, 2)
        })

    return results




def get_today_data():
    espn_batters_props = ["batter_runs_scored", "batter_total_bases", "batter_rbis", "batter_walks", "batter_stolen_bases", "batter_strikeouts"]
    espn_pitchers_props = ["pitcher_strikeouts", "pitcher_hits_allowed", "pitcher_walks", "pitcher_earned_runs"]
    events = get_events()
    
    teams = set()
    
    for event in events:
        if len(teams) == TEAM_SIZE:
            break
        
        id = event["id"]
        date = event["commence_time"][:10]
        teams.add(event["home_team"])
        teams.add(event["away_team"])
         
        file = f"data/batters/{id}-{date.replace("-","_")}.json"
        
        with open(file, "w") as f:
            json.dump(get_odds(id, ",".join(espn_batters_props)), f, indent=2)
            
        file = f"data/pitchers/{id}-{date.replace("-","_")}.json"
            
        with open(file, "w") as f:
            json.dump(get_odds(id, ",".join(espn_pitchers_props)), f, indent=2)
            
        

#get_today_data()

# with open("joe2.json", "w") as f:
#    json.dump(get_odds("86066964719c5c58af7907ad2005d106", ",".join(espn_batters_props)), f, indent=2)

# with open("joe2.json", "r") as f:
#     odds_data = json.load(f)
    
# for book in odds_data["bookmakers"]:
#     print(book["key"], len(book["markets"]))
    
#     for market in book["markets"]:
#         print(market["key"])



#get_today_data()
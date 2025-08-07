import requests
from dotenv import load_dotenv
from collections import defaultdict
import os
import json
import statsapi
import numpy as np
import pandas as pd

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
    player_data = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))

    # Collect raw data
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

                direction = "over" if "over" in outcome["name"].lower() else "under"
                player_data[name][prop_key][line][direction] = price

    # Compute expected values
    raw_stats = []
    for name, prop_dict in player_data.items():
        row = []
        for prop in props:
            line_group = prop_dict.get(prop, {})
            evs = []

            for ln, prices in line_group.items():
                if "over" in prices and "under" in prices:
                    p_over = 1 / prices["over"]
                    p_under = 1 / prices["under"]
                    total = p_over + p_under
                    p_over /= total
                    p_under /= total
                    ev = p_over * (ln + 0.5) + p_under * (ln - 0.5)
                    evs.append(ev)

            row.append(round(sum(evs) / len(evs), 3) if evs else None)
        raw_stats.append((name, row))

    # Build DataFrame
    names = [name for name, _ in raw_stats]
    data = [row for _, row in raw_stats]
    df = pd.DataFrame(data, index=names, columns=props)

    # Filter out players with 2+ missing stats
    df = df[df.isnull().sum(axis=1) < 2]

    # Compute mean and std
    col_means = df.mean()
    col_stds = df.std()

    # Compute fill values: mean - std if both available,
    # fallback to mean if only mean available,
    # fallback to 0.0 otherwise
    col_fill = pd.Series(index=df.columns, dtype=float)
    for col in df.columns:
        mean = col_means[col]
        std = col_stds[col]
        if pd.notna(mean) and pd.notna(std):
            col_fill[col] = max(0.0, mean - std)
        elif pd.notna(mean):
            col_fill[col] = max(0.0, mean)
        else:
            col_fill[col] = 0.0

    # Track which values were originally missing
    na_mask = df.isna()

    # Fill missing values
    df_filled = df.fillna(col_fill)
    
    print(df_filled)

    # Build final output
    final_results = []
    for name in df_filled.index:
        display_stats = []
        filled_row = []
        for i, col in enumerate(df.columns):
            if na_mask.loc[name, col]:
                val = col_fill[col]
                display_stats.append(f"{round(val, 3)}*")
            else:
                val = df.loc[name, col]
                display_stats.append(str(round(val, 3)))
            filled_row.append(val)

        expected_score = round(sum(filled_row[i] * scores[i] for i in range(len(scores))), 2)
        final_results.append({
            "name": name,
            "stats": [game] + display_stats,
            "expected_score": expected_score
        })

    return final_results

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
         
        file = f"data/mlb/{id}-{date.replace("-","_")}.json"
        
        with open(file, "w") as f:
            json.dump(get_odds(id, ",".join(espn_batters_props)), f, indent=2)
            
        file = f"data/mlb/{id}-{date.replace("-","_")}.json"
            
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
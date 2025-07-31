import requests
from dotenv import load_dotenv
from collections import defaultdict
import os
import json
import statsapi

load_dotenv()
SPORT = "baseball_mlb" #"americanfootball_nfl"
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
    
def get_events():
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
              "bookmakers":"draftkings"}
    

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print("Error fetching odds:", e)
        return []

def parse_json(file):
    with open(file, "r") as f:
        odds_data = json.load(f)

    players = defaultdict(dict)
    for bookmaker in odds_data["bookmakers"]:
        for outcome in bookmaker["markets"][0]["outcomes"]:
            name = outcome["description"]
            line = outcome["point"]

            players[name]["name"] = name
            players[name]["line"] = line
            if outcome["name"] == "Over":
                players[name]["over_odds"] = outcome["price"]
            else:
                players[name]["under_odds"] = outcome["price"]
        
    cleaned_players = []

    for player in players.values():
        if "over_odds" in player and "under_odds" in player:
            over_odds = player["over_odds"]
            under_odds = player["under_odds"]
            line = player["line"]

            # Calculate implied probabilities
            p_over = 1 / over_odds
            p_under = 1 / under_odds
            total = p_over + p_under
            p_over /= total
            p_under /= total

            # Approximate expected value
            ev = p_over * (line + 0.5) + p_under * (line - 0.5)
            
            # home = statsapi.lookup_team(odds_data["home_team"])[0]
            # away = statsapi.lookup_team(odds_data["away_team"])[0]
            
            game = f"{odds_data["home_team"]} vs {odds_data["away_team"]}"
            
            # lookup_player = statsapi.lookup_player(name)
            # if (len(lookup_player) == 1):
            #     print(lookup_player[0]["id"])
            
            cleaned_players.append({"name": player["name"], "stats": [game, round(ev, 3), player["line"], player["over_odds"], player["under_odds"]]})

    return cleaned_players



def get_today_data(line, role):
    # batter_hits_runs_rbis     batters
    # pitcher_strikeouts        hitters
    events = get_events()
    date = events[0]["commence_time"][:10]
    for event in events:
        if event["commence_time"][:10] == date:
            id = event["id"]
            file = f"data/{role}/{line}-{id}-{date.replace("-","_")}.json"
            
            with open(file, "w") as f:
                json.dump(get_odds(id, line), f, indent=2)

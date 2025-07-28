import requests
from dotenv import load_dotenv
import os
import json

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
              "bookmakers":"fanduel,draftkings"}
    

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print("Error fetching odds:", e)
        return []
    



# odds = get_odds("75733d0036dc1f8de4c15b87f6a6a697", "batter_hits_runs_rbis")
# for odd in odds:
#     print(odd)
# print(odds)

# with open("odds_cache.json", "w") as f:
#     json.dump(odds, f, indent=2)

with open("odds_cache.json", "r") as f:
    odds_data = json.load(f)

for i in odds_data["bookmakers"]:
    print(i["key"])





# events = get_events()
# for event in events:
#     print(event)
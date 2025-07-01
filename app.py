from flask import Flask, render_template
import requests
from dotenv import load_dotenv
import os

load_dotenv()
API_KEY = os.getenv("ODDS_API_KEY")

app = Flask(__name__)

@app.route("/")
def home():
    # You can replace this with dynamic data later
    players = [
        {"name": "Patrick Mahomes", "team": "KC Chiefs", "odds": "+350"},
        {"name": "Christian McCaffrey", "team": "49ers", "odds": "+900"},
    ]
    return render_template("index.html", players=players)

def get_available_sports():
    url = "https://api.the-odds-api.com/v4/sports"
    params = {"apiKey": API_KEY}

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()  # Raise exception for HTTP errors
        sports = response.json()
        return sports
    except requests.exceptions.RequestException as e:
        print("Error fetching sports:", e)
        return []
    
def get_player_props(markets="player_pass_yards", sport = "americanfootball_nfl"):
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds"
    print(url)
    params = {
        "apiKey": API_KEY,
        "regions": "us",
        "markets": markets,
        "oddsFormat": "american",
    }
    try:
        res = requests.get(url, params=params)
        res.raise_for_status()
        return res.json()
    except requests.RequestException as e:
        print("Error fetching NFL odds:", e)
        return None

if __name__ == "__main__":
    #app.run(debug=True)

    props = get_player_props("player_pass_yards")
    if props:
        print(f"Found {len(props)} games with player passing yard props.\n")
        for game in props[:2]:  # Show a few games
            print(f"{game['home_team']} vs {game['away_team']}")
            for bookmaker in game["bookmakers"]:
                print(f"  Bookmaker: {bookmaker['title']}")
                for market in bookmaker["markets"]:
                    for outcome in market["outcomes"]:
                        print(f"    {outcome['name']}: {outcome['price']} | Line: {outcome.get('point')}")
            print()
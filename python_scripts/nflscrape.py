import nfl_data_py as nfl
import pandas as pd
import pymongo

# [season, team, position, depth_chart_position, jersey_number, status, player_name, first_name, last_name, birth_date, height, weight, college, player_id, espn_id, sportradar_id, yahoo_id, rotowire_id, pff_id, 
# pfr_id, fantasy_data_id, sleeper_id, years_exp, headshot_url, ngs_position, week, game_type, status_description_abbr, football_name, esb_id, gsis_it_id, smart_id, entry_year, rookie_year, draft_club, draft_number, age]



client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client["nfl_data"]
players_collection = db["nfl_players"]

players_df = nfl.import_seasonal_rosters([2024])
active_players_df = players_df[(players_df['status'] == 'ACT')]

position_map = {
    "QB": "Quarterback",
    "RB": "Running Back",
    "WR": "Wide Receiver",
    "TE": "Tight End",
}

nfl_team_codes = {
    "ARI": "Arizona Cardinals",
    "ATL": "Atlanta Falcons",
    "BAL": "Baltimore Ravens",
    "BUF": "Buffalo Bills",
    "CAR": "Carolina Panthers",
    "CHI": "Chicago Bears",
    "CIN": "Cincinnati Bengals",
    "CLE": "Cleveland Browns",
    "DAL": "Dallas Cowboys",
    "DEN": "Denver Broncos",
    "DET": "Detroit Lions",
    "GB":  "Green Bay Packers",
    "HOU": "Houston Texans",
    "IND": "Indianapolis Colts",
    "JAX": "Jacksonville Jaguars",
    "KC":  "Kansas City Chiefs",
    "LV":  "Las Vegas Raiders",
    "LAC": "Los Angeles Chargers",
    "LA": "Los Angeles Rams",
    "MIA": "Miami Dolphins",
    "MIN": "Minnesota Vikings",
    "NE":  "New England Patriots",
    "NO":  "New Orleans Saints",
    "NYG": "New York Giants",
    "NYJ": "New York Jets",
    "PHI": "Philadelphia Eagles",
    "PIT": "Pittsburgh Steelers",
    "SEA": "Seattle Seahawks",
    "SF":  "San Francisco 49ers",
    "TB":  "Tampa Bay Buccaneers",
    "TEN": "Tennessee Titans",
    "WAS": "Washington Commanders"
}

# Define which fields to keep
fields = [
    "player_name", "position", "team", "player_id", "headshot_url", "espn_id"
]

# Filter columns
active_players_df = active_players_df[fields]

# Optionally add profile URLs using ESPN ID (example format)
def build_profile_url(row):
    if pd.notna(row["espn_id"]):
        return f"https://www.espn.com/nfl/player/_/id/{int(row['espn_id'])}"
    return None

active_players_df["profile_url"] = active_players_df.apply(build_profile_url, axis=1)
active_players_df["position"] = active_players_df["position"].map(position_map)
active_players_df = active_players_df.dropna(subset=["position"])
active_players_df["team"] = active_players_df["team"].map(nfl_team_codes)

# Convert to dicts for Mongo
player_docs = active_players_df.to_dict("records")

# Clear and reinsert if needed
players_collection.delete_many({})  # optional: reset collection
if player_docs:
    players_collection.insert_many(player_docs)
    print(f"Inserted {len(player_docs)} players.")
else:
    print("No player documents to insert.")
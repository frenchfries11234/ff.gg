import json
import os
from functools import wraps
from dotenv import load_dotenv
from flask import Flask, redirect, url_for, render_template, session, request, jsonify
from flask_dance.contrib.google import make_google_blueprint, google
from flask_login import (
    LoginManager, login_user, logout_user, current_user, login_required, UserMixin
)
from flask_cors import CORS
from pymongo import MongoClient
from bson.objectid import ObjectId
from collections import defaultdict
import python_scripts.the_odds as the_odds
from datetime import datetime

# Load env
load_dotenv()

# Flask app setup
app = Flask(__name__)
CORS(app)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev")

# MongoDB setup
client = MongoClient("mongodb://localhost:27017/")
db = client["user_data"]
users_collection = db["users"]

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "index"

# Data
batters_dir = "data/batters"
espn_batters_props = ["batter_runs_scored", "batter_total_bases", "batter_rbis", "batter_walks", "batter_stolen_bases"]
espn_batters_scores = [1, 1, 1, 1, 1]

pitchers_dir = "data/pitchers"
espn_pitchers_props = ["pitcher_strikeouts", "pitcher_hits_allowed", "pitcher_walks", "pitcher_earned_runs"]
espn_pitchers_scores = [1, -1, -1, -2]

positions_by_prop = {
    "player_pass_yds":      ["QB"],
    "player_pass_tds":      ["QB"],
    "player_rush_yds":      ["QB", "RB"],
    "player_rush_tds":      ["QB", "RB"],
    "player_receptions":    ["RB", "WR", "TE"],
    "player_reception_yds": ["RB", "WR", "TE"],
    "player_reception_tds": ["RB", "WR", "TE"],
}
POSITIONS_ORDER = ["QB", "RB", "WR", "TE"]

# User class
class User(UserMixin):
    def __init__(self, user_doc):
        self.id = str(user_doc["_id"])  # required by Flask-Login
        self.email = user_doc["email"]

# Flask-Login user loader
@login_manager.user_loader
def load_user(user_id):
    user_doc = users_collection.find_one({"_id": ObjectId(user_id)})
    return User(user_doc) if user_doc else None

# Google OAuth blueprint
google_bp = make_google_blueprint(
    client_id=os.environ["GOOGLE_OAUTH_CLIENT_ID"],
    client_secret=os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
    redirect_url="/login/callback",
    scope=["openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"],
)
app.register_blueprint(google_bp, url_prefix="/login")

# Routes
@app.route("/login/callback")
def index():
    if not google.authorized:
        return redirect(url_for("google.login"))
    
    resp = google.get("/oauth2/v2/userinfo")
    if not resp.ok:
        return "Failed to fetch user info."
    
    info = resp.json()
    email = info["email"]

    session["email"] = email  # optional: store in session for template use

    # Lookup or create user
    user_doc = users_collection.find_one({"email": email})
    if not user_doc:
        users_collection.insert_one({"email": email})
        user_doc = users_collection.find_one({"email": email})

    user = User(user_doc)
    login_user(user)  # Flask-Login

    return redirect(url_for("nfl"))

@app.route("/logout")
def logout():
    # Flask-Login logout
    logout_user()

    # Remove OAuth token from Flask-Dance
    token = google.token
    if token:
        del google.token  # this logs out the Google session for Flask-Dance

    # Clear session variables if needed
    session.clear()

    return redirect(url_for("nfl"))

@app.route("/")
@app.route("/nfl")
def nfl():
    db  = client["fantasy_football"]
    col = db["players"]

    # Fetch players including their games and team info
    players = list(col.find(
        {"position": {"$in": POSITIONS_ORDER}},
        {"name": 1, "espn_id": 1, "team": 1, "team_logo": 1, "position": 1, "games": 1}
    ))

    # Group by position
    grouped = defaultdict(list)
    for p in players:
        grouped[p["position"]].append(p)

    # Build players_by_role in the specified order
    players_by_role = {}
    for role in POSITIONS_ORDER:
        group = grouped.get(role, [])
        if not group:
            continue

        # Determine relevant props and human-readable column names
        props   = [prop for prop, roles in positions_by_prop.items() if role in roles]
        columns = ["Team"] + [prop.replace("player_", "").replace("_", " ").title() for prop in props]

        rows = []
        for p in group:
            # Find most recent game by commence_time
            games = p.get("games", [])
            recent_proj = {}
            if games:
                try:
                    games_sorted = sorted(
                        games,
                        key=lambda g: datetime.fromisoformat(g["commence_time"].replace("Z", "+00:00"))
                    )
                    recent_proj = games_sorted[-1].get("projections", {})
                except Exception:
                    recent_proj = {}

            # Build stats: team cell plus one stat per prop
            stats = [{
                "abbrev": p.get("team", "—"),
                "logo":   p.get("team_logo")
            }]
            stats += [round(recent_proj.get(prop, 0), 2) for prop in props]

            rows.append({
                "name":    p["name"],
                "espn_id": p["espn_id"],
                "stats":   stats
            })

        players_by_role[role] = {
            "columns": columns,
            "rows":    rows
        }

    return render_template("nfl.html", players=players_by_role)

@app.route("/nfl/players/<int:espn_id>")
def player_page(espn_id):
    db  = client["fantasy_football"]
    col = db["players"]

    # 1) Look up player by numeric espn_id
    player = col.find_one({"espn_id": espn_id})
    if not player:
        return render_template("player_not_found.html", espn_id=espn_id), 404

    # 2) Sort their games most‐recent first
    games = player.get("games", [])
    try:
        games = sorted(
            games,
            key=lambda g: datetime.fromisoformat(g["commence_time"].replace("Z", "+00:00")),
            reverse=True
        )
    except Exception:
        pass
    player["games"] = games

    # 3) Render, passing headshot, team_logo, and sorted games
    return render_template("player.html", player=player)

@app.route("/mlb")
def mlb():
    batter_rows = []
    for filename in os.listdir(batters_dir):   
        filepath = os.path.join(batters_dir, filename)
        batter_rows += the_odds.parse_json(filepath, espn_batters_props, espn_batters_scores)

    pitcher_rows = []
    for filename in os.listdir(pitchers_dir):   
        filepath = os.path.join(pitchers_dir, filename)
        pitcher_rows += the_odds.parse_json(filepath, espn_pitchers_props, espn_pitchers_scores)  # Replace if pitcher logic differs
    
    players = {
    "batters": {
        "columns": ["Name", "Game", "Expected Score"] + espn_batters_props,
        "rows": batter_rows
    },
    "pitchers": {
        "columns": ["Name", "Game", "Expected Score"] + espn_pitchers_props,
        "rows": pitcher_rows
    }
    }

    return render_template("mlb.html", players=players, email=session.get("email"))

@app.route("/teams")
@login_required
def teams():
    user = users_collection.find_one({"email": current_user.email})
    teams = user.get("teams", [])
    return render_template("teams.html", teams=teams)

@app.route("/api/team", methods=["POST"])
def save_team():
    data = request.json
    email = data.get("email")
    team_name = data.get("teamName")
    league_id = data.get("leagueId")
    team_id = data.get("teamId")
    season_id = data.get("seasonId")
    
    if not team_name:
        return jsonify({"error": "Missing teamName"}), 400
    
    

    team_entry = {
        "teamName": team_name,
        "leagueId": league_id,
        "teamId": team_id,
        "seasonId": season_id
    }
    print(team_entry)
    # Target user by email and update
    result = users_collection.update_one(
        {"email": email},
        {"$addToSet": {"teams": team_entry}},
        upsert=True
    )


    if result.modified_count == 0:
        return jsonify({"error": "User not found or team not added"}), 404

    return jsonify({"message": "Team added to user"}), 200

# Run
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(debug=True, host="localhost", port=port)

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

def iso_to_dt(s):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None

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

from flask import request

@app.route("/")
@app.route("/nfl")
def nfl():
    db   = client["fantasy_football"]
    pcol = db["players"]
    tcol = db["teams"]

    # Build abbrev -> logo map from teams collection
    logo_by_abbrev = {}
    for t in tcol.find({}, {"_id": 0, "abbrev": 1, "logo": 1}):
        ab = (t.get("abbrev") or "").upper()
        if ab and ab not in logo_by_abbrev:
            logo_by_abbrev[ab] = t.get("logo")

    players = list(pcol.find(
        {"position": {"$in": POSITIONS_ORDER}},
        {"name": 1, "espn_id": 1, "team": 1, "position": 1, "games": 1}
    ))

    grouped = defaultdict(list)
    for p in players:
        grouped[p["position"]].append(p)

    # optional: let a query param set the initial label (defaults to PPR)
    scoring = request.args.get("scoring", "espn_ppr")
    scoring_labels = {"espn_ppr": "Fantasy (PPR)", "espn_half": "Fantasy (Half)", "espn_std": "Fantasy (Standard)"}
    fantasy_header = scoring_labels.get(scoring, "Fantasy")

    players_by_role = {}
    for role in POSITIONS_ORDER:
        group = grouped.get(role, [])
        if not group:
            continue

        props   = [prop for prop, roles in positions_by_prop.items() if role in roles]
        # Team, Opponent, Fantasy, then the per-prop EVs
        columns = ["Team", "Opponent", fantasy_header] + [
            prop.replace("player_", "").replace("_", " ").title() for prop in props
        ]

        rows = []
        for p in group:
            # latest game (if any)
            recent = None
            games = p.get("games", []) or []
            if games:
                games_sorted = sorted(
                    [g for g in games if g.get("commence_time")],
                    key=lambda g: iso_to_dt(g["commence_time"]) or datetime.min
                )
                recent = games_sorted[-1] if games_sorted else None

            team_abbrev = (p.get("team") or "—").upper()
            team_logo   = logo_by_abbrev.get(team_abbrev)

            opp_abbrev = None
            opp_logo   = None
            if recent:
                home = (recent.get("home_team") or "").upper()
                away = (recent.get("away_team") or "").upper()
                if team_abbrev == home:
                    opp_abbrev = away
                elif team_abbrev == away:
                    opp_abbrev = home
                if opp_abbrev:
                    opp_logo = logo_by_abbrev.get(opp_abbrev)

            projections = recent.get("projections", {}) if recent else {}

            # Fantasy values (all three stored so the client can toggle)
            f = (recent or {}).get("fantasy", {}) or {}
            fantasy_cell = {
                "type": "fantasy",
                "values": {
                    "espn_ppr":  round(float(f.get("espn_ppr", 0) or 0), 2),
                    "espn_half": round(float(f.get("espn_half", 0) or 0), 2),
                    "espn_std":  round(float(f.get("espn_std", 0) or 0), 2),
                }
            }

            team_cell = {"abbrev": team_abbrev, "logo": team_logo}
            opp_cell  = {"abbrev": opp_abbrev,  "logo": opp_logo}

            stats = [
                team_cell,
                opp_cell,
                fantasy_cell,  # single column the UI can swap (PPR/Half/Std)
            ] + [round(float(projections.get(prop, 0) or 0), 2) for prop in props]

            rows.append({
                "name":    p["name"],
                "espn_id": p["espn_id"],
                "stats":   stats
            })

        players_by_role[role] = {"columns": columns, "rows": rows}

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

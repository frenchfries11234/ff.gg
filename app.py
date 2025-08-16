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
from datetime import datetime, timezone
from urllib.parse import urlencode

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

POSITIONS_BY_PROP = {
    "player_pass_yds":      ["QB"],
    "player_pass_tds":      ["QB"],
    "player_rush_yds":      ["QB", "RB"],
    "player_rush_tds":      ["QB", "RB"],
    "player_receptions":    ["RB", "WR", "TE"],
    "player_reception_yds": ["RB", "WR", "TE"],
    "player_reception_tds": ["RB", "WR", "TE"],
}
POSITIONS_ORDER = ["QB", "RB", "WR", "TE"]

SCORING_LABELS = {
    "espn_ppr":  "Fantasy (PPR)",
    "espn_half": "Fantasy (Half)",
    "espn_std":  "Fantasy (Standard)",
}

def iso_to_dt(s):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None
    
def _parse_iso(s: str):
    try:
        # handles ...Z by converting to +00:00
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None

def build_logo_map(tcol):
    out = {}
    for t in tcol.find({}, {"_id": 0, "abbrev": 1, "logo": 1}):
        ab = (t.get("abbrev") or "").upper()
        if ab and ab not in out:
            out[ab] = t.get("logo")
    return out

def get_recent_game(player_doc):
    games = player_doc.get("games") or []
    games = [g for g in games if g.get("commence_time")]
    games.sort(key=lambda g: _parse_iso(g["commence_time"]) or datetime.min)
    return games[-1] if games else None

def team_and_opponent_cells(team_abbrev, recent, logo_by_abbrev):
    team_abbrev = (team_abbrev or "—").upper()
    team_logo = logo_by_abbrev.get(team_abbrev)
    opp_abbrev = opp_logo = None
    if recent:
        home = (recent.get("home_team") or "").upper()
        away = (recent.get("away_team") or "").upper()
        if team_abbrev == home:
            opp_abbrev = away
        elif team_abbrev == away:
            opp_abbrev = home
        if opp_abbrev:
            opp_logo = logo_by_abbrev.get(opp_abbrev)
    return {"abbrev": team_abbrev, "logo": team_logo}, {"abbrev": opp_abbrev, "logo": opp_logo}

def fantasy_cell(recent):
    f = (recent or {}).get("fantasy") or {}
    return {
        "type": "fantasy",
        "values": {
            "espn_ppr":  round(float(f.get("espn_ppr", 0)  or 0), 2),
            "espn_half": round(float(f.get("espn_half", 0) or 0), 2),
            "espn_std":  round(float(f.get("espn_std", 0)  or 0), 2),
        }
    }

def projection_values(recent, props):
    proj = (recent or {}).get("projections") or {}
    return [round(float(proj.get(prop, 0) or 0), 2) for prop in props]

def build_columns(props, scoring_key):
    return (["Team", "Opponent", SCORING_LABELS.get(scorिंग_key := scoring_key, "Fantasy")] + [prop.replace("player_", "").replace("_", " ").title() for prop in props])

def build_row(player_doc, logo_by_abbrev, props):
    recent = get_recent_game(player_doc)
    team_cell, opp_cell = team_and_opponent_cells(player_doc.get("team"), recent, logo_by_abbrev)
    return {
        "name":    player_doc.get("name"),
        "espn_id": player_doc.get("espn_id"),
        "stats":   [team_cell, opp_cell, fantasy_cell(recent)] + projection_values(recent, props),
    }
    
@app.route("/")
@app.route("/nfl")
def nfl():
    db   = client["fantasy_football"]
    pcol = db["players"]
    tcol = db["teams"]

    logo_by_abbrev = build_logo_map(tcol)

    players = list(pcol.find(
        {"position": {"$in": POSITIONS_ORDER}},
        {"name": 1, "espn_id": 1, "team": 1, "position": 1, "games": 1}
    ))

    grouped = defaultdict(list)
    for p in players:
        grouped[p["position"]].append(p)

    scoring = request.args.get("scoring", "espn_ppr")
    fantasy_header = SCORING_LABELS.get(scoring, "Fantasy")

    players_by_role = {}
    for role in POSITIONS_ORDER:
        group = grouped.get(role, [])
        if not group:
            continue

        props = [prop for prop, roles in POSITIONS_BY_PROP.items() if role in roles]
        columns = ["Team", "Opponent", fantasy_header] + [
            prop.replace("player_", "").replace("_", " ").title() for prop in props
        ]

        rows = [build_row(p, logo_by_abbrev, props) for p in group]
        players_by_role[role] = {"columns": columns, "rows": rows}

    return render_template("nfl.html", players=players_by_role)

@app.route("/teams")
@login_required
def teams():
    user = users_collection.find_one({"email": current_user.email}) or {}
    teams = user.get("teams", [])

    fdb  = client["fantasy_football"]
    pcol = fdb["players"]
    tcol = fdb["teams"]

    logo_by_abbrev = build_logo_map(tcol)

    def make_roster_url(t):
        params = {"leagueId": t.get("leagueId"), "teamId": t.get("teamId")}
        if t.get("seasonId"):
            params["seasonId"] = t["seasonId"]
        return f"https://fantasy.espn.com/football/team?{urlencode(params)}"

    scoring = request.args.get("scoring", "espn_ppr")
    fantasy_header = SCORING_LABELS.get(scoring, "Fantasy")

    for t in teams:
        t.setdefault("players", [])
        t["players"] = sorted(
            t["players"],
            key=lambda p: (str(p.get("team", "")).upper(), str(p.get("name", "")).lower())
        )

        # links + labels for the card
        t["roster_url"] = make_roster_url(t)
        t["league_url"] = f"https://fantasy.espn.com/football/league?leagueId={t.get('leagueId')}" if t.get("leagueId") else None
        t["league_name"] = (t.get("league", {}) or {}).get("name") or t.get("leagueName") or "League"
        t["team_logo"] = t.get("teamLogo")  # provided by your content script, if you store it

        # 1) IDs from saved roster (from your extension)
        espn_ids = [str(p.get("espnId") or p.get("espn_id")) for p in t["players"] if p.get("espnId") or p.get("espn_id")]
        espn_ids = list({int(eid) for eid in espn_ids if eid})

        # 2) Fetch full docs exactly like /nfl uses
        docs = list(pcol.find(
            {"espn_id": {"$in": espn_ids}},
            {"name": 1, "espn_id": 1, "team": 1, "position": 1, "games": 1}
        ))

        # 3) Any players missing in DB → placeholder with no games
        docs_by_id = {str(d["espn_id"]): d for d in docs}
        for p in t["players"]:
            eid = str(p.get("espnId") or "")
            if eid and eid not in docs_by_id:
                docs_by_id[eid] = {
                    "name": p.get("name"),
                    "espn_id": eid,
                    "team": p.get("team"),
                    "position": None,
                    "games": [],
                }
        resolved_players = list(docs_by_id.values())

        # 4) Union of props across positions on this roster
        roles_present = {rp.get("position") for rp in resolved_players if rp.get("position")}
        props_union = [prop for prop, roles in POSITIONS_BY_PROP.items() if any(role in roles for role in roles_present)]

        # 5) Build same columns/rows as /nfl, with Position column
        columns = ["Team", "Opponent", "Pos", fantasy_header] + [
            prop.replace("player_", "").replace("_", " ").title() for prop in props_union
        ]
        rows = [
            {**row, "stats": [row["stats"][0], row["stats"][1], str(pdoc.get("position") or "").upper(), *row["stats"][2:]]}
            for pdoc in resolved_players
            for row in [build_row(pdoc, logo_by_abbrev, props_union)]
        ]
        t["table"] = {"columns": columns, "rows": rows}

    return render_template("teams.html", teams=teams)


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


@app.route("/nfl/players/<int:espn_id>")
def player_page(espn_id):
    db   = client["fantasy_football"]
    pcol = db["players"]
    tcol = db["teams"]

    player = pcol.find_one({"espn_id": espn_id})
    if not player:
        return render_template("player_not_found.html", espn_id=espn_id), 404

    # team logos map (by abbrev)
    logo_by_abbrev = {
        (t.get("abbrev") or "").upper(): (t.get("logo") or t.get("logo_primary_on_primary"))
        for t in tcol.find({}, {"abbrev": 1, "logo": 1, "logo_primary_on_primary": 1})
    }

    # pick prop columns by position
    role = player.get("position")
    prop_columns = [k for k, roles in POSITIONS_BY_PROP.items() if role in roles]
    prop_titles  = [k.replace("player_", "").replace("_", " ").title() for k in prop_columns]

    # sort games newest→oldest
    games = player.get("games", []) or []
    try:
        games.sort(
            key=lambda g: datetime.fromisoformat(g["commence_time"].replace("Z", "+00:00")),
            reverse=True
        )
    except Exception:
        pass

    team_abbrev = (player.get("team") or "").upper()
    rows = []
    for g in games:
        home = (g.get("home_team") or "").upper()
        away = (g.get("away_team") or "").upper()
        opp  = away if team_abbrev == home else (home if team_abbrev == away else None)
        opp_logo = logo_by_abbrev.get(opp)

        projections = g.get("projections", {}) or {}
        fantasy     = g.get("fantasy", {}) or {}

        rows.append({
            "date_str": g.get("commence_time", "")[:10],
            "opp_abbrev": opp,
            "opp_logo": opp_logo,
            "fantasy": {
                "espn_ppr":  round(float(fantasy.get("espn_ppr", 0) or 0), 2),
                "espn_half": round(float(fantasy.get("espn_half", 0) or 0), 2),
                "espn_std":  round(float(fantasy.get("espn_std", 0) or 0), 2),
            },
            "props": [ round(float(projections.get(pk, 0) or 0), 2) for pk in prop_columns ]
        })

    return render_template(
        "player.html",
        player=player,
        team_logo=logo_by_abbrev.get(team_abbrev),
        espn_link=f"https://www.espn.com/nfl/player/_/id/{espn_id}",
        rows=rows,
        prop_titles=prop_titles
    )

@app.route("/mlb")
def mlb():
    # batter_rows = []
    # for filename in os.listdir(batters_dir):   
    #     filepath = os.path.join(batters_dir, filename)
    #     batter_rows += the_odds.parse_json(filepath, espn_batters_props, espn_batters_scores)

    # pitcher_rows = []
    # for filename in os.listdir(pitchers_dir):   
    #     filepath = os.path.join(pitchers_dir, filename)
    #     pitcher_rows += the_odds.parse_json(filepath, espn_pitchers_props, espn_pitchers_scores)  # Replace if pitcher logic differs
    
    # players = {
    # "batters": {
    #     "columns": ["Name", "Game", "Expected Score"] + espn_batters_props,
    #     "rows": batter_rows
    # },
    # "pitchers": {
    #     "columns": ["Name", "Game", "Expected Score"] + espn_pitchers_props,
    #     "rows": pitcher_rows
    # }
    # }

    # return render_template("mlb.html", players=players, email=session.get("email"))
    return redirect("/")

@app.route("/api/nfl/search-index")
def nfl_search_index():
    db   = client["fantasy_football"]
    pcol = db["players"]

    players = pcol.find(
        {"position": {"$in": ["QB", "RB", "WR", "TE"]}},
        {"name": 1, "espn_id": 1, "team": 1, "position": 1, "games": 1}
    )

    def iso_to_dt(s):
        from datetime import datetime
        try: return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except: return None

    results = []
    for p in players:
        latest = None
        games = p.get("games", []) or []
        if games:
            gs = sorted(
                [g for g in games if g.get("commence_time")],
                key=lambda g: iso_to_dt(g["commence_time"]) or datetime.min
            )
            latest = gs[-1] if gs else None
        fantasy = (latest or {}).get("fantasy", {}) or {}
        results.append({
            "name": p["name"],
            "espn_id": p["espn_id"],
            "team": (p.get("team") or "").upper(),
            "position": p.get("position"),
            "fantasy_ppr": round(float(fantasy.get("espn_ppr", 0) or 0), 2),
        })
    return jsonify(results)


@app.route("/api/team", methods=["POST"])
def save_team():
    data = request.json or {}
    email = data.get("email")
    team_name = data.get("teamName")
    season_id = str(data.get("seasonId")) if data.get("seasonId") is not None else None
    league_id = str(data.get("leagueId")) if data.get("leagueId") is not None else None
    league_name = str(data.get("leagueName")) if data.get("leagueName") is not None else None
    team_id   = str(data.get("teamId")) if data.get("teamId") is not None else None 
    players   = data.get("players", [])
    
    if not email:
        return jsonify({"error": "Missing email"}), 400
    if not team_name:
        return jsonify({"error": "Missing teamName"}), 400
    if not league_id or not team_id:
        return jsonify({"error": "Missing leagueId or teamId"}), 400

    # 1) Try to update existing team (match by leagueId + teamId)
    res = users_collection.update_one(
        {"email": email, "teams.leagueId": league_id, "teams.teamId": team_id},
        {"$set": {
            "teams.$.teamName": team_name,
            "teams.$.seasonId": season_id,
            "teams.$.leagueId": league_id,
            "teams.$.leagueName": league_name,
            "teams.$.teamId": team_id,
            "teams.$.players": players,
            "teams.$.updatedAt": datetime.now(timezone.utc)
,
        }}
    )

    if res.matched_count > 0:
        return jsonify({"message": "Team updated"}), 200

    # 2) If not found, append new team (and create user doc if needed)
    team_entry = {
        "teamName": team_name,
        "seasonId": season_id,
        "leagueId": league_id,
        "leagueName": league_name,
        "teamId": team_id,
        "players": players,
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    }

    users_collection.update_one(
        {"email": email},
        {"$push": {"teams": team_entry}},
        upsert=True
    )
    return jsonify({"message": "Team added to user"}), 200

# Run
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(debug=True, host="localhost", port=port)

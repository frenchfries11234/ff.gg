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

import python_scripts.the_odds as the_odds

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
login_manager.login_view = "google.login"

# Data directories
batters_dir = "data/batters"
pitchers_dir = "data/pitchers"

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

    return redirect(url_for("mlb"))

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

    return redirect(url_for("mlb"))

@app.route("/nfl")
def nfl():
    players = {
        "batters": {
            "columns": ["batter_hits_runs_rbis", "Line", "Over", "Under"],
            "rows": []
        },
        "pitchers": {
            "columns": ["ERA", "SO", "W"],
            "rows": []
        }
    }
    return render_template('nfl.html', players=players)

@app.route("/")
@app.route("/mlb")
def mlb():
    batter_rows = []
    for filename in os.listdir(batters_dir):   
        filepath = os.path.join(batters_dir, filename)
        batter_rows += the_odds.parse_json(filepath)
        
    pitcher_rows = []
    for filename in os.listdir(pitchers_dir):   
        filepath = os.path.join(pitchers_dir, filename)
        pitcher_rows += the_odds.parse_json(filepath)
    
    players = {
        "batters": {
            "columns": ["Game", "batter_hits_runs_rbis", "Line", "Over", "Under"],
            "rows": batter_rows
        },
        "pitchers": {
            "columns": ["Game", "pitcher_strikeouts", "Line", "Over", "Under"],
            "rows": pitcher_rows
        }
    }    

    return render_template("mlb.html", players=players, email=session.get("email"))

@app.route("/teams")
def teams():
    return render_template('teams.html')

@app.route("/api/team", methods=["POST"])
def save_team():
    data = request.json
    team_name = data.get("teamName")

    if not team_name:
        return jsonify({"error": "Missing teamName"}), 400

    # Target user by email and update
    result = users_collection.update_one(
        {"email": "frenchfries11234@gmail.com"},
        {"$push": {"teams": team_name}}  # adds to array `teams`
    )

    if result.modified_count == 0:
        return jsonify({"error": "User not found or team not added"}), 404

    return jsonify({"message": "Team added to user"}), 200

# Run
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(debug=True, host="localhost", port=port)

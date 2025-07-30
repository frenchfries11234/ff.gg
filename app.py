from flask import Flask, render_template
import json
import the_odds
import os

app = Flask(__name__)

batters_dir = "data/batters"
pitchers_dir = "data/pitchers"

@app.route('/nfl')
def nfl():
    players = {
        "batters": {
            "columns": ["batter_hits_runs_rbis", "Line", "Over", "Under"],
            "rows": the_odds.parse_json("odds_cache.json")
        },
        "pitchers": {
            "columns": ["ERA", "SO", "W"],
            "rows": []
        }
    } 
    
    return render_template('nfl.html', players=players)

@app.route('/')
@app.route('/mlb')
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

    return render_template("mlb.html", players=players)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))  # default fallback
    app.run(host="0.0.0.0", port=port)
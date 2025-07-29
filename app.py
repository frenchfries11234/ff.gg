from flask import Flask, render_template
import json
import the_odds

app = Flask(__name__)



@app.route('/nfl')
def nfl():
    return render_template('nfl.html', players=players)

@app.route('/')
@app.route('/mlb')
def mlb():
    with open("odds_cache.json", "r") as f:
        odds_data = json.load(f)

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

    return render_template("mlb.html", players=players)

if __name__ == '__main__':
    app.run(debug=True)
from flask import Flask, render_template

app = Flask(__name__)

players = {
    "batters": {
        "columns": ["AVG", "HR", "RBI"],
        "rows": [
            {"name": "Aaron Judge", "stats": [0.321, 30, 70]},
            {"name": "Juan Soto", "stats": [0.298, 25, 62]},
        ]
    },
    "pitchers": {
        "columns": ["ERA", "SO", "W"],
        "rows": [
            {"name": "Gerrit Cole", "stats": [2.45, 110, 10]},
            {"name": "Blake Snell", "stats": [2.90, 97, 8]},
        ]
    }
}


@app.route('/nfl')
def nfl():
    return render_template('nfl.html', players=players)

@app.route('/')
@app.route('/mlb')
def mlb():
    
    return render_template("mlb.html", players=players)

if __name__ == '__main__':
    app.run(debug=True)
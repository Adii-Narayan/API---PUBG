import requests
import sqlite3
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
socketio = SocketIO(app)  # Initialize SocketIO
app.config['JWT_SECRET_KEY'] = 'your_jwt_secret_key'  # Change this to a random secret key
jwt = JWTManager(app)

# Function to initialize the database
def init_db():
    with sqlite3.connect('tournaments.db') as conn:
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS pubg_matches")
        cursor.execute("DROP TABLE IF EXISTS wagers")  # Drop wagers table if it exists
        cursor.execute("DROP TABLE IF EXISTS users")  # Drop users table if it exists
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS pubg_matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id TEXT,
            mode TEXT,
            map TEXT,
            created_at TEXT,
            rank INTEGER,
            rp REAL,
            kill_ratio REAL
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS wagers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            match_id TEXT,
            outcome TEXT,
            stake REAL,
            status TEXT,
            created_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)  -- Assumes a users table exists
        )''')
        conn.commit()

# Function to save PUBG match data to the database
def save_to_db(matches):
    with sqlite3.connect('tournaments.db') as conn:
        cursor = conn.cursor()
        for match in matches:
            cursor.execute('''INSERT INTO pubg_matches (match_id, mode, map, created_at, rank, rp, kill_ratio)
                              VALUES (?, ?, ?, ?, ?, ?, ?)''',
                           (match['id'], match.get('mode'), match.get('map'), match.get('created_at'),
                            match.get('rank'), match.get('rp'), match.get('kill_ratio')))
        conn.commit()

# Function to fetch match data using username
def fetch_player_matches(username):
    player_id_url = f"https://api.pubg.com/shards/steam/players?filter[playerNames]={username}"
    headers = {
        "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJqdGkiOiJkYTMxMzVhMC1iNWY3LTAxM2QtZGMwZS0wYWY2MzhlNGMzOTIiLCJpc3MiOiJnYW1lbG9ja2VyIiwiaWF0IjoxNzM3MDA0OTcwLCJwdWIiOiJibHVlaG9sZSIsInRpdGxlIjoicHViZyIsImFwcCI6ImNhdG9mZndlYjMifQ.m-Mk0Ln1RMNQcr8kU_P2lr7gHIyRc8z90bzRSXGcU-4",  # Replace with your actual API key
        "Accept": "application/vnd.api+json"
    }

    try:
        response = requests.get(player_id_url, headers=headers)
        if response.status_code != 200:
            print(f"Error fetching player data: {response.text}")
            return None

        player_data = response.json()
        if not player_data.get("data"):
            print("No player found for the given username.")
            return None

        player = player_data["data"][0]
        matches = player.get("relationships", {}).get("matches", {}).get("data", [])
        match_details = []

        for match in matches:
            match_id = match["id"]
            match_url = f"https://api.pubg.com/shards/steam/matches/{match_id}"
            match_response = requests.get(match_url, headers=headers)

            if match_response.status_code == 200:
                match_data = match_response.json()
                attributes = match_data.get("data", {}).get("attributes", {})
                included = match_data.get("included", [])
                
                rank = None
                rp = None
                kill_ratio = None
                
                for item in included:
                    if item.get("type") == "participant":
                        stats = item.get("attributes", {}).get("stats", {})
                        rank = stats.get("winPlace")
                        rp = stats.get("rankPoints")
                        kills = stats.get("kills", 0)
                        damage_dealt = stats.get("damageDealt", 1)
                        kill_ratio = kills / (damage_dealt / 100) if damage_dealt > 0 else 0
                        break
                
                match_details.append({
                    "id": match_id,
                    "mode": attributes.get("gameMode"),
                    "map": attributes.get("mapName"),
                    "rank": rank,
                    "rp": rp,
                    "kill_ratio": kill_ratio,
                    "created_at": attributes.get("createdAt")
                })

        return match_details
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

# Route for the home page
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/display', methods=['GET'])
def display():
    username = request.args.get('username')
    matches = fetch_player_matches(username)

    if matches:
        save_to_db(matches)
        emit_match_updates(matches)  # Emit real-time match updates
        return render_template('display.html', matches=matches, username=username)
    else:
        return render_template('display.html', matches=[], username=username)

# P2P Wagering Functionality
@app.route('/create_wager', methods=['POST'])
@jwt_required()
def create_wager():
    user_id = get_jwt_identity()  # Get the current user's identity (user ID)
    match_id = request.form.get('match_id')
    outcome = request.form.get('outcome')
    stake = float(request.form.get('stake'))

    with sqlite3.connect('tournaments.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO wagers (user_id, match_id, outcome, stake, status, created_at)
                          VALUES (?, ?, ?, ?, ?, ?)''',
                       (user_id, match_id, outcome, stake, 'open', datetime.utcnow()))
        conn.commit()

    return {'status': 'success', 'message': 'Wager created successfully!'}

@app.route('/get_wagers', methods=['GET'])
def get_wagers():
    with sqlite3.connect('tournaments.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM wagers WHERE status = "open"')
        open_wagers = cursor.fetchall()
    
    wagers_list = []
    for wager in open_wagers:
        wagers_list.append({
            'id': wager[0],
            'user_id': wager[1],
            'match_id': wager[2],
            'outcome': wager[3],
            'stake': wager[4],
            'status': wager[5],
            'created_at': wager[6]
        })
    
    return {'wagers': wagers_list}

# Emit real-time match updates via WebSocket
def emit_match_updates(matches):
    socketio.emit('match_updates', {'matches': matches})

# WebSocket event to handle client connection
@socketio.on('connect')
def handle_connect():
    print('Client connected')

# WebSocket event to handle disconnection
@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

# Initialize the database and run the app
if __name__ == "__main__":
    init_db()
    socketio.run(app, debug=True)

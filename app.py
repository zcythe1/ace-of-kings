from flask import Flask, request, redirect, session, render_template_string
from flask_socketio import SocketIO, join_room, emit
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
import uuid
import random
import string

app = Flask(__name__)
app.secret_key = "SUPER_SECRET_KEY_CHANGE_THIS"
socketio = SocketIO(app, cors_allowed_origins="*")

serializer = URLSafeTimedSerializer(app.secret_key)

ROLES = ["Oracle", "Witch", "Werewolf", "Queen", "Jester", "Knight", "Horse"]
MAX_PLAYERS = len(ROLES)

valid_product_codes = {
    "order-0001": {"used": False}
}
active_games = {}

def generate_game_code(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def start_game(game_code):
    """Start the game: assign roles and notify all players."""
    if game_code not in active_games:
        return
    
    game = active_games[game_code]
    game["state"] = "started"
    
    players = game["players"]
    available_roles = ROLES[:len(players)]
    random.shuffle(available_roles)
    
    roles_assigned = {}
    for i, player in enumerate(players):
        role = available_roles[i]
        player["role"] = role
        roles_assigned[player["sid"]] = role
    
    game["roles_assigned"] = roles_assigned
    
    socketio.emit("game_started", {
        "game_code": game_code,
        "roles": roles_assigned
    }, room=game_code)

@app.route("/play")
def play():
    token = request.args.get("token")

    if not token:
        return "Invalid access."

    try:
        product_id = serializer.loads(token, max_age=60*60*24*365)
    except SignatureExpired:
        return "QR code expired."
    except BadSignature:
        return "Invalid QR code."

    if product_id not in valid_product_codes:
        return "Product not recognized."

    if valid_product_codes[product_id]["used"]:
        return "This code has already been used."

    valid_product_codes[product_id]["used"] = True

    session["product_id"] = product_id

    return redirect("/host")

@app.route("/host")
def host():
    if "product_id" not in session:
        return "Access denied."

    game_code = generate_game_code()
    active_games[game_code] = {
        "host_sid": None,
        "players": [],
        "state": "waiting",
        "roles_assigned": {}
    }
    session["game_code"] = game_code

    return render_template_string("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Host</title>
            <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
        </head>
        <body>
            <div id="waiting-phase">
                <h1>You're the host</h1>
                <h2>Game code: <strong id="game-code">{{code}}</strong></h2>
                <p>Max players: {{max_players}}</p>
                <h3>Players joined:</h3>
                <ul id="player-list">
                    <li><em>Waiting for players...</em></li>
                </ul>
                <button id="start-btn" onclick="startGame()">Start Game</button>
            </div>
            <div id="started-phase" style="display:none;">
                <h1>Game Started!</h1>
            </div>
            <script>
                const socket = io();
                const gameCode = "{{code}}";
                const maxPlayers = {{max_players}};
                
                socket.emit("host_join", {game_code: gameCode});
                
                socket.on("player_joined", (data) => {
                    const playerList = document.getElementById("player-list");
                    if (playerList.querySelector("em")) {
                        playerList.innerHTML = "";
                    }
                    const li = document.createElement("li");
                    li.textContent = data.player_name;
                    playerList.appendChild(li);
                    
                    // Auto-start if max players reached
                    if (data.player_count >= maxPlayers) {
                        startGame();
                    }
                });
                
                socket.on("game_started", (data) => {
                    document.getElementById("waiting-phase").style.display = "none";
                    document.getElementById("started-phase").style.display = "block";
                    document.getElementById("game-code").style.display = "none";
                });
                
                function startGame() {
                    socket.emit("start_game", {game_code: gameCode});
                }
            </script>
        </body>
        </html>
    """, code=game_code, max_players=MAX_PLAYERS)

@app.route("/join", methods=["GET", "POST"])
def join():
    if request.method == "POST":
        code = request.form.get("code")
        player_name = request.form.get("name")

        if code in active_games:
            session["game_code"] = code
            session["player_name"] = player_name
            return render_template_string("""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Player</title>
                    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
                </head>
                <body>
                    <div id="waiting-phase">
                        <h1>You're a player</h1>
                        <h2 id="game-code-display">Joined game: <strong>{{code}}</strong></h2>
                        <p>Player name: <strong>{{name}}</strong></p>
                    </div>
                    <div id="started-phase" style="display:none;">
                        <h1>Your Role</h1>
                        <h2 id="role-display"></h2>
                    </div>
                    <script>
                        const socket = io();
                        const gameCode = "{{code}}";
                        const playerName = "{{name}}";
                        
                        socket.emit("player_join", {game_code: gameCode, player_name: playerName});
                        
                        socket.on("game_started", (data) => {
                            document.getElementById("waiting-phase").style.display = "none";
                            document.getElementById("started-phase").style.display = "block";
                            document.getElementById("game-code-display").style.display = "none";
                            
                            // Get this player's role
                            const yourRole = data.roles[socket.id] || "Unknown";
                            document.getElementById("role-display").textContent = yourRole;
                        });
                    </script>
                </body>
                </html>
            """, code=code, name=player_name)
        else:
            return "Invalid game code."

    return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Join Game</title>
        </head>
        <body>
            <h1>Join a Game</h1>
            <form method="POST">
                <label>Player Name: <input name="name" required></label><br><br>
                <label>Game Code: <input name="code" required></label><br><br>
                <button type="submit">Join</button>
            </form>
        </body>
        </html>
    """

@socketio.on("connect")
def handle_connect():
    print("Client connected")

@socketio.on("host_join")
def handle_host_join(data):
    game_code = data.get("game_code")
    if game_code in active_games:
        active_games[game_code]["host_sid"] = request.sid
        join_room(game_code)
        print(f"Host {request.sid} joined game {game_code}")

@socketio.on("player_join")
def handle_player_join(data):
    game_code = data.get("game_code")
    player_name = data.get("player_name")
    
    if game_code in active_games:
        player = {"name": player_name, "sid": request.sid, "role": None}
        active_games[game_code]["players"].append(player)
        join_room(game_code)
        
        emit("player_joined", {
            "player_name": player_name,
            "player_count": len(active_games[game_code]["players"])
        }, room=game_code)
        print(f"Player {player_name} ({request.sid}) joined game {game_code}")

@socketio.on("start_game")
def handle_start_game(data):
    game_code = data.get("game_code")
    start_game(game_code)
    print(f"Game {game_code} started")


if __name__ == "__main__":
    socketio.run(app, debug=True)
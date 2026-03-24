from flask import Flask, request, redirect, session, render_template
from flask_socketio import SocketIO, join_room, emit
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
import random
import string
from werkzeug.security import check_password_hash
import threading
import product_codes_dict


app = Flask(__name__)
app.secret_key = "youngenterprise"
socketio = SocketIO(app, cors_allowed_origins="*")

serializer = URLSafeTimedSerializer(app.secret_key)

ADMIN_PASSWORD_HASH = "scrypt:32768:8:1$6jy3oGhWeTkcPgnk$24daa97b98a863051d0872bd197a897a1db1cdff410d3ea08381994a29c463d7e320548f5546ff3da6de41e779e02635762afa946f7fc4962a5feae6aef6e668"

ROLES = ["Oracle", "Ogre", "Witch", "Werewolf", "Queen", "Jester", "Knight", "Horse"]
MAX_PLAYERS = len(ROLES)

COURTS = ["Queen", "Jester", "Knight", "Horse"]
MONSTERS = ["Oracle", "Ogre", "Witch", "Werewolf"]

FATE_LINE_LENGTH = 5

valid_product_codes = product_codes_dict.valid_product_codes
active_games = {}

def generate_game_code(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def create_deck():
    deck = []
    for _ in range(6): deck.append({"type": "number", "value": 1, "label": "1"})
    for _ in range(5): deck.append({"type": "number", "value": 2, "label": "2"})
    for _ in range(5): deck.append({"type": "number", "value": 3, "label": "3"})
    for _ in range(4): deck.append({"type": "number", "value": 4, "label": "4"})
    for _ in range(4): deck.append({"type": "number", "value": 5, "label": "5/0", "choice": True})
    for _ in range(3): deck.append({"type": "special", "action": "plus1", "label": "+1"})
    for _ in range(3): deck.append({"type": "special", "action": "plus2", "label": "+2"})
    for _ in range(2): deck.append({"type": "special", "action": "barter", "label": "Forced Barter"})
    for _ in range(3): deck.append({"type": "special", "action": "naysire", "label": "Nay Sire"})
    for _ in range(2): deck.append({"type": "special", "action": "castanew", "label": "Cast Anew"})
    for _ in range(2): deck.append({"type": "special", "action": "courts", "label": "Courts & Monsters"})
    for _ in range(2): deck.append({"type": "special", "action": "clockwork", "label": "Clock Work"})
    for _ in range(2): deck.append({"type": "special", "action": "counterturn", "label": "Counter Turn"})
    for _ in range(3): deck.append({"type": "special", "action": "skip", "label": "Skipping Stones"})
    for _ in range(2): deck.append({"type": "special", "action": "replace", "label": "Replace"})
    for _ in range(2): deck.append({"type": "special", "action": "rearrange", "label": "Rearrange"})
    random.shuffle(deck)
    return deck

def deal_cards(deck, num_players, cards_per_player=7):
    hands = []
    for i in range(num_players):
        hands.append(deck[i*cards_per_player:(i+1)*cards_per_player])
    remaining = deck[num_players*cards_per_player:]
    return hands, remaining

def get_team(role):
    if role in COURTS:
        return "courts"
    return "monsters"

def get_player_by_sid(game, sid):
    for p in game["players"]:
        if p["sid"] == sid:
            return p
    return None

def get_player_index(game, sid):
    for i, p in enumerate(game["players"]):
        if p["sid"] == sid:
            return i
    return -1

def next_player_index(game, current_idx=None):
    if current_idx is None:
        current_idx = game["current_player_idx"]
    n = len(game["players"])
    direction = game["direction"]
    skips = game.get("skip_next", 0)
    idx = (current_idx + direction * (1 + skips)) % n
    game["skip_next"] = 0
    return idx

def broadcast_game_state(game_code):
    game = active_games.get(game_code)
    if not game:
        return
    
    public_state = {
        "running_total": game["running_total"],
        "current_player_idx": game["current_player_idx"],
        "direction": game["direction"],
        "players": [
            {
                "name": p["name"],
                "role": p["role"],
                "team": get_team(p["role"]),
                "card_count": len(p["hand"]),
                "sid": p["sid"]
            }
            for p in game["players"]
        ],
        "fate_points": game["fate_points"],
        "fate_line": FATE_LINE_LENGTH,
        "round": game["round"],
        "log": game["log"][-5:],
        "state": game["state"],
        "pending_action": game.get("pending_action"),
        "blocked_players": game.get("blocked_players", []),
        "pickup_next": game.get("pickup_next", 0),
        "winner_team": game.get("winner_team")
    }
    
    for p in game["players"]:
        socketio.emit("game_state", {
            **public_state,
            "your_sid": p["sid"],
            "your_hand": p["hand"],
            "your_role": p["role"],
            "your_team": get_team(p["role"])
        }, room=p["sid"])
    
    socketio.emit("game_state", {
        **public_state,
        "is_host": True
    }, room=game["host_sid"])

def add_log(game, message):
    game["log"].append(message)

def start_new_round(game_code):
    game = active_games[game_code]
    deck = create_deck()
    n = len(game["players"])
    hands, remaining = deal_cards(deck, n)
    
    for i, p in enumerate(game["players"]):
        p["hand"] = hands[i]
    
    game["deck"] = remaining
    game["running_total"] = 0
    game["direction"] = 1
    game["skip_next"] = 0
    game["pickup_next"] = 0
    game["blocked_players"] = []
    game["pending_action"] = None
    game["current_player_idx"] = (game.get("current_player_idx", -1) + 1) % n
    game["log"] = [f"Round {game['round']} begins!"]
    game["state"] = "playing"

def check_round_end(game_code, loser_sid=None, winner_team=None):
    game = active_games[game_code]
    
    if loser_sid:
        loser = get_player_by_sid(game, loser_sid)
        losing_team = get_team(loser["role"])
        winning_team = "courts" if losing_team == "monsters" else "monsters"
        add_log(game, f"💥 {loser['name']} busted! {winning_team.title()} win the round!")
    elif winner_team:
        winning_team = winner_team
        add_log(game, f"🏆 {winning_team.title()} win the round!")
    else:
        return
    
    if winning_team not in game["fate_points"]:
        game["fate_points"][winning_team] = 0
    game["fate_points"][winning_team] += 1
    
    add_log(game, f"⭐ {winning_team.title()} now have {game['fate_points'][winning_team]} fate points!")
    
    if game["fate_points"][winning_team] >= FATE_LINE_LENGTH:
        game["state"] = "game_over"
        game["winner_team"] = winning_team
        add_log(game, f"🎉 {winning_team.title()} win the game!")
        broadcast_game_state(game_code)
        return
    
    game["round"] += 1
    game["state"] = "round_end"
    broadcast_game_state(game_code)
    
    def next_round():
        socketio.sleep(3)
        start_new_round(game_code)
        broadcast_game_state(game_code)
    
    socketio.start_background_task(next_round)

def start_game(game_code):
    if game_code not in active_games:
        return
    
    game = active_games[game_code]
    game["state"] = "started"
    
    players = game["players"]
    n = len(players)
    courts_pool = COURTS.copy()
    monsters_pool = MONSTERS.copy()
    random.shuffle(courts_pool)
    random.shuffle(monsters_pool)

    half = n // 2
    courts_count = half
    monsters_count = n - half

    available_roles = courts_pool[:courts_count] + monsters_pool[:monsters_count]
    random.shuffle(available_roles)
    
    for i, player in enumerate(players):
        player["role"] = available_roles[i]
    
    game["fate_points"] = {"courts": 0, "monsters": 0}
    game["round"] = 1
    game["log"] = []
    game["direction"] = 1
    game["skip_next"] = 0
    game["pickup_next"] = 0
    game["blocked_players"] = []
    game["pending_action"] = None
    game["current_player_idx"] = 0
    
    deck = create_deck()
    hands, remaining = deal_cards(deck, n)
    for i, player in enumerate(players):
        player["hand"] = hands[i]
    game["deck"] = remaining
    game["running_total"] = 0
    game["state"] = "playing"
    
    add_log(game, "Game started! Good luck to all players.")

    for p in players:
        socketio.emit("role_assigned", {
            "role": p["role"],
            "team": get_team(p["role"])
        }, room=p["sid"])

    broadcast_game_state(game_code)

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
        "roles_assigned": {},
        "fate_points": {},
        "round": 1,
        "log": [],
        "direction": 1,
        "skip_next": 0,
        "pickup_next": 0,
        "blocked_players": [],
        "pending_action": None,
        "current_player_idx": 0,
        "deck": [],
        "running_total": 0
    }
    session["game_code"] = game_code
    return render_template("host.html", code=game_code, max_players=MAX_PLAYERS)

@app.route("/join", methods=["GET", "POST"])
def join():
    if request.method == "POST":
        code = request.form.get("code", "").upper()
        player_name = request.form.get("name", "").strip()
        if code in active_games and active_games[code]["state"] == "waiting":
            session["game_code"] = code
            session["player_name"] = player_name
            return render_template("player.html", code=code, name=player_name)
        else:
            return render_template("join.html", error="Invalid or already started game code.")
    return render_template("join.html", error="")

@app.route("/", methods=["GET", "POST"])
@app.route("/", methods=["GET", "POST"])
def index():
    error = ""
    if request.method == "POST":
        entered_key = request.form.get("key", "").strip().upper()
        matched_id = None
        for product_id, data in valid_product_codes.items():
            if data.get("key", "").upper() == entered_key:
                matched_id = product_id
                break
        if not matched_id:
            error = "Key not recognised."
        else:
            session["product_id"] = matched_id
            return redirect("/host")
    return render_template("index.html", error=error)


@socketio.on("connect")
def handle_connect():
    pass

@socketio.on("nay_sire_response")
def handle_nay_sire_response(data):
    game = active_games.get(data.get("game_code"))
    if not game or not game.get("pending_action"):
        return
    pa = game["pending_action"]
    game["pending_action"] = None

    if data.get("blocked"):
        target = get_player_by_sid(game, pa["target_sid"])
        for i, c in enumerate(target["hand"]):
            if c.get("action") == "naysire":
                target["hand"].pop(i)
                break
        add_log(game, f"🛡 {pa['target_name']} blocked {pa['card_label']} with Nay Sire!")
    else:
        next_idx = resolve_blockable_action(pa["action"], pa["acting_player_idx"], data.get("game_code"))
        game["current_player_idx"] = next_idx

    broadcast_game_state(data.get("game_code"))

@socketio.on("host_join")
def handle_host_join(data):
    game_code = data.get("game_code")
    if game_code in active_games:
        active_games[game_code]["host_sid"] = request.sid
        join_room(game_code)
        join_room(request.sid)

@socketio.on("player_join")
def handle_player_join(data):
    game_code = data.get("game_code")
    player_name = data.get("player_name")
    if game_code in active_games:
        game = active_games[game_code]
        if len(game["players"]) >= MAX_PLAYERS:
            emit("error", {"message": "Game is full"})
            return
        player = {"name": player_name, "sid": request.sid, "role": None, "hand": []}
        game["players"].append(player)
        join_room(game_code)
        join_room(request.sid)
        emit("player_joined", {
            "player_name": player_name,
            "player_count": len(game["players"])
        }, room=game_code)
        if len(game["players"]) >= MAX_PLAYERS:
            start_game(game_code)

@socketio.on("start_game")
def handle_start_game(data):
    game_code = data.get("game_code")
    game = active_games.get(game_code)
    if game and game["host_sid"] == request.sid:
        if len(game["players"]) >= 2:
            start_game(game_code)
        else:
            emit("error", {"message": "Need at least 2 players"})

BLOCKABLE_ACTIONS = {"plus1", "plus2", "skip", "counterturn", "barter"}

def resolve_blockable_action(action, player_idx, game_code):
    game = active_games[game_code]
    player = game["players"][player_idx]
    next_idx = next_player_index(game, player_idx)
    next_player = game["players"][next_idx]

    if action == "plus1":
        game["pickup_next"] = 1
    elif action == "plus2":
        game["pickup_next"] = 2
    elif action == "skip":
        add_log(game, f"⏭ {next_player['name']} is skipped!")
        game["skip_next"] = 1
        next_idx = next_player_index(game, player_idx)
    elif action == "counterturn":
        game["direction"] *= -1
        add_log(game, f"🔄 Order reversed!")
        next_idx = next_player_index(game, player_idx)
    elif action == "barter":
        if player["hand"] and next_player["hand"]:
            give_card = player["hand"].pop(0)
            take_card = next_player["hand"].pop(random.randint(0, len(next_player["hand"]) - 1))
            player["hand"].append(take_card)
            next_player["hand"].append(give_card)
            add_log(game, f"🔀 {player['name']} bartered with {next_player['name']}!")
    return next_idx

@socketio.on("play_card")
def handle_play_card(data):
    game_code = data.get("game_code")
    card_idx = data.get("card_idx")
    choice = data.get("choice")
    target_sid = data.get("target_sid")
    
    game = active_games.get(game_code)
    if not game or game["state"] != "playing":
        return
    
    player_idx = get_player_index(game, request.sid)
    if player_idx != game["current_player_idx"]:
        emit("error", {"message": "Not your turn"})
        return
    
    player = game["players"][player_idx]
    
    if card_idx < 0 or card_idx >= len(player["hand"]):
        return

    if request.sid in game.get("blocked_players", []):
        game["blocked_players"].remove(request.sid)
        add_log(game, f"🚫 {player['name']} is blocked and skips their turn!")
        game["current_player_idx"] = next_player_index(game)
        broadcast_game_state(game_code)
        return
    
    pickup = game.get("pickup_next", 0)
    if pickup > 0:
        game["pickup_next"] = 0
        deck = game["deck"]
        for _ in range(pickup):
            if deck:
                player["hand"].append(deck.pop(0))
        add_log(game, f"📥 {player['name']} picks up {pickup} card(s)!")
        game["current_player_idx"] = next_player_index(game)
        broadcast_game_state(game_code)
        return
    
    card = player["hand"].pop(card_idx)
    n = len(game["players"])
    next_idx = next_player_index(game)
    next_player = game["players"][next_idx]
    
    if card["type"] == "number":
        val = card["value"]
        if card.get("choice"):
            val = choice if choice in [0, 5] else 5
        
        game["running_total"] += val
        add_log(game, f"🃏 {player['name']} plays {card['label']} → Total: {game['running_total']}")
        
        if game["running_total"] > 13:
            add_log(game, f"💥 Total exceeded 13!")
            game["state"] = "round_end"
            broadcast_game_state(game_code)
            check_round_end(game_code, loser_sid=request.sid)
            return
    
    elif card["type"] == "special":
        action = card["action"]
        add_log(game, f"✨ {player['name']} plays {card['label']}!")

        if action in BLOCKABLE_ACTIONS:
            has_nay = any(c.get("action") == "naysire" for c in next_player["hand"])
            if has_nay:
                game["pending_action"] = {
                    "type": "nay_sire_check",
                    "action": action,
                    "card_label": card["label"],
                    "target_name": next_player["name"],
                    "target_sid": next_player["sid"],
                    "acting_player_idx": player_idx
                }
                game["current_player_idx"] = next_idx
                broadcast_game_state(game_code)
                return
            else:
                next_idx = resolve_blockable_action(action, player_idx, game_code)

        elif action == "clockwork":
            game["running_total"] = 0
            add_log(game, f"⏰ Clock Work! Total reset to 0.")

        elif action == "castanew":
            all_cards = []
            for p in game["players"]:
                all_cards.extend(p["hand"])
            random.shuffle(all_cards)
            per = len(all_cards) // n
            for i, p in enumerate(game["players"]):
                p["hand"] = all_cards[i*per:(i+1)*per]
            remainder = all_cards[n*per:]
            game["deck"] = remainder + game["deck"]
            add_log(game, f"🌀 Cast Anew! Cards redistributed.")

        elif action == "courts":
            handle_character_ability(game_code, player, player["role"], target_sid)
            game["current_player_idx"] = next_idx
            broadcast_game_state(game_code)
            return

        elif action == "naysire":
            add_log(game, f"🛡 {player['name']} holds Nay Sire — played proactively but no effect.")

        elif action == "replace":
            player_team = get_team(player["role"])
            teams_sorted = sorted(game["fate_points"].items(), key=lambda x: x[1], reverse=True)
            if teams_sorted and teams_sorted[0][1] > 0:
                losing_team = teams_sorted[0][0]
                game["fate_points"][losing_team] -= 1
                game["fate_points"][player_team] += 1
                add_log(game, f"🔄 Replace! {losing_team.title()} lost a fate point and {player_team.title()} gained one!")

        elif action == "rearrange":
            teams = list(game["fate_points"].keys())
            if len(teams) == 2:
                game["fate_points"][teams[0]], game["fate_points"][teams[1]] = \
                    game["fate_points"][teams[1]], game["fate_points"][teams[0]]
                add_log(game, f"🔀 Rearrange! Fate points swapped!")

    # Check if the player has emptied their hand (works for both number and special cards)
    if len(player["hand"]) == 0:
        add_log(game, f"✨ {player['name']} played all their cards!")
        game["state"] = "round_end"
        broadcast_game_state(game_code)
        check_round_end(game_code, winner_team=get_team(player["role"]))
        return
    
    game["current_player_idx"] = next_idx
    broadcast_game_state(game_code)

def handle_character_ability(game_code, player, role, target_sid=None):
    game = active_games[game_code]
    n = len(game["players"])
    player_idx = get_player_index(game, player["sid"])
    next_idx = (player_idx + game["direction"]) % n
    next_player = game["players"][next_idx]
    
    if role == "Queen":
        demanded = "plus1"
        taken = 0
        for offset in [1, 2]:
            target_idx = (player_idx + game["direction"] * offset) % n
            target = game["players"][target_idx]
            cards_to_take = [c for c in target["hand"] if c.get("action") == demanded or str(c.get("value")) == demanded]
            player["hand"].extend(cards_to_take)
            for c in cards_to_take:
                target["hand"].remove(c)
            taken += len(cards_to_take)
        add_log(game, f"👑 Queen's Royal Decree! Took {taken} card(s).")
    
    elif role == "Jester":
        hands = [p["hand"] for p in game["players"]]
        rotated = [hands[(i - game["direction"]) % n] for i in range(n)]
        for i, p in enumerate(game["players"]):
            p["hand"] = rotated[i]
        add_log(game, f"🃏 Jester's Chaos! All hands rotated!")
    
    elif role == "Knight":
        if target_sid:
            target_idx = get_player_index(game, target_sid)
            if target_idx >= 0:
                game["players"][player_idx], game["players"][target_idx] = \
                    game["players"][target_idx], game["players"][player_idx]
                game["current_player_idx"] = target_idx
                add_log(game, f"⚔️ Knight swapped seats with {game['players'][target_idx]['name']}!")
    
    elif role == "Horse":
        idx = player_idx
        for _ in range(n):
            idx = (idx + game["direction"]) % n
            if game["players"][idx]["role"] in COURTS and idx != player_idx:
                game["current_player_idx"] = idx
                add_log(game, f"🐴 Horse leaped to {game['players'][idx]['name']}!")
                return
    
    elif role == "Oracle":
        socketio.emit("oracle_peek", {
            "hand": next_player["hand"],
            "target_name": next_player["name"]
        }, room=player["sid"])
        add_log(game, f"🔮 Oracle peeks at {next_player['name']}'s hand!")
    
    elif role == "Ogre":
        blocked = 0
        for offset in [1, 2, 3, 4]:
            check_idx = (player_idx + game["direction"] * offset) % n
            check_player = game["players"][check_idx]
            if check_player["role"] in COURTS:
                if check_player["sid"] not in game["blocked_players"]:
                    game["blocked_players"].append(check_player["sid"])
                blocked += 1
                if blocked >= 2:
                    break
        add_log(game, f"👹 Ogre blocks next 2 court members!")
    
    elif role == "Witch":
        choice = random.choice([2, -2])
        game["running_total"] = max(0, game["running_total"] + choice)
        op = "+" if choice > 0 else ""
        add_log(game, f"🧙 Witch's Malediction! Total {op}{choice} → {game['running_total']}")
    
    elif role == "Werewolf":
        stolen = 0
        for _ in range(2):
            if next_player["hand"]:
                idx_steal = random.randint(0, len(next_player["hand"])-1)
                player["hand"].append(next_player["hand"].pop(idx_steal))
                stolen += 1
        add_log(game, f"🐺 Werewolf stole {stolen} card(s) from {next_player['name']}!")

@app.route("/host-dev", methods=["GET", "POST"])
def host_dev():
    if request.method == "POST":
        password = request.form.get("password", "")
        if check_password_hash(ADMIN_PASSWORD_HASH, password):
            session["product_id"] = "dev"
            valid_product_codes["dev"] = {"used": False}
            return redirect("/host")
        else:
            error = "Wrong password."
    else:
        error = ""
    
    return f"""
        <form method="POST">
            <input type="password" name="password" placeholder="Admin password" autofocus>
            <button type="submit">Enter</button>
            <p style="color:red">{error}</p>
        </form>
    """

if __name__ == "__main__":
    socketio.run(app, debug=True, host="0.0.0.0", port=5000)
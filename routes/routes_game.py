from flask import Blueprint, request, redirect, session, render_template
from itsdangerous import BadSignature, SignatureExpired

from utils.game_manager import *

game_bp = Blueprint('game', __name__)

@game_bp.route("/play")
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

@game_bp.route("/host")
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

@game_bp.route("/join", methods=["GET", "POST"])
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
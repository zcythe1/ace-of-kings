import random
import string

from config import *
from extensions.gamestorage import *
from extensions.general import *
from .gm_utils import *

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
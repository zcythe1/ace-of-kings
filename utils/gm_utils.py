# hold non import dependent utility functions for game_manager.py
from random import random
from string import ascii_uppercase, digits
from config import COURTS


def generate_game_code(length=6):
    return ''.join(random.choices(ascii_uppercase + digits, k=length))


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
        hands.append(deck[i * cards_per_player:(i + 1) * cards_per_player])
    remaining = deck[num_players * cards_per_player:]
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
from flask import request
from flask_socketio import join_room, emit

from utils.game_manager import *


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
                p["hand"] = all_cards[i * per:(i + 1) * per]
            remainder = all_cards[n * per:]
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
                add_log(game,
                        f"🔄 Replace! {losing_team.title()} lost a fate point and {player_team.title()} gained one!")

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
            cards_to_take = [c for c in target["hand"] if
                             c.get("action") == demanded or str(c.get("value")) == demanded]
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
                idx_steal = random.randint(0, len(next_player["hand"]) - 1)
                player["hand"].append(next_player["hand"].pop(idx_steal))
                stolen += 1
        add_log(game, f"🐺 Werewolf stole {stolen} card(s) from {next_player['name']}!")

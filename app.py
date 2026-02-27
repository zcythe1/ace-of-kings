from flask import Flask, request, redirect, session, render_template_string
from flask_socketio import SocketIO, join_room
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
import uuid
import random
import string

app = Flask(__name__)
app.secret_key = "SUPER_SECRET_KEY_CHANGE_THIS"
socketio = SocketIO(app)

serializer = URLSafeTimedSerializer(app.secret_key)

# Simulated database
valid_product_codes = {
    "test-product-001": {"used": False} #ADD VALID PRODUCT CODES HERE
}
active_games = {}


def generate_game_code(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

@app.route("/play")
def play():
    token = request.args.get("token")

    if not token:
        return "Invalid access."

    try:
        product_id = serializer.loads(token, max_age=60*60*24*365)  # 1 year expiry
    except SignatureExpired:
        return "QR code expired."
    except BadSignature:
        return "Invalid QR code."

    # Check product exists
    if product_id not in valid_product_codes:
        return "Product not recognized."

    # Optional: single use
    if valid_product_codes[product_id]["used"]:
        return "This code has already been used."

    # Mark used (optional, comment out if reusable)
    valid_product_codes[product_id]["used"] = True

    session["product_id"] = product_id

    return redirect("/host")

@app.route("/host")
def host():
    if "product_id" not in session:
        return "Access denied."

    game_code = generate_game_code()
    active_games[game_code] = {"host_sid": None, "players": []}

    return render_template_string("""
        <h1>You're the host</h1>
        <h2>Game code: {{code}}</h2>
    """, code=game_code)

@app.route("/join", methods=["GET", "POST"])
def join():
    if request.method == "POST":
        code = request.form.get("code")

        if code in active_games:
            return f"<h1>You're a player</h1><h2>Joined game {code}</h2>"
        else:
            return "Invalid game code."

    return """
        <form method="POST">
            Enter game code: <input name="code">
            <button type="submit">Join</button>
        </form>
    """

@socketio.on("connect")
def handle_connect():
    print("Client connected")


if __name__ == "__main__":
    socketio.run(app, debug=True)
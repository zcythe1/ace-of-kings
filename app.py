from flask import Flask, request, redirect, session, render_template
from flask_socketio import SocketIO, join_room, emit
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
import random
import string
from werkzeug.security import check_password_hash
from extensions import product_codes_dict
from extensions.general import *
from config import *
from routes.routes_dev import dev_bp
from routes.routes_game import game_bp
from routes.routes_main import main_bp
from ws import game_ws
from utils.game_manager import *


app = Flask(__name__)
app.secret_key = SECRET_KEY

socketio.init_app(app)

app.register_blueprint(game_bp)
app.register_blueprint(dev_bp)
app.register_blueprint(main_bp)

if __name__ == "__main__":
    socketio.run(app, debug=True, host="0.0.0.0", port=5000)
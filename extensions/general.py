from flask_socketio import SocketIO
from itsdangerous import URLSafeTimedSerializer
from config import SECRET_KEY

socketio = SocketIO(cors_allowed_origins="*")

serializer = URLSafeTimedSerializer(SECRET_KEY)
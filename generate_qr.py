from itsdangerous import URLSafeTimedSerializer

SECRET_KEY = "SUPER_SECRET_KEY_CHANGE_THIS"
serializer = URLSafeTimedSerializer(SECRET_KEY)

product_id = "test-product-001"
token = serializer.dumps(product_id)

input(f"http://localhost:5000/play?token={token}")
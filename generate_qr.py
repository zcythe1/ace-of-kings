from itsdangerous import URLSafeTimedSerializer
from PIL import Image, ImageDraw, ImageFont
import qrcode
import product_codes_dict

SECRET_KEY = "youngenterprise"
serializer = URLSafeTimedSerializer(SECRET_KEY)

product_codes_dict.generate_new_key()
product_ids = product_codes_dict.valid_product_codes
product_id = list(product_ids.keys())[-1]
label = product_ids[product_id]["key"]

token = serializer.dumps(product_id)
qr_img = qrcode.make(f"https://theaceous-stephine-hylozoic.ngrok-free.dev/play?token={token}").convert("RGB")

try:
    font = ImageFont.truetype("arial.ttf", 24)
except IOError:
    font = ImageFont.load_default()

dummy_draw = ImageDraw.Draw(qr_img)
bbox = dummy_draw.textbbox((0, 0), label, font=font)
text_w = bbox[2] - bbox[0]
text_h = bbox[3] - bbox[1]

padding = 20
qr_w, qr_h = qr_img.size

canvas = Image.new("RGB", (qr_w, qr_h + text_h + padding * 2), "white")
canvas.paste(qr_img, (0, 0))

draw = ImageDraw.Draw(canvas)
draw.text(((qr_w - text_w) // 2, qr_h + padding), label, fill="black", font=font)

canvas.save(f"qrcodes/{product_id}.png")
print(f"Saved qrcodes/{product_id}.png")
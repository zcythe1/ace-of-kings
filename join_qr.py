import qrcode
img = qrcode.make("https://theaceous-stephine-hylozoic.ngrok-free.dev/join")
type(img)  # qrcode.image.pil.PilImage
img.save("qrcodes/join.png")
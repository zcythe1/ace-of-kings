import qrcode
img = qrcode.make("https://game.aceofkings.space/join")
type(img)  # qrcode.image.pil.PilImage
img.save("qrcodes/join.png")
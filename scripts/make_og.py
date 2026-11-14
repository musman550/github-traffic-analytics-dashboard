"""Generate docs/assets/og-image.png (static brand card, contains no statistics)."""
from PIL import Image, ImageDraw, ImageFont
W, H = 1200, 630
im = Image.new("RGB", (W, H), "#0b1220")
d = ImageDraw.Draw(im)
for i in range(H):  # subtle vertical gradient
    c = int(18 + 22 * i / H)
    d.line([(0, i), (W, i)], fill=(8, c, 52 + int(40 * i / H)))
B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
R = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
d.rounded_rectangle([70, 70, 150, 150], radius=18, fill="#0b5fff")
d.line([(88, 124), (104, 104), (118, 116), (140, 88)], fill="white", width=8, joint="curve")
d.text((70, 210), "GitHub Traffic", font=ImageFont.truetype(B, 84), fill="white")
d.text((70, 305), "Analytics Dashboard", font=ImageFont.truetype(B, 84), fill="white")
d.text((70, 430), "Views, clones, referrers and stars with permanent", font=ImageFont.truetype(R, 36), fill="#b6c4dc")
d.text((70, 480), "daily history. Free, open source, no login.", font=ImageFont.truetype(R, 36), fill="#b6c4dc")
im.save("docs/assets/og-image.png", optimize=True)

"""Generate PNG icons for the web app manifest (run once, output is committed)."""
from PIL import Image, ImageDraw

def icon(size, pad=0.0, path=None):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    p = int(size * pad)
    d.rounded_rectangle([p, p, size - p, size - p], radius=int((size - 2 * p) * 0.22), fill="#0b5fff")
    s = size - 2 * p
    pts = [(p + s * .19, p + s * .69), (p + s * .375, p + s * .47), (p + s * .53, p + s * .6), (p + s * .81, p + s * .25)]
    d.line(pts, fill="white", width=max(2, int(s * .094)), joint="curve")
    im.save(path, optimize=True)

icon(192, 0, "docs/assets/icon-192.png")
icon(512, 0, "docs/assets/icon-512.png")
icon(512, 0.1, "docs/assets/icon-maskable-512.png")
icon(180, 0, "docs/assets/apple-touch-icon.png")

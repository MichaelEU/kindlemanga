"""Draws the app icon (a manga page with one panel zoomed out of it) into AppIcon.iconset."""
import os, sys
from PIL import Image, ImageDraw, ImageFilter

S = 1024
out = sys.argv[1] if len(sys.argv) > 1 else "AppIcon.iconset"
os.makedirs(out, exist_ok=True)

img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
# macOS icon body: rounded square, 824px inside a 1024 canvas
body, r, off = 824, 185, (S - 824) // 2
grad = Image.new("RGBA", (body, body))
g = ImageDraw.Draw(grad)
for y in range(body):
    t = y / body
    g.line([(0, y), (body, y)], fill=(int(40 + 30 * t), int(56 + 40 * t), int(110 + 70 * t), 255))
mask = Image.new("L", (body, body), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, body - 1, body - 1], r, fill=255)
shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
ImageDraw.Draw(shadow).rounded_rectangle([off, off + 14, off + body, off + body + 14], r, fill=(0, 0, 0, 90))
img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(18)))
img.paste(grad, (off, off), mask)

d = ImageDraw.Draw(img)
# the page
px0, py0, px1, py1 = 250, 205, 690, 820
d.rounded_rectangle([px0, py0, px1, py1], 18, fill=(250, 250, 247, 255))
ink, gap = (52, 56, 66, 255), 16
# panel layout: wide top panel, slanted middle pair, bottom panel
panels = [
    [(px0 + 28, py0 + 28), (px1 - 28, py0 + 28), (px1 - 28, py0 + 190), (px0 + 28, py0 + 190)],
    [(px0 + 28, py0 + 190 + gap), (px0 + 250, py0 + 190 + gap), (px0 + 210, py0 + 420), (px0 + 28, py0 + 420)],
    [(px0 + 250 + gap, py0 + 190 + gap), (px1 - 28, py0 + 190 + gap), (px1 - 28, py0 + 420), (px0 + 210 + gap, py0 + 420)],
    [(px0 + 28, py0 + 420 + gap), (px1 - 28, py0 + 420 + gap), (px1 - 28, py1 - 28), (px0 + 28, py1 - 28)],
]
for p in panels:
    d.polygon(p, outline=ink, width=9)
# speech-bubble hints
d.ellipse([px0 + 60, py0 + 60, px0 + 170, py0 + 140], outline=ink, width=6)
d.ellipse([px0 + 70, py0 + 470, px0 + 190, py0 + 555], outline=ink, width=6)

# the zoomed panel popping out, with an accent frame
zx0, zy0, zx1, zy1 = 470, 395, 830, 660
zshadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
ImageDraw.Draw(zshadow).rounded_rectangle([zx0, zy0 + 12, zx1, zy1 + 12], 22, fill=(0, 0, 0, 110))
img.alpha_composite(zshadow.filter(ImageFilter.GaussianBlur(16)))
d = ImageDraw.Draw(img)
d.rounded_rectangle([zx0, zy0, zx1, zy1], 22, fill=(255, 255, 255, 255), outline=(255, 149, 0, 255), width=14)
d.ellipse([zx0 + 40, zy0 + 40, zx0 + 200, zy0 + 150], outline=ink, width=8)
d.line([(zx0 + 110, zy0 + 150), (zx0 + 95, zy0 + 185)], fill=ink, width=8)
d.line([(zx0 + 230, zy1 - 40), (zx1 - 40, zy0 + 60)], fill=ink, width=8)
# zoom rays from the small panel to the big one
d.line([(px0 + 250 + gap + 6, py0 + 190 + gap + 6), (zx0 + 8, zy0 + 8)], fill=(255, 149, 0, 200), width=7)
d.line([(px1 - 34, py0 + 420 - 6), (zx0 + 8, zy1 - 8)], fill=(255, 149, 0, 200), width=7)

for size in (16, 32, 128, 256, 512):
    img.resize((size, size), Image.LANCZOS).save(f"{out}/icon_{size}x{size}.png")
    img.resize((size * 2, size * 2), Image.LANCZOS).save(f"{out}/icon_{size}x{size}@2x.png")

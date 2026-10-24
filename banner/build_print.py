"""Upscale the back-wall layout to a print file with sharp logo, QR code and type.

Usage:
    python3 banner/build_print.py <original-logo.png>

Reads banner/goodbye-coffee-back-wall-FINAL-layout.png (3230 px wide) and writes
banner/goodbye-coffee-back-wall-PRINT-120x40.png at 6000 px wide (50 ppi at 120").
The art is upscaled; the logo comes from the original logo file, the QR code is
redrawn pixel-exact, and all type is reset in Changa One.
"""
import sys
import cv2
import numpy as np
import zxingcpp
from PIL import Image, ImageDraw, ImageFont

HERE = sys.path[0]
OUT_W = 6000
BONE = (0xF2, 0xED, 0xE4)
BG = (6, 6, 6)  # flat background behind the center block
FONT = f"{HERE}/fonts/ChangaOne-Regular.ttf"

# Element boxes in layout (3230 px) coordinates: x0, y0, x1, y1.
LOGO = (805, 185, 2060, 622)
LOGO_CLEAR = (790, 165, 2075, 640)
CENTER = (760, 0, 2095, 1062)  # flat-black area between the left and right art
URL = (750, 830, 2500, 960)
HANDLE = (1290, 645, 1985, 768)
TAGLINE = (1000, 40, 1840, 130)
QR_LABEL = (2120, 45, 2565, 200)
QR_BOX = (2100, 220, 2582, 710)


def clear(img, box, s):
    x0, y0, x1, y1 = (int(v * s) for v in box)
    region = img[y0:y1, x0:x1]
    marks = (region.max(axis=2) > 20).astype(np.uint8)
    marks = cv2.dilate(marks, np.ones((15, 15), np.uint8)) > 0
    region[marks] = BG


def fit_text(d, text, box, s, max_size=600):
    x0, y0, x1, y1 = (int(v * s) for v in box)
    size = max_size
    while True:
        f = ImageFont.truetype(FONT, size)
        b = d.textbbox((0, 0), text, font=f)
        if b[2] - b[0] <= x1 - x0 and b[3] - b[1] <= y1 - y0:
            return f, b
        size -= 2


def draw_centered(d, text, box, s, f=None):
    if f is None:
        f, _ = fit_text(d, text, box, s)
    b = d.textbbox((0, 0), text, font=f)
    x0, y0, x1, y1 = (int(v * s) for v in box)
    d.text(((x0 + x1) // 2 - (b[2] - b[0]) // 2 - b[0], (y0 + y1) // 2 - (b[3] - b[1]) // 2 - b[1]), text, font=f, fill=BONE)


def main(logo_path):
    layout = cv2.imread(f"{HERE}/goodbye-coffee-back-wall-FINAL-layout.png")
    s = OUT_W / layout.shape[1]
    img = cv2.resize(layout, (OUT_W, round(layout.shape[0] * s)), interpolation=cv2.INTER_LANCZOS4)

    for box in (LOGO_CLEAR, URL, HANDLE, TAGLINE, QR_LABEL):
        clear(img, box, s)

    # Logo from the original file, fitted to the logo box.
    o = cv2.imread(logo_path)
    crop = o[110:580, 40:1740]
    ys, xs = np.where(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) > 60)
    logo = crop[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    x0, y0, x1, y1 = (int(v * s) for v in LOGO)
    k = min((x1 - x0) / logo.shape[1], (y1 - y0) / logo.shape[0])
    logo = cv2.resize(logo, (int(logo.shape[1] * k), int(logo.shape[0] * k)), interpolation=cv2.INTER_LANCZOS4)
    lx, ly = x0 + (x1 - x0 - logo.shape[1]) // 2, y0 + (y1 - y0 - logo.shape[0]) // 2
    a = np.clip((logo.max(axis=2).astype(np.float32) - 25) / 40, 0, 1)[..., None]
    roi = img[ly:ly + logo.shape[0], lx:lx + logo.shape[1]].astype(np.float32)
    img[ly:ly + logo.shape[0], lx:lx + logo.shape[1]] = (logo * a + roi * (1 - a)).astype(np.uint8)

    # Flatten leftover near-black smudges in the center block.
    for x0, y0, x1, y1 in (CENTER, (2090, 0, 2600, 215)):
        region = img[int(y0 * s):int(y1 * s), int(x0 * s):int(x1 * s)]
        region[region.max(axis=2) < 24] = BG

    # QR code, pixel-exact.
    x0, y0, x1, y1 = (int(v * s) for v in QR_BOX)
    img[y0:y1, x0:x1] = 255
    qr = cv2.imread(f"{HERE}/../qr/goodbyecoffee-ride-qr.png")
    q = min(x1 - x0, y1 - y0)
    qx, qy = x0 + (x1 - x0 - q) // 2, y0 + (y1 - y0 - q) // 2
    img[qy:qy + q, qx:qx + q] = cv2.resize(qr, (q, q), interpolation=cv2.INTER_AREA)

    im = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    d = ImageDraw.Draw(im)
    draw_centered(d, "GOODBYECOFFEE.COM", URL, s)
    draw_centered(d, "COFFEE FOR RIDERS", TAGLINE, s)
    draw_centered(d, "@goodbye_coffee_co", HANDLE, s)
    lx0, ly0, lx1, ly1 = QR_LABEL
    mid = (ly0 + ly1) / 2
    top, bottom = (lx0, ly0, lx1, mid - 6), (lx0, mid + 6, lx1, ly1)
    f = min((fit_text(d, t, b, s)[0] for t, b in (("PUT YOUR RIDE", top), ("ON OUR BAG", bottom))), key=lambda f: f.size)
    draw_centered(d, "PUT YOUR RIDE", top, s, f)
    draw_centered(d, "ON OUR BAG", bottom, s, f)

    out = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)
    path = f"{HERE}/goodbye-coffee-back-wall-PRINT-120x40.png"
    Image.fromarray(cv2.cvtColor(out, cv2.COLOR_BGR2RGB)).save(path, dpi=(50, 50))
    print(out.shape, "qr:", [r.text for r in zxingcpp.read_barcodes(out)])


if __name__ == "__main__":
    main(sys.argv[1])

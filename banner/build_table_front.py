"""Build the 60x18 Goodbye Coffee table-front banner with a Facebook QR code.

Usage:
    python3 banner/build_table_front.py <original-logo.png>
"""
import sys
import cv2
import numpy as np
import segno
import zxingcpp
from PIL import Image, ImageDraw, ImageFont

HERE = sys.path[0]
W, H = 3000, 900  # 60 x 18 in at 50 ppi
MARGIN = 150
TOP_ZONE = (60, 620)  # px; the bottom ~5.5" stays empty black
BG = (10, 10, 10)
BONE = (0xF2, 0xED, 0xE4)
FONT = f"{HERE}/fonts/ChangaOne-Regular.ttf"
FACEBOOK_URL = "https://www.facebook.com/goodbyecoffeeco"


def make_facebook_qr():
    q = segno.make(FACEBOOK_URL, error="q", micro=False)
    for ext, kw in (("svg", {}), ("pdf", {"scale": 20}), ("png", {"scale": 150})):
        q.save(f"{HERE}/../qr/goodbyecoffee-facebook-qr.{ext}", border=4, **kw)
    return Image.open(f"{HERE}/../qr/goodbyecoffee-facebook-qr.png").convert("RGB")


def load_logo(path):
    o = cv2.imread(path)
    crop = o[110:580, 40:1740]
    ys, xs = np.where(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) > 60)
    crop = crop[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))


def main(logo_path):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)

    # Everything sits in the top of the banner; people standing at the table block the bottom.
    zone_top, zone_bottom = TOP_ZONE
    zone_mid = (zone_top + zone_bottom) // 2

    # Facebook QR block on the right: label above, code below.
    qs = 400
    qr = make_facebook_qr().resize((qs, qs), Image.NEAREST)
    label_font = ImageFont.truetype(FONT, 56)
    labels = ["FOLLOW US", "ON FACEBOOK"]
    lbs = [d.textbbox((0, 0), t, font=label_font) for t in labels]
    line_h = max(b[3] - b[1] for b in lbs)
    block_h = 2 * line_h + 16 + 26 + qs
    qx = W - MARGIN - qs
    top = zone_top + (zone_bottom - zone_top - block_h) // 2
    for i, (t, b) in enumerate(zip(labels, lbs)):
        d.text((qx + qs // 2 - (b[2] - b[0]) // 2 - b[0], top + i * (line_h + 16) - b[1]), t, font=label_font, fill=BONE)
    im.paste(qr, (qx, top + 2 * line_h + 16 + 26))

    # Logo on the left.
    logo = load_logo(logo_path)
    lw = 1000
    logo = logo.resize((lw, int(logo.height * lw / logo.width)), Image.LANCZOS)
    mask = Image.fromarray(np.clip((np.array(logo).max(axis=2).astype(float) - 25) / 40 * 255, 0, 255).astype(np.uint8))
    im.paste(logo, (MARGIN, zone_mid - logo.height // 2), mask)

    # Divider, two-line tagline and a small website line, centered between logo and QR.
    left, right = MARGIN + lw + 70, qx - 90
    d.rectangle([left, zone_top + 40, left + 8, zone_bottom - 40], fill=BONE)
    lines = ["COFFEE FOR", "THE RIDE"]
    avail = right - (left + 8 + 70)
    size = 300
    while True:
        f = ImageFont.truetype(FONT, size)
        boxes = [d.textbbox((0, 0), t, font=f) for t in lines]
        if max(b[2] - b[0] for b in boxes) <= avail:
            break
        size -= 2
    url_font = ImageFont.truetype(FONT, 64)
    ub = d.textbbox((0, 0), "GOODBYECOFFEE.COM", font=url_font)
    gap, url_gap = 36, 44
    heights = [b[3] - b[1] for b in boxes]
    block = sum(heights) + gap + url_gap + (ub[3] - ub[1])
    y = zone_mid - block // 2
    cx = (left + 8 + 70 + right) // 2
    for t, b, h in zip(lines, boxes, heights):
        d.text((cx - (b[2] - b[0]) // 2 - b[0], y - b[1]), t, font=f, fill=BONE)
        y += h + gap
    y += url_gap - gap
    d.text((cx - (ub[2] - ub[0]) // 2 - ub[0], y - ub[1]), "GOODBYECOFFEE.COM", font=url_font, fill=BONE)

    path = f"{HERE}/goodbye-coffee-table-front-PRINT-60x18.png"
    im.save(path, dpi=(50, 50))
    out = cv2.imread(path)
    print("font", size, "cap in", round(heights[0] / H * 18, 1), "url in", round((ub[3] - ub[1]) / H * 18, 1),
          "qr in", round(qs / H * 18, 1), "decodes:", [r.text for r in zxingcpp.read_barcodes(out)])


if __name__ == "__main__":
    main(sys.argv[1])

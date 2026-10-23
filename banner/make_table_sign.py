"""Build the 11x17 Goodbye Coffee tabletop sign mockup.

Edit MENU below with real prices, then run:
    python3 banner/make_table_sign.py <original-logo.png>
"""
import sys
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

MENU = [
    ("SEND IT", "$__"),
    ("ANALOG", "$__"),
    ("OTB", "$__"),
    ("CANDY", "$__"),
    ("CUPS", "$__"),
]

W, H = 1650, 2550  # 11 x 17 in at 150 dpi
BLACK = (0x0A, 0x0A, 0x0A)
BONE = (0xF2, 0xED, 0xE4)
PINK = (0xFF, 0x00, 0x6E)
BLUE = (0x0B, 0x2A, 0x9E)
BLACK_FONT = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
BOLD_FONT = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"
HERE = sys.path[0]


def load_logo(path):
    o = cv2.imread(path)
    crop = o[110:580, 40:1740]
    ys, xs = np.where(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) > 60)
    crop = crop[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))


def centered(d, y, text, font, fill):
    b = d.textbbox((0, 0), text, font=font)
    d.text(((W - (b[2] - b[0])) // 2 - b[0], y - b[1]), text, font=font, fill=fill)
    return y + (b[3] - b[1])


def main(logo_path):
    im = Image.new("RGB", (W, H), BLACK)
    d = ImageDraw.Draw(im)

    logo = load_logo(logo_path)
    lw = 1100
    logo = logo.resize((lw, int(logo.height * lw / logo.width)), Image.LANCZOS)
    mask = logo.convert("L").point(lambda v: min(255, v * 3))
    im.paste(logo, ((W - lw) // 2, 90), mask)
    y = 90 + logo.height + 90

    y = centered(d, y, "FREE", ImageFont.truetype(BLACK_FONT, 200), PINK) + 25
    y = centered(d, y, "WATER BOTTLE", ImageFont.truetype(BLACK_FONT, 175), PINK) + 35
    y = centered(d, y, "with any bag of coffee", ImageFont.truetype(BOLD_FONT, 80), BONE) + 70

    d.rectangle([150, y, W - 150, y + 8], fill=BLUE)
    y += 8 + 70

    item_font = ImageFont.truetype(BLACK_FONT, 90)
    for name, price in MENU:
        b = d.textbbox((0, 0), name, font=item_font)
        pb = d.textbbox((0, 0), price, font=item_font)
        d.text((180, y - b[1]), name, font=item_font, fill=BONE)
        d.text((W - 180 - pb[2], y - pb[1]), price, font=item_font, fill=BONE)
        d.line([(180 + b[2] + 40, y + 60), (W - 180 - pb[2] - 40, y + 60)], fill=(90, 90, 90), width=4)
        y += 135

    y = centered(d, y, "CASH  ·  CARD  ·  TAP", ImageFont.truetype(BOLD_FONT, 70), BONE) + 60

    y = centered(d, y, "SCAN TO SHOP", ImageFont.truetype(BLACK_FONT, 80), BONE) + 30
    qs = 380
    qr = Image.open(f"{HERE}/../qr/goodbyecoffee-qr.png").convert("RGB").resize((qs, qs), Image.NEAREST)
    im.paste(qr, ((W - qs) // 2, y))
    y += qs + 30
    centered(d, y, "@goodbye_coffee_co", ImageFont.truetype(BOLD_FONT, 70), BONE)

    im.save(f"{HERE}/goodbye-coffee-table-sign-mockup.png")


if __name__ == "__main__":
    main(sys.argv[1])

"""Build the 120x40 Goodbye Coffee back-wall banner layout.

Usage:
    python3 banner/build_back_wall.py <designer-proof.png> <rider-photo-clean.jpg> <rider-mask.png> <fonts-dir> [ink|photo] [out-name]

Starts from the designer's proof (art, logo, URL, handle), then:
  - removes the drawn-on grommets (the printer adds real ones)
  - swaps the AI rider for the real race photo, inked, jersey kept royal blue
  - puts the real /ride QR code in the white box
  - adds the "COFFEE FOR RIDERS" line and the On the Bag call to action
"""
import os
import sys
import cv2
import numpy as np
import zxingcpp
from PIL import Image, ImageDraw, ImageFont

HERE = sys.path[0]
BONE = (0xF2, 0xED, 0xE4)
BLACK_BGR = (10, 10, 10)
ROYAL_BGR = np.array([158, 42, 11], np.float32)
BG = (6, 6, 6)  # flat background behind the center block

SOCIAL_ROW = (645, 768)
SOCIAL_CENTER_X = 1420
SOCIAL_TEXT = "GOODBYE COFFEE CO"
SOCIAL_CAP = 60  # px cap height in the 3230-wide layout (about 2.3" at 40" tall)
ICON_SCALE = 0.72
ICON_SRC_WIDTHS = (106, 102, 124)  # Instagram, Facebook, YouTube in the upscaled proof
ICON_GAP, TEXT_GAP = 33, 45


def social_layout(fonts, icon_widths):
    """Icon x positions and the text box (x0, y0, x1, y1) for the social row."""
    f = ImageFont.truetype(f"{fonts}/ChangaOne-Regular.ttf", 100)
    b = f.getbbox(SOCIAL_TEXT)
    text_w = int((b[2] - b[0]) * SOCIAL_CAP / (b[3] - b[1]))
    total = sum(icon_widths) + ICON_GAP * (len(icon_widths) - 1) + TEXT_GAP + text_w
    x = SOCIAL_CENTER_X - total // 2
    xs = []
    for w in icon_widths:
        xs.append(x)
        x += w + ICON_GAP
    x += TEXT_GAP - ICON_GAP
    mid = sum(SOCIAL_ROW) // 2
    return xs, (x, mid - SOCIAL_CAP // 2, x + text_w, mid + SOCIAL_CAP // 2)


def load_proof(path):
    proof = cv2.imread(path)
    back = proof[189:720, 26:1641].copy()

    # Drawn grommets: small gold rings along the edges.
    hsv = cv2.cvtColor(back, cv2.COLOR_BGR2HSV)
    gold = cv2.inRange(hsv, (10, 60, 90), (35, 255, 255))
    n, lab, st, _ = cv2.connectedComponentsWithStats(gold)
    h, w = gold.shape
    mask = np.zeros_like(gold)
    for k in range(1, n):
        x, y, bw, bh, a = st[k]
        near_edge = x < 25 or x + bw > w - 25 or y < 25 or y + bh > h - 25
        if 15 < a < 400 and near_edge:
            cv2.circle(mask, (x + bw // 2, y + bh // 2), max(bw, bh), 255, -1)
    back = cv2.inpaint(back, mask, 5, cv2.INPAINT_TELEA)

    return cv2.resize(back, (back.shape[1] * 2, back.shape[0] * 2), interpolation=cv2.INTER_CUBIC)


def ink_rider(photo_path, mask_path, style="ink"):
    p = cv2.imread(photo_path)
    mask = cv2.imread(mask_path, 0)
    ys, xs = np.where(mask > 0)
    p = p[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    mask = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]

    g = cv2.cvtColor(p, cv2.COLOR_BGR2GRAY)
    if style == "photo":
        # Plain high-contrast black and white: no posterizing, no drawn outlines.
        g = cv2.createCLAHE(2.0, (8, 8)).apply(g)
        g = cv2.LUT(g, np.clip((np.arange(256) - 25) * 1.25, 0, 255).astype(np.uint8))
        edges = np.zeros_like(g)
    else:
        g = cv2.createCLAHE(3.0, (8, 8)).apply(g)
        g = cv2.addWeighted(g, 1.6, cv2.GaussianBlur(g, (0, 0), 3), -0.6, 0)
        g = cv2.LUT(g, np.clip((np.arange(256) - 60) * 1.6, 0, 255).astype(np.uint8))
        g = (np.round(g / 255 * 4) / 4 * 255).astype(np.uint8)
        edges = cv2.Canny(cv2.GaussianBlur(cv2.cvtColor(p, cv2.COLOR_BGR2GRAY), (5, 5), 0), 50, 130)
        g[cv2.dilate(edges, np.ones((2, 2), np.uint8)) > 0] = 0
    ink = cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)

    hsv = cv2.cvtColor(p, cv2.COLOR_BGR2HSV)
    jersey = cv2.morphologyEx(cv2.inRange(hsv, (100, 110, 60), (130, 255, 255)),
                              cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    lum = cv2.cvtColor(p, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    blue = np.clip(ROYAL_BGR[None, None, :] * (0.55 + 1.1 * lum[..., None]), 0, 255).astype(np.uint8)
    blue[edges > 0] = 0
    ink = np.where(jersey[..., None] > 0, blue, ink)

    outline = cv2.dilate(mask, np.ones((9, 9), np.uint8))
    ink[(outline > 0) & (mask == 0)] = BLACK_BGR
    alpha = cv2.GaussianBlur(outline, (5, 5), 0).astype(np.float32) / 255
    return ink, alpha


def splash_panel(h, lw, cx, cy, seed=11):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:lw].astype(np.float32)
    d = np.sqrt(((xx - cx) / 330) ** 2 + ((yy - cy) / (h * 0.55)) ** 2)

    def octave(s):
        n = rng.random((h // s + 2, lw // s + 2)).astype(np.float32)
        return cv2.resize(n, (lw, h), interpolation=cv2.INTER_CUBIC)

    n = 0.5 * octave(70) + 0.3 * octave(20) + 0.2 * octave(6)
    splash = ((1.2 - d) + 0.6 * (n - 0.5)) > 0.35
    specks = np.zeros((h, lw), np.uint8)
    for _ in range(1400):
        r, a = rng.uniform(0.8, 1.45), rng.uniform(0, 2 * np.pi)
        x, y = int(cx + np.cos(a) * r * 330), int(cy + np.sin(a) * r * h * 0.55)
        if 0 <= x < lw and 0 <= y < h:
            cv2.circle(specks, (x, y), int(rng.choice([1, 2, 2, 3, 4, 7])), 255, -1)
    panel = np.full((h, lw, 3), 10, np.uint8)
    panel[splash | (specks > 0)] = (228, 237, 242)
    panel[(rng.random((h, lw)) > 0.985) & splash] = BLACK_BGR
    return panel, xx


def main(proof_path, photo_path, mask_path, fonts, style="ink", out_name="goodbye-coffee-back-wall-FINAL-layout.png"):
    base = load_proof(proof_path)
    H, W = base.shape[:2]

    # Social row: Instagram, Facebook and YouTube icons + one search name, since the
    # Facebook username (goodbyecoffeeco) differs from the other two (@goodbye_coffee_co).
    y0, y1 = SOCIAL_ROW
    icons = [base[y0:y1, 889:995].copy(), base[y0:y1, 1044:1146].copy(), base[y0:y1, 1194:1318].copy()]
    icons = [cv2.resize(i, (int(i.shape[1] * ICON_SCALE), int(i.shape[0] * ICON_SCALE)), interpolation=cv2.INTER_AREA)
             for i in icons]
    base[y0 - 10:y1 + 10, 780:2085] = BG
    icon_xs, text_box = social_layout(fonts, [i.shape[1] for i in icons])
    for icon, x in zip(icons, icon_xs):
        y = (y0 + y1) // 2 - icon.shape[0] // 2
        a = np.clip((icon.max(axis=2).astype(np.float32) - 25) / 40, 0, 1)[..., None]
        roi = base[y:y + icon.shape[0], x:x + icon.shape[1]].astype(np.float32)
        base[y:y + icon.shape[0], x:x + icon.shape[1]] = (icon * a + roi * (1 - a)).astype(np.uint8)

    out = base.copy()

    # Left art: real rider on an ink splash, cross-faded into the original art.
    LW, cx = 800, 360
    panel, xx = splash_panel(H, LW, cx, H * 0.45)
    ink, alpha = ink_rider(photo_path, mask_path, style)
    rh = int(H * 0.97)
    rw = int(ink.shape[1] * rh / ink.shape[0])
    ink = cv2.resize(ink, (rw, rh), interpolation=cv2.INTER_AREA)
    alpha = cv2.resize(alpha, (rw, rh))[..., None]
    ox, oy = int(cx - rw / 2), H - rh
    roi = panel[oy:oy + rh, ox:ox + rw].astype(np.float32)
    panel[oy:oy + rh, ox:ox + rw] = (ink * alpha + roi * (1 - alpha)).astype(np.uint8)
    fade = np.clip((LW - xx) / 160, 0, 1)[..., None]
    out[:, :LW] = (panel * fade + base[:, :LW] * (1 - fade)).astype(np.uint8)

    # QR box (designer's white square) gets the real code.
    x0, x1, y0, y1 = 2100, 2582, 220, 710
    out[y0:y1, x0:x1] = 255
    qr = cv2.imread(f"{HERE}/../qr/goodbyecoffee-ride-qr.png")
    s = min(x1 - x0, y1 - y0)
    out[y0 + (y1 - y0 - s) // 2:y0 + (y1 - y0 - s) // 2 + s, x0 + (x1 - x0 - s) // 2:x0 + (x1 - x0 - s) // 2 + s] = \
        cv2.resize(qr, (s, s), interpolation=cv2.INTER_AREA)

    # Clear the old "SCAN TO SHOP" label.
    region = out[40:228, 2060:2625]
    text = (cv2.cvtColor(region, cv2.COLOR_BGR2GRAY) > 60).astype(np.uint8) * 255
    out[40:228, 2060:2625] = cv2.inpaint(region, cv2.dilate(text, np.ones((7, 7), np.uint8)), 7, cv2.INPAINT_TELEA)

    im = Image.fromarray(cv2.cvtColor(out, cv2.COLOR_BGR2RGB))
    d = ImageDraw.Draw(im)
    font_path = f"{fonts}/ChangaOne-Regular.ttf"

    def line(text, size, cx, top):
        f = ImageFont.truetype(font_path, size)
        b = d.textbbox((0, 0), text, font=f)
        d.text((cx - (b[2] - b[0]) // 2 - b[0], top - b[1]), text, font=f, fill=BONE)
        return top + (b[3] - b[1])

    qcx = (x0 + x1) // 2
    bottom = line("PUT YOUR RIDE", 66, qcx, 62)
    line("ON OUR BAG", 66, qcx, bottom + 22)

    line("COFFEE FOR RIDERS", 92, 1420, 55)

    tx0, ty0, tx1, ty1 = text_box
    f = ImageFont.truetype(font_path, 100)
    b = d.textbbox((0, 0), SOCIAL_TEXT, font=f)
    f = ImageFont.truetype(font_path, int(100 * (ty1 - ty0) / (b[3] - b[1])))
    b = d.textbbox((0, 0), SOCIAL_TEXT, font=f)
    d.text((tx0 - b[0], ty0 - b[1]), SOCIAL_TEXT, font=f, fill=BONE)

    out = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)
    cv2.imwrite(os.path.join(HERE, out_name), out)
    print("qr:", [r.text for r in zxingcpp.read_barcodes(out)])


if __name__ == "__main__":
    main(*sys.argv[1:7])

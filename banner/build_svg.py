"""Build vector (SVG) print files for the three Goodbye Coffee banners.

Usage:
    python3 banner/build_svg.py <original-logo.png>

Vector: logo (traced from the original logo file), all type (Changa One
converted to outlines, so no font is needed), QR codes, social icons.
Raster (embedded): the back wall's photo and illustration art only.
Files are sized in inches, so they open at true print size.
"""
import base64
import io
import sys

import cv2
import numpy as np
import potrace
import segno
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from PIL import Image

HERE = sys.path[0]
sys.path.insert(0, HERE)

BLACK = "#0A0A0A"
BONE = "#F2EDE4"
PINK = "#FF006E"
BLUE = "#02319F"
WHITE = "#FFFFFF"

FONT = TTFont(f"{HERE}/fonts/ChangaOne-Regular.ttf")
GLYPHS = FONT.getGlyphSet()
CMAP = FONT.getBestCmap()
UPM = FONT["head"].unitsPerEm


# ---------- tracing ----------

def trace(mask, sx=1.0, sy=1.0, ox=0.0, oy=0.0):
    """Trace a boolean mask into an SVG path 'd' (even-odd), scaled and offset."""
    # potracer fills the dark (False) pixels, so invert.
    path = potrace.Bitmap(~mask).trace(turdsize=8, alphamax=1.0, opticurve=True, opttolerance=0.2)
    p = lambda pt: f"{pt.x * sx + ox:.2f},{pt.y * sy + oy:.2f}"
    parts = []
    for curve in path:
        parts.append(f"M{p(curve.start_point)}")
        for seg in curve.segments:
            if seg.is_corner:
                parts.append(f"L{p(seg.c)}L{p(seg.end_point)}")
            else:
                parts.append(f"C{p(seg.c1)} {p(seg.c2)} {p(seg.end_point)}")
        parts.append("Z")
    return "".join(parts)


def logo_layers(logo_path):
    """Trace the original logo into flat-color layers. Returns (width, height, [(color, d)])."""
    o = cv2.imread(logo_path)
    crop = o[110:580, 40:1740]
    ys, xs = np.where(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) > 60)
    crop = crop[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    up = 4
    big = cv2.resize(crop, None, fx=up, fy=up, interpolation=cv2.INTER_CUBIC).astype(np.float32)
    palette = np.array([[1, 1, 2], [253, 253, 253], [102, 5, 248], [159, 49, 2]], np.float32)  # BGR
    dist = ((big[:, :, None, :] - palette[None, None]) ** 2).sum(-1)
    label = dist.argmin(-1).astype(np.uint8)
    label = cv2.medianBlur(label, 7)
    layers = []
    for idx, color, grow in ((2, PINK, 2), (3, BLUE, 2), (1, WHITE, 0)):
        m = (label == idx).astype(np.uint8)
        if grow:
            m = cv2.dilate(m, np.ones((grow * 2 + 1,) * 2, np.uint8))
        layers.append((color, trace(m > 0, 1 / up, 1 / up)))
    return crop.shape[1], crop.shape[0], layers


def logo_svg(layers_info, x, y, width):
    w, h, layers = layers_info
    k = width / w
    paths = "".join(f'<path fill="{c}" fill-rule="evenodd" d="{d}"/>' for c, d in layers)
    return f'<g transform="translate({x:.2f},{y:.2f}) scale({k:.5f})">{paths}</g>', h * k


def icon_svg(gray, x, y, height):
    """Trace a white-on-black icon (grayscale array) into a white path."""
    up = 6
    big = cv2.resize(gray, None, fx=up, fy=up, interpolation=cv2.INTER_CUBIC)
    m = cv2.GaussianBlur(big, (5, 5), 0) > 128
    k = height / gray.shape[0]
    return f'<path fill="{BONE}" fill-rule="evenodd" d="{trace(m, k / up, k / up, x, y)}"/>'


# ---------- type ----------

def text_path(text, size):
    """Outline a string in Changa One. Returns (d, x_min, y_min, x_max, y_max) at origin baseline."""
    s = size / UPM
    x = 0
    d = []
    bounds = [None] * 4
    hmtx = FONT["hmtx"]
    for ch in text:
        name = CMAP[ord(ch)]
        pen = SVGPathPen(GLYPHS)
        GLYPHS[name].draw(TransformPen(pen, (s, 0, 0, -s, x, 0)))
        d.append(pen.getCommands())
        bp = BoundsPen(GLYPHS)
        GLYPHS[name].draw(TransformPen(bp, (s, 0, 0, -s, x, 0)))
        if bp.bounds:
            b = bp.bounds
            bounds = [b[i] if bounds[i] is None else (min if i < 2 else max)(bounds[i], b[i]) for i in range(4)]
        x += hmtx[name][0] * s
    return "".join(d), *bounds


def text_svg(text, box=None, size=None, cx=None, cy=None, fill=BONE):
    """Place text centered in box (x0,y0,x1,y1) at the largest size that fits, or at size centered on (cx, cy)."""
    if size is None:
        x0, y0, x1, y1 = box
        _, a, b, c, e = text_path(text, 1000)
        size = 1000 * min((x1 - x0) / (c - a), (y1 - y0) / (e - b))
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    d, a, b, c, e = text_path(text, size)
    tx, ty = cx - (a + c) / 2, cy - (b + e) / 2
    return f'<path fill="{fill}" transform="translate({tx:.2f},{ty:.2f})" d="{d}"/>', size, e - b


# ---------- QR ----------

def qr_svg(url, x, y, size):
    """QR code as vector squares, including a white quiet zone of 4 modules."""
    q = segno.make(url, error="q", micro=False)
    n = q.symbol_size(border=4)[0]
    m = size / n
    rects = [f'<rect x="{x:.2f}" y="{y:.2f}" width="{size:.2f}" height="{size:.2f}" fill="{WHITE}"/>']
    d = []
    for r, row in enumerate(q.matrix_iter(border=4)):
        for c, v in enumerate(row):
            if v:
                d.append(f"M{x + c * m:.3f},{y + r * m:.3f}h{m:.3f}v{m:.3f}h{-m:.3f}z")
    rects.append(f'<path fill="#000000" d="{"".join(d)}"/>')
    return "".join(rects)


# ---------- documents ----------

def document(w_in, h_in, vw, vh, body):
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{w_in}in" height="{h_in}in" viewBox="0 0 {vw} {vh}">'
            f'<rect width="{vw}" height="{vh}" fill="{BLACK}"/>{body}</svg>\n')


def embed_png(img_bgr, x, y, w, h):
    buf = io.BytesIO()
    Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)).save(buf, "PNG", optimize=True)
    data = base64.b64encode(buf.getvalue()).decode()
    return f'<image x="{x}" y="{y}" width="{w}" height="{h}" preserveAspectRatio="none" xlink:href="data:image/png;base64,{data}"/>'


def valance(logo):
    W, H = 6000, 600
    url, _, url_h = text_svg("GOODBYECOFFEE.COM", size=1, cx=0, cy=0)
    # Size URL to 200 px cap height, matching the PNG version.
    _, a, b, c, e = text_path("GOODBYECOFFEE.COM", 1000)
    size = 1000 * 200 / (e - b)
    url_w = (c - a) * size / 1000
    lw = logo[0] * 430 / logo[1]
    gap = 140
    total = lw + gap + 12 + gap + url_w
    x = (W - total) / 2
    g, _ = logo_svg(logo, x, (H - 430) / 2, lw)
    dx = x + lw + gap
    divider = f'<rect x="{dx:.2f}" y="130" width="12" height="{H - 260}" fill="{BONE}"/>'
    url, _, _ = text_svg("GOODBYECOFFEE.COM", size=size, cx=dx + 12 + gap + url_w / 2, cy=H / 2)
    return document(120, 12, W, H, g + divider + url)


def table_front(logo):
    from build_table_front import MARGIN, TOP_ZONE, FACEBOOK_URL
    W, H = 3000, 900
    zone_top, zone_bottom = TOP_ZONE
    zone_mid = (zone_top + zone_bottom) / 2
    body = []

    qs = 400
    label_h = 44
    block_h = 2 * label_h + 16 + 26 + qs
    qx = W - MARGIN - qs
    top = zone_top + (zone_bottom - zone_top - block_h) / 2
    for i, t in enumerate(("FOLLOW US", "ON FACEBOOK")):
        _, a, b, c, e = text_path(t, 1000)
        p, _, _ = text_svg(t, size=1000 * label_h / (e - b), cx=qx + qs / 2, cy=top + i * (label_h + 16) + label_h / 2)
        body.append(p)
    body.append(qr_svg(FACEBOOK_URL, qx, top + 2 * label_h + 16 + 26, qs))

    lw = 1000
    g, lh = logo_svg(logo, MARGIN, 0, lw)
    g, lh = logo_svg(logo, MARGIN, zone_mid - lh / 2, lw)
    body.append(g)

    left, right = MARGIN + lw + 70, qx - 90
    body.append(f'<rect x="{left}" y="{zone_top + 40}" width="8" height="{zone_bottom - zone_top - 80}" fill="{BONE}"/>')
    avail = right - (left + 8 + 70)
    lines = ["COFFEE FOR", "THE RIDE"]
    size = min(1000 * avail / (text_path(t, 1000)[3] - text_path(t, 1000)[1]) for t in lines)
    heights = [text_path(t, size)[4] - text_path(t, size)[2] for t in lines]
    gap = 36
    y = zone_mid - (sum(heights) + gap) / 2
    cx = (left + 8 + 70 + right) / 2
    for t, h in zip(lines, heights):
        p, _, _ = text_svg(t, size=size, cx=cx, cy=y + h / 2)
        body.append(p)
        y += h + gap

    _, a, b, c, e = text_path("GOODBYECOFFEE.COM", 1000)
    url_size = 1000 * 45 / (e - b)
    url_mid = zone_bottom + (H - zone_bottom) / 2 - 20
    p, _, _ = text_svg("GOODBYECOFFEE.COM", size=url_size, cx=W / 2, cy=url_mid)
    body.append(p)
    return document(60, 18, W, H, "".join(body))


def back_wall(logo, logo_path):
    import build_print as bp
    from build_back_wall import ICON_SCALE, ICON_SRC_WIDTHS, SOCIAL_ROW, social_layout

    layout = cv2.imread(f"{HERE}/goodbye-coffee-back-wall-FINAL-layout.png")
    s = bp.OUT_W / layout.shape[1]
    img = cv2.resize(layout, (bp.OUT_W, round(layout.shape[0] * s)), interpolation=cv2.INTER_LANCZOS4)
    H, W = img.shape[:2]
    S = lambda box: tuple(v * s for v in box)

    # Icons, traced from the layout before they're cleared.
    icon_xs, handle = social_layout(f"{HERE}/fonts", [int(w * ICON_SCALE) for w in ICON_SRC_WIDTHS])
    y0, y1 = SOCIAL_ROW
    gray = cv2.cvtColor(layout, cv2.COLOR_BGR2GRAY)
    icons = []
    for x, w in zip(icon_xs, [int(w * ICON_SCALE) for w in ICON_SRC_WIDTHS]):
        rows = np.where((gray[y0:y1, x:x + w] > 128).any(axis=1))[0]
        iy0, iy1 = y0 + rows.min(), y0 + rows.max() + 1
        icons.append((gray[iy0:iy1, x:x + w], x * s, iy0 * s, (iy1 - iy0) * s))
        bp.clear(img, (x - 4, iy0 - 4, x + w + 4, iy1 + 4), s)

    for box in (bp.LOGO_CLEAR, bp.URL, handle, bp.TAGLINE, bp.QR_LABEL):
        bp.clear(img, box, s)
    for x0, y0_, x1, y1_ in (bp.CENTER, (2090, 0, 2600, 215)):
        region = img[int(y0_ * s):int(y1_ * s), int(x0 * s):int(x1 * s)]
        region[region.max(axis=2) < 24] = bp.BG
    qx0, qy0, qx1, qy1 = (int(v * s) for v in bp.QR_BOX)
    img[qy0:qy1, qx0:qx1] = bp.BG

    body = [embed_png(img, 0, 0, W, H)]

    lx0, ly0, lx1, ly1 = S(bp.LOGO)
    k = min((lx1 - lx0) / logo[0], (ly1 - ly0) / logo[1])
    g, lh = logo_svg(logo, lx0 + (lx1 - lx0 - logo[0] * k) / 2, ly0 + (ly1 - ly0 - logo[1] * k) / 2, logo[0] * k)
    body.append(g)

    q = min(qx1 - qx0, qy1 - qy0)
    body.append(f'<rect x="{qx0}" y="{qy0}" width="{qx1 - qx0}" height="{qy1 - qy0}" fill="{WHITE}"/>')
    body.append(qr_svg("https://goodbyecoffee.com/ride", qx0 + (qx1 - qx0 - q) / 2, qy0 + (qy1 - qy0 - q) / 2, q))

    for gray_icon, x, y, h in icons:
        body.append(icon_svg(gray_icon, x, y, h))

    body.append(text_svg("GOODBYECOFFEE.COM", S(bp.URL))[0])
    body.append(text_svg("COFFEE FOR RIDERS", S(bp.TAGLINE))[0])
    body.append(text_svg("GOODBYE COFFEE CO", S(handle))[0])
    a0, b0, a1, b1 = bp.QR_LABEL
    mid = (b0 + b1) / 2
    top_box, bottom_box = S((a0, b0, a1, mid - 6)), S((a0, mid + 6, a1, b1))
    size = min(text_svg("PUT YOUR RIDE", top_box)[1], text_svg("ON OUR BAG", bottom_box)[1])
    for t, box in (("PUT YOUR RIDE", top_box), ("ON OUR BAG", bottom_box)):
        body.append(text_svg(t, size=size, cx=(box[0] + box[2]) / 2, cy=(box[1] + box[3]) / 2)[0])

    return document(120, round(120 * H / W, 2), W, H, "".join(body))


def main(logo_path):
    logo = logo_layers(logo_path)
    for name, svg in (("valance-120x12", valance(logo)),
                      ("table-front-60x18", table_front(logo)),
                      ("back-wall-120x40", back_wall(logo, logo_path))):
        path = f"{HERE}/goodbye-coffee-{name}.svg"
        with open(path, "w") as f:
            f.write(svg)
        print(path, f"{len(svg) / 1e6:.1f} MB")


if __name__ == "__main__":
    main(sys.argv[1])

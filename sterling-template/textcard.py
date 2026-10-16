"""Render the pink handwritten quote card for a Sterling's Life Lessons reel.

usage: python3 textcard.py quotes/<name>.txt out.png
Quote file: one line of text per line as it should appear on screen.
Wrap ONE word in underscores (e.g. _caring._) to underline it.
"""
import sys, re, os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, 'assets', 'caveat-brush-latin-400-normal.woff')
PINK = (252, 0, 108, 255)            # #FC006C, sampled from the template
W, H = 720, 1280
X0, X1, Y0, Y1 = 34, 683, 148, 1125  # text block bounds, sampled from the template
MAXPX, GAP = 150, 4

def fit(text, width):
    size = 200
    while size > 10:
        f = ImageFont.truetype(FONT, size)
        b = f.getbbox(text)
        if b[2] - b[0] <= width:
            return f
        size -= 1
    return ImageFont.truetype(FONT, size)

def main(src, out):
    raw = [l.strip() for l in open(src, encoding='utf-8') if l.strip()]
    lines, underline = [], {}
    for i, l in enumerate(raw):
        m = re.search(r'_(.+?)_', l)
        if m:
            underline[i] = m.group(1)
            l = l.replace(m.group(0), m.group(1))
        lines.append(l)
    fonts = []
    for l in lines:
        f = fit(l, X1 - X0)
        if f.size > MAXPX:
            f = ImageFont.truetype(FONT, MAXPX)
        fonts.append(f)
    height = lambda: sum(f.getbbox(l)[3] - f.getbbox(l)[1] for f, l in zip(fonts, lines)) + GAP * (len(lines) - 1)
    total = height()
    if total > Y1 - Y0:
        k = (Y1 - Y0) / total
        fonts = [ImageFont.truetype(FONT, int(f.size * k)) for f in fonts]
        total = height()
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    y = Y0 + ((Y1 - Y0) - total) // 2
    for i, (l, f) in enumerate(zip(lines, fonts)):
        b = f.getbbox(l)
        x = (W - (b[2] - b[0])) // 2 - b[0]
        d.text((x, y - b[1]), l, font=f, fill=PINK)
        if i in underline:
            word = underline[i]
            ux0 = x + f.getlength(l[:l.index(word)])
            uy = y + (b[3] - b[1]) + 3
            d.line((ux0 + 2, uy, ux0 + f.getlength(word) - 2, uy), fill=PINK, width=max(3, f.size // 22))
        y += b[3] - b[1] + GAP
    im.save(out)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])

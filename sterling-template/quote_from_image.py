"""Turn a pink handwritten quote on a white background into a transparent 720x1280 card.

usage: python3 quote_from_image.py input.(png|jpg|webp) quotes/<name>.png
"""
import sys
import numpy as np
from PIL import Image

PINK = (252, 0, 108)

def main(src, out):
    a = np.asarray(Image.open(src).convert('RGB')).astype(float)
    alpha = np.clip(((255 - a[:, :, 1]) / 255 - 0.08) / 0.6, 0, 1)  # pink has low green
    ys, xs = np.where(alpha > 0.2)
    rgba = np.zeros(a.shape[:2] + (4,), np.uint8)
    rgba[..., :3] = PINK
    rgba[..., 3] = (alpha * 255).astype(np.uint8)
    t = Image.fromarray(rgba).crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    k = min(660 / t.width, 1060 / t.height)
    t = t.resize((int(t.width * k), int(t.height * k)), Image.LANCZOS)
    card = Image.new('RGBA', (720, 1280), (0, 0, 0, 0))
    card.alpha_composite(t, ((720 - t.width) // 2, (1280 - t.height) // 2))
    card.save(out)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])

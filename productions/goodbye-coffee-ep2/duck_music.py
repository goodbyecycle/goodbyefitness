# Ducks the piano under the v4 narration: -13 dB while a line plays, with soft ramps.
# Line starts/lengths are from the stitched voiceover (voiceover-v4.md).
import numpy as np, wave, sys
LINES = [(0.80,13.32),(15.22,13.64),(29.96,3.97),(34.23,1.41),(36.74,5.49),(43.33,5.15),(49.57,2.93),
         (53.60,7.16),(61.85,6.19),(69.15,3.16),(73.41,6.43),(80.93,4.28),(86.32,12.83),(100.24,7.24),
         (108.58,1.80),(111.48,12.12),(124.70,3.24),(129.04,6.27),(137.51,2.12),(140.53,2.35),
         (143.78,4.52),(150.80,1.23)]
src, dst = sys.argv[1], sys.argv[2]
w = wave.open(src); sr = w.getframerate(); ch = w.getnchannels()
x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32).reshape(-1, ch) / 32768
t = np.arange(len(x)) / sr
duck = np.zeros(len(x), np.float32)
for s, d in LINES:
    a, b = s - 0.35, s + d + 0.6
    up = np.clip((t - a) / 0.35, 0, 1)
    down = np.clip((b - t) / 0.8, 0, 1)
    duck = np.maximum(duck, np.minimum(up, down))
gain = 10 ** (-13 * duck / 20)
y = (x * gain[:, None] * 32767).clip(-32768, 32767).astype(np.int16)
o = wave.open(dst, 'wb'); o.setnchannels(ch); o.setsampwidth(2); o.setframerate(sr); o.writeframes(y.tobytes()); o.close()
print('ducked', len(x) / sr, 's')

"""Deep, slow solo-piano bed (synthesized). usage: python3 piano_bed.py out.wav [seconds] [variant 0-7]"""
import sys, wave
import numpy as np
SR = 44100
def freq(m): return 440 * 2 ** ((m - 69) / 12)
def note(m, dur, vel):
    t = np.arange(int(SR * dur)) / SR; f = freq(m); s = np.zeros_like(t)
    for h, a in [(1, 1), (2, .5), (3, .25), (4, .12), (5, .06), (6, .03), (7, .015)]:
        fh = f * h * np.sqrt(1 + 0.0004 * h * h)
        s += a * np.sin(2 * np.pi * fh * t) * np.exp(-t * (0.45 + 0.45 * h) * (f / 260) ** 0.3)
    return vel * s * np.minimum(1, t / 0.008)
# minor progressions, deep register (triads as MIDI notes)
PROGS = [
    [(45, 48, 52), (41, 45, 48), (36, 40, 43), (43, 47, 50)],  # Am F C G
    [(40, 43, 47), (36, 40, 43), (43, 47, 50), (38, 41, 45)],  # Em C G Dm
    [(38, 41, 45), (34, 38, 41), (41, 45, 48), (33, 36, 40)],  # Dm Bb F Am
    [(45, 48, 52), (38, 41, 45), (40, 43, 47), (45, 48, 52)],  # Am Dm Em Am
    [(36, 39, 43), (44, 48, 51), (46, 50, 53), (43, 47, 50)],  # Cm Ab Bb G
    [(41, 44, 48), (37, 41, 44), (39, 43, 46), (36, 39, 43)],  # Fm Db Eb Cm
    [(43, 46, 50), (39, 43, 46), (46, 50, 53), (41, 45, 48)],  # Gm Eb Bb F
    [(40, 43, 47), (45, 48, 52), (36, 40, 43), (35, 39, 42)],  # Em Am C B
]
def render(out, seconds=21.6, v=0):
    rng = np.random.default_rng(100 + v); prog = PROGS[v % len(PROGS)]
    buf = np.zeros(int(SR * (seconds + 8))); beat = 60 / 40
    def add(m, start, dur, vel):
        i = int(start * SR); n = note(m, dur, vel); buf[i:i + len(n)] += n[:len(buf) - i]
    t, ci = 0.3, 0
    while t < seconds:
        r, th, fi = prog[ci % len(prog)]
        add(r - 12, t, 8, .6); add(r, t + .03, 8, .3)              # deep octave bass
        for k, n in enumerate([th + 12, fi + 12, r + 24]):           # slow broken chord
            add(n, t + beat * (1 + k * .9), 6, .2)
        mel = [fi + 24, th + 24, r + 24]
        add(int(rng.choice(mel)), t + beat * 2.6, 6, .24)
        t += beat * 4; ci += 1
    buf = buf[:int(SR * seconds)]
    y = buf.copy()
    for d, g in [(.029, .4), (.043, .35), (.067, .3), (.101, .25), (.149, .2), (.211, .16), (.307, .12), (.43, .08)]:
        k = int(d * SR); y[k:] += g * buf[:-k]
    fo = int(2 * SR); y[-fo:] *= np.linspace(1, 0, fo)
    y /= np.abs(y).max() * 1.1
    pcm = (y * 32767).astype(np.int16)
    w = wave.open(out, 'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(np.stack([pcm, pcm], 1).tobytes()); w.close()
if __name__ == '__main__':
    render(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 21.6, int(sys.argv[3]) if len(sys.argv) > 3 else 0)

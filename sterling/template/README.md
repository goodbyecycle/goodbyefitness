# Sterling's Life Lessons — reel template

Master reference: `assets/sterlings-life-lessons-01.mp4` (720x1280, 24fps, ~21.5s).
Every new reel reuses its music and end card.

## Format
| Time | What happens |
|---|---|
| 0–4.5s | Sterling scene (mustard velvet couch, bike shop, blue Goodbye Coffee mug with pink G) |
| 4.5–8s | Scene desaturates and fades to black; pink quote fades in |
| 8–18s | Quote holds on black |
| 18–19s | Quote fades out |
| 19.25s–end | "Sterling's Life Lessons / Good Bye Coffee / @goodbye_coffee_co" end card |
| Audio | `assets/music-bed.m4a` (#01's music with the old voice removed) + new voiceover from 4.5s |

Text: Caveat Brush, pink `#FC006C`, centered, each line sized to fill the width,
one key word underlined.

## Making a new one
1. Generate the scene clip in Higgsfield (9:16, ~10s; only the first 8s is used).
2. Write the quote in `quotes/<name>.txt`, one on-screen line per line,
   and wrap the key word in underscores: `_weaponizing_`.
   Or use a handwritten quote image (pink on white):
   `python3 quote_from_image.py hand.webp quotes/<name>.png` and pass the `.png` instead.
3. Voiceover: in Higgsfield, text-to-speech → ElevenLabs → preset voice **"Sterling"**
   (voice id `dc382508-c8bd-443c-8cb2-46e57b8d2e6f`). Write the quote with `...` between
   phrases for Sterling's slow pacing. Aim for ~11–13s.
4. Run:
   ```
   ./build.sh scene.mp4 quotes/<name>.txt out.mp4 voiceover.mp3   # or quotes/<name>.png
   ```
Requires ffmpeg and Python 3 with Pillow.

### Timing a different clip
If Sterling is still moving when the fade starts, skip the start of the clip and/or hold
the scene longer (everything after — fade, quote, voice — shifts with it; end card stays at 19.25s):
```
START=0.5 DELAY=1.5 ./build.sh scene.mp4 quotes/<name>.png out.mp4 voiceover.mp3
```
The Oct 15 "sits back and crosses his legs" clip uses `START=0.5 DELAY=1.5`.

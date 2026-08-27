# MARIA — THE LONG WAY HERE

Remotion assembly for the Coffee Mug Stories short. 1920×1080, 30 fps.

## Status

| Stage | State |
|---|---|
| 18 storyboard frames | present, **not yet 16:9** — see *Known blockers* |
| Seedance clips | none yet |
| ElevenLabs narration | none yet |
| Remotion composition | built, renders as a timed animatic today |

## Quick start

```bash
npm install
npm run scan        # detect which clips/audio are present
npm run studio      # interactive timeline
npm run animatic    # render current state to out/animatic.mp4
```

Set `REMOTION_BROWSER_EXECUTABLE` if Chromium isn't auto-detected.

## How assets drop in

The composition renders whatever exists and falls back for the rest, so it is
always renderable:

```
public/clips/Scene_01.mp4 … Scene_18.mp4   Seedance clips (scene falls back to
                                            its storyboard still if absent)
public/audio/narration.mp3                  ElevenLabs VO — the timing spine
public/audio/music.mp3                      score bed, ducked under narration
```

Run `npm run scan` after adding files. It regenerates `src/clips-manifest.ts`.

## Runtime: 4:18, not 2:30

The production package specifies exactly 150 seconds. That target predates the
voiceover and does not survive contact with it. The script in section 5 is **503
words across 97 lines with 18 ellipsis pauses**. Fitting that into 150s requires
roughly 202 wpm with no pauses at all — auctioneer pace, and the opposite of the
"natural slow-to-medium" delivery the package itself calls for.

Runtime was extended rather than cutting the script. Durations are derived
per-scene from the VO actually assigned to each scene (via the package's own
"Edit / VO note" cues), read at 145 wpm with a 0.20s beat per line break, 0.35s
extra per ellipsis, and 0.6s headroom. Scenes carrying no VO keep a visual floor.

**Total: 258.0s = 7,740 frames = 4:18.0**

All timing lives in `src/edit-map.ts`. That is the only file to edit to retime.

## Known blockers

**1. The frames are not 16:9.** Every file is a 1920×1080 canvas, but the real
artwork is a square or portrait image inside blurred pillarbox bars — between
36% and 67% of each frame is filler, and true aspect swings from 0.588 (scene
10) to 1.141 (scene 09). Image-to-video will animate the bars along with the
art, and they will drift and shimmer. Measured content boxes for every frame are
in `src/frame-geometry.ts` for the outpaint pass. Fix before generating clips.

**2. Long scenes will drift.** Seedance 2.5 generates 4–30s, so every scene fits
in one clip. But holding character and bike continuity across a 30s generation is
far harder than across 8s, and scenes 10, 11, 12, 14, 17 and 18 are all 18s+.
Expect to split the long ones into two clips seeded from the previous last frame,
or use Seedance's `video_extension` mode.

**3. Narrator voice is unconfirmed.** The package asks for a female narrator,
35–50. The standing brand default is Michael C. Vincent, with Daniel as the
alternate, and any new voice needs sign-off.

**4. "Exactly four women" may not match the art.** The continuity lock requires
any frame showing four women to stay four women. In scenes 09, 16 and 17 the
third figure reads male-presenting. Confirm before generating those three, or
three separate clips will each resolve it differently.

## Generation settings

When generating clips, pass `generate_audio: false` — Seedance defaults it to
true, and generated audio will fight the ElevenLabs narration and the sound
design plan.

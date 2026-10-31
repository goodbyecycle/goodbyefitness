# Sterling — Goodbye Coffee "Sterling's Life Lessons"

Everything for the Sterling reels in one place.

## Folders
| Path | What |
|---|---|
| `template/` | Reel template: `build.sh`, quote card scripts, music bed, font, master reel `assets/sterlings-life-lessons-01.mp4`. See `template/README.md`. |
| `quotes/batch-02-handwritten/` | Next batch of quotes (13–20), pink handwritten on white. Convert with `template/quote_from_image.py`. |
| `sterling-original-frame.jpg` | Frame from reel #01 (mustard couch, bike-shop café, blue G mug). |

Published reels 01–12: Google Drive, `sterlings-life-lessons-01.mp4` … `-12.mp4` (uploaded Oct 15).

## Batch 02 quotes
13. Being the person that everyone depends on doesn't mean you have someone to depend on.
14. The loneliest feeling isn't having nobody around—it's realizing nobody notices when you're struggling.
15. You can spend your whole life showing up for people who never think to show up for you.
16. If you are lonely when you are alone, you are in bad company.
17. Solitude is the most compassionate companion.
18. GOAL: Become the person who does not abandon themself to make everybody happy.
19. STOP: Measuring your worth by how often other people remember you.
20. Resolve the incident when it happens. Anger and resentment only collect interest. Eventually the loan will come due and you'll forget what the loan was for.

## Batch 02 look
- Scene in **black and white; the only color is the blue Goodbye Coffee mug (pink G) and Sterling's royal-blue newsie cap**.
- Quote card: **white background, pink handwriting**, using the batch images as-is (not the template's pink-on-black).
- Music: deep, slow piano (`template/piano_bed.py`, 8 variants).
- Build: `PIANO=<0-7> ./template/build_bw.sh scene.mp4 quotes/batch-02-handwritten/quote-13.png out.mp4 [voiceover.mp3]`
  (scene, fade to white, pink-on-white card from the image as-is, template end card).

## Higgsfield assets
Pass these IDs as `medias[].value` in Higgsfield generations.

| ID | Type | What |
|---|---|---|
| `a566dc59-c471-4119-920b-a0dba5f02a0f` | uploaded image | Sterling start frame (couch, journal, mug), used for the Oct 15–16 scenes |
| `49a10554-6067-465c-b911-dcfddee553fd` | image job | Earlier Sterling start frame (Oct 9) |
| `b50580a6-7938-4f5a-9ba9-ca1042f7e7f3` | image job | **Blue newsie cap still v1**, B&W except mug + cap |
| `d2ab78d1-d571-4f14-ad77-3b730cdd8e69` | image job | **Blue newsie cap still v2**, B&W except mug + cap |
| `a9344526-2960-43fd-88bc-b6444ee947de` | image job | **Blue newsie cap still v3 (high quality)**, only mug + cap in color |
| `df12b8ca-af97-49e6-b5a5-6a93dde52e23` | image job | **Blue newsie cap still v4 (high quality)**, only mug + cap in color |
| `abb7a5a7-9070-4ba2-bb16-91a19c199fa6` | video (seedance 2.5) | **Batch 02 scene A**, cap still v4 animated |
| `7f6228c3-4f13-4d6b-922b-fa3697195f0a` | video (seedance 2.5) | **Batch 02 scene B**, cap still v4 animated |
| `52af8a23-23d6-4cfc-8ad8-c0a4c7dcd44f` | video (seedance 2.5) | Sets journal down, sits back, crosses legs (Oct 15; used with `START=0.5 DELAY=1.5`) |
| `092f577c-40b9-4fbd-a894-4bfc9d6bda4c` | video (seedance 2.5) | Closes journal, hand on it, push-in to mug (Oct 16) |
| `f7d18f2e-04a1-4b95-b4bb-bd82632e2b6d` | video (kling 3.0) | Closes journal, picks up mug, 9:16 (Oct 9) |

Sterling voice: Higgsfield text-to-speech → ElevenLabs → preset **"Sterling"**
(voice id `dc382508-c8bd-443c-8cb2-46e57b8d2e6f`).

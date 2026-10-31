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

## Batch 02 voiceovers (Sterling voice, ElevenLabs via Higgsfield text2speech_v2)
| Quote | Job ID |
|---|---|
| 13 | `61fcd163-298b-4b22-af44-9d0569bd30f6` |
| 14 | `1a01caa3-70a3-4081-90b0-bb7ca66b94aa` |
| 15 | `d1cf0e25-cba1-43f6-9f30-c9135e4cf787` |
| 16 | `f0fdd55c-8826-40e9-b73b-18ace6e06b13` |
| 17 | `bbb42e3f-0def-458c-aeac-d60c7350e0bd` |
| 18 | `204b771e-14a6-4278-bd47-62d3c23d3be2` |
| 19 | `f01c3eb2-0b7c-49bb-8f37-1ed626932ae4` |
| 20 | `b717584e-0c2e-4404-be88-6ef5b04e9860` |

## Batch 02 finished reels (scene A, built with `build_bw.sh`, START=0.8 DELAY=2.5; #20 DELAY=0.5)
Stored in Higgsfield media (uploads).
| Reel | Link |
|---|---|
| 13 | https://d2ol7oe51mr4n9.cloudfront.net/user_3CDJYxo6oMtAhh5w2jvaKvUEU5w/b48c3a85-48f9-4a8f-92f0-fe45bfd9885a.mp4 |
| 14 | https://d2ol7oe51mr4n9.cloudfront.net/user_3CDJYxo6oMtAhh5w2jvaKvUEU5w/5654992a-9f38-4c2d-ad70-a441a50a7799.mp4 |
| 15 | https://d2ol7oe51mr4n9.cloudfront.net/user_3CDJYxo6oMtAhh5w2jvaKvUEU5w/9c21eccc-ab0d-4048-ad62-08c8862890d3.mp4 |
| 16 | https://d2ol7oe51mr4n9.cloudfront.net/user_3CDJYxo6oMtAhh5w2jvaKvUEU5w/1ed3bd0e-1e23-4e6d-8875-ad7f11858edf.mp4 |
| 17 | https://d2ol7oe51mr4n9.cloudfront.net/user_3CDJYxo6oMtAhh5w2jvaKvUEU5w/df3b3d63-3d1d-4162-8d7e-37b9029f4126.mp4 |
| 18 | https://d2ol7oe51mr4n9.cloudfront.net/user_3CDJYxo6oMtAhh5w2jvaKvUEU5w/60d29c3d-d566-4e3f-aac8-29764edfd768.mp4 |
| 19 | https://d2ol7oe51mr4n9.cloudfront.net/user_3CDJYxo6oMtAhh5w2jvaKvUEU5w/b637d5b1-ff05-4217-b594-273c32074e59.mp4 |
| 20 | https://d2ol7oe51mr4n9.cloudfront.net/user_3CDJYxo6oMtAhh5w2jvaKvUEU5w/3f12d02a-bdcd-4685-88d8-9d0e85f31bed.mp4 |

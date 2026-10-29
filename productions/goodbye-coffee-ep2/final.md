# Ep. 2 — final cut (page-turn version, 2:40)

**Video (with subtitles, soft piano):** https://d2ol7oe51mr4n9.cloudfront.net/user_3CDJYxo6oMtAhh5w2jvaKvUEU5w/394a22ef-d882-4aa1-a194-6c490cea74f4.mp4

The earlier cut, without subtitles: https://d2ol7oe51mr4n9.cloudfront.net/user_3CDJYxo6oMtAhh5w2jvaKvUEU5w/2a688377-5f4a-4ee1-8240-5bbe2c981a6f.mp4

- **Subtitles:** Montserrat ExtraBold, royal blue (#1f45ff) with a 14px white outline, lower third. Short phrases are timed from word timestamps (`remotion/src/captions.js`). There are no subtitles over the quote card, which already shows the words.
- **Piano:** softer than the first cut. It sits 4 dB lower, is low-passed at 3.2 kHz, has more room reverb, and still drops 13 dB under the narration.

- **Picture:** 19 storyboard stills with no AI animation. Each still pushes in slowly, and a page turn plus a paper sound moves to the next panel. Film grain and a vignette go over everything.
- **Ending:**
  - E ("Let me tell you something, young lady") fades out, and the feed-safe quote card fades in.
  - The quote appears one sentence at a time as it is read.
  - The picture fades back in on F ("…Probably not."), then the end card.
- **Audio:**
  - The v4 voiceover.
  - The piano score (`piano_score.py`, ducked by `duck_music.py`).
  - Page-flip sounds.
  - The mix is normalized to -16 LUFS with two-pass linear loudnorm.
- **Build:**
  - Remotion (`remotion/`) renders the picture with audio muted, in two halves.
  - ffmpeg joins the halves, mixes the audio, and adds the grain and vignette.
- **Cost:** 0 Higgsfield credits for assembly.
- **Stills used:** C = 7bd06518 (wide; her look matches A). 14 = 6602cf08 (journal with illegible scribbles).

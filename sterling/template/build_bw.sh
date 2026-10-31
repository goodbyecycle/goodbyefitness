#!/bin/bash
# Batch 02 look: selective-color scene (only mug + blue newsie cap in color) -> fade to WHITE ->
# pink-on-white handwritten quote card (image used as-is) -> template end card. Deep slow piano bed.
# usage: ./build_bw.sh <scene.mp4> <quote-image.png> <out.mp4> [voiceover.mp3]
# env: START, DELAY (as build.sh), PIANO=<0-7> piano variant (default 0)
set -e
START=${START:-0}; DELAY=${DELAY:-0}; PIANO=${PIANO:-0}
f() { python3 -c "print(round($1,3))"; }
T_IN=$(f "4.5+$DELAY"); T_PAD=$(f "11.25-$DELAY"); T_VO=$(f "(4.5+$DELAY)*1000")
D=$(cd "$(dirname "$0")" && pwd)
TPL="$D/assets/sterlings-life-lessons-01.mp4"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
python3 - "$2" "$TMP/card.png" <<'PY'
import sys
from PIL import Image
import numpy as np
im = Image.open(sys.argv[1]).convert('RGB')
a = np.asarray(im).astype(float); lo = a.min(axis=2, keepdims=True)
a = np.where(lo > 225, 255, a)  # pure-white paper
im = Image.fromarray(a.astype(np.uint8)); k = 700 / max(im.size)
im = im.resize((int(im.width * k), int(im.height * k)), Image.LANCZOS)
c = Image.new('RGB', (720, 1280), 'white'); c.paste(im, ((720 - im.width) // 2, (1280 - im.height) // 2)); c.save(sys.argv[2])
PY
python3 "$D/piano_bed.py" "$TMP/piano.wav" 21.6 "$PIANO"
if [ -n "$4" ]; then
  A="[4:a]aformat=sample_rates=44100:channel_layouts=stereo,loudnorm=I=-16:TP=-2:LRA=7,adelay=${T_VO}|${T_VO}[vo];
[3:a]aformat=sample_rates=44100:channel_layouts=stereo,volume=-9dB[mu];
[mu][vo]amix=inputs=2:duration=first:normalize=0,afade=t=out:st=20.6:d=0.9[a]"
else
  A='[3:a]aformat=sample_rates=44100:channel_layouts=stereo,loudnorm=I=-18:TP=-2,afade=t=out:st=20.6:d=0.9[a]'
fi
ffmpeg -v error -y -i "$1" -loop 1 -t 19.25 -i "$TMP/card.png" -ss 19.26 -i "$TPL" -i "$TMP/piano.wav" -i "${4:-$D/assets/silence.m4a}" -filter_complex "
[0:v]trim=$START:$(f "$START+8+$DELAY"),setpts=PTS-STARTPTS,scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,fps=24,format=yuv420p,
 fade=out:st=$(f "$T_IN+2.4"):d=0.1:color=white,tpad=stop_mode=add:stop_duration=$T_PAD:color=white[sc];
[1:v]fps=24,format=yuva420p,fade=in:st=$T_IN:d=2.5:alpha=1,fade=out:st=18:d=1:alpha=1[card];
[sc][card]overlay=0:0:format=auto,format=yuv420p,trim=0:19.25,setpts=PTS-STARTPTS[main];
[2:v]fps=24,format=yuv420p,setpts=PTS-STARTPTS[end];
[main][end]concat=n=2:v=1:a=0[v];
$A" -map "[v]" -map "[a]" -c:v libx264 -crf 18 -preset medium -pix_fmt yuv420p -c:a aac -b:a 192k -shortest -movflags +faststart "$3"

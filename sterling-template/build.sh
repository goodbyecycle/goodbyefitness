#!/bin/bash
# Build a Sterling's Life Lessons reel from a new scene clip + quote.
# usage: ./build.sh <scene.mp4> <quotes/name.txt | quotes/name.png> <out.mp4> [voiceover.mp3]
#   .txt -> rendered in Caveat Brush; .png -> used as-is (720x1280, transparent)
#   voiceover: ElevenLabs "Sterling" preset voice, starts at 4.5s over assets/music-bed.m4a
#
# Timeline (matches assets/sterlings-life-lessons-01.mp4):
#   0-4.5s    scene
#   4.5-8s    scene desaturates and fades to black while the pink quote fades in
#   8-18s     quote on black
#   18-19s    quote fades out
#   19.25s->  end card, taken straight from the template
#   audio     music bed (template music, voice removed) + voiceover from 4.5s
set -e
D=$(cd "$(dirname "$0")" && pwd)
TPL="$D/assets/sterlings-life-lessons-01.mp4"
CARD=$(mktemp --suffix=.png)
if [ -n "$4" ]; then
  VO='[4:a]aformat=sample_rates=44100:channel_layouts=stereo,loudnorm=I=-16:TP=-2:LRA=7,adelay=4500|4500[vo];
[3:a]aformat=sample_rates=44100:channel_layouts=stereo[mu];
[mu][vo]amix=inputs=2:duration=first:normalize=0,afade=t=out:st=20.6:d=0.9[a]'
else
  VO='[3:a]aformat=sample_rates=44100:channel_layouts=stereo,dynaudnorm=f=500:g=31,loudnorm=I=-18:TP=-2,afade=t=out:st=20.6:d=0.9[a]'
fi
case "$2" in
  *.png) cp "$2" "$CARD" ;;
  *) python3 "$D/textcard.py" "$2" "$CARD" ;;
esac
ffmpeg -v error -y -i "$1" -loop 1 -t 19.25 -i "$CARD" -ss 19.26 -i "$TPL" -i "$D/assets/music-bed.m4a" -i "${4:-$D/assets/silence.m4a}" -filter_complex "
[0:v]trim=0:8,setpts=PTS-STARTPTS,scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,fps=24,format=yuv420p,
 eq=eval=frame:saturation='if(lt(t,4.5),1,max(0,1-(t-4.5)/2.5))',
 fade=out:st=5.5:d=2.5,tpad=stop_mode=add:stop_duration=11.25:color=black[sc];
[1:v]format=rgba,fade=in:st=4.5:d=3:alpha=1,fade=out:st=18:d=1:alpha=1[tx];
[sc][tx]overlay=0:0:format=auto,format=yuv420p,trim=0:19.25,setpts=PTS-STARTPTS[main];
[2:v]fps=24,format=yuv420p,setpts=PTS-STARTPTS[end];
[main][end]concat=n=2:v=1:a=0[v];
$VO" \
 -map "[v]" -map "[a]" -c:v libx264 -crf 18 -preset medium -pix_fmt yuv420p -c:a aac -b:a 192k -shortest -movflags +faststart "$3"
rm -f "$CARD"

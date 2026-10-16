#!/bin/bash
# Build a Sterling's Life Lessons reel from a new scene clip + quote.
# usage: ./build.sh <scene.mp4> <quotes/name.txt> <out.mp4>
#
# Timeline (matches assets/sterlings-life-lessons-01.mp4):
#   0-4.5s    scene
#   4.5-8s    scene desaturates and fades to black while the pink quote fades in
#   8-18s     quote on black
#   18-19s    quote fades out
#   19.25s->  end card + music, taken straight from the template
set -e
D=$(cd "$(dirname "$0")" && pwd)
TPL="$D/assets/sterlings-life-lessons-01.mp4"
CARD=$(mktemp --suffix=.png)
python3 "$D/textcard.py" "$2" "$CARD"
ffmpeg -v error -y -i "$1" -loop 1 -t 19.25 -i "$CARD" -ss 19.26 -i "$TPL" -i "$TPL" -filter_complex "
[0:v]trim=0:8,setpts=PTS-STARTPTS,scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,fps=24,format=yuv420p,
 eq=eval=frame:saturation='if(lt(t,4.5),1,max(0,1-(t-4.5)/2.5))',
 fade=out:st=5.5:d=2.5,tpad=stop_mode=add:stop_duration=11.25:color=black[sc];
[1:v]format=rgba,fade=in:st=4.5:d=3:alpha=1,fade=out:st=18:d=1:alpha=1[tx];
[sc][tx]overlay=0:0:format=auto,format=yuv420p,trim=0:19.25,setpts=PTS-STARTPTS[main];
[2:v]fps=24,format=yuv420p,setpts=PTS-STARTPTS[end];
[main][end]concat=n=2:v=1:a=0[v]" \
 -map "[v]" -map 3:a -c:v libx264 -crf 18 -preset medium -pix_fmt yuv420p -c:a aac -b:a 192k -shortest -movflags +faststart "$3"
rm -f "$CARD"

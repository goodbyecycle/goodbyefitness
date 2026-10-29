// Panel cut points come from the stitched v4 voiceover (voiceover-v4.md).
export const FPS = 30;
export const TURN = 0.9;
export const VO_FILE = 'vo.mp3';

export const PANELS = [
  {src: 's01.jpg', start: 0, end: 14.6},
  {src: 's02.jpg', start: 14.6, end: 29.4, drift: -1},
  {src: 's03.jpg', start: 29.4, end: 33.9},
];
export const TOTAL = PANELS[PANELS.length - 1].end;

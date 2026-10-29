// Panel cut points come from the stitched v4 voiceover (voiceover-v4.md):
// each turn sits in the gap between two lines.
export const FPS = 30;
export const TURN = 0.9;
export const VO_FILE = 'vo.mp3';

export const PANELS = [
  {src: 's01.jpg', start: 0, end: 14.67},
  {src: 's02.jpg', start: 14.67, end: 29.41, drift: -1},
  {src: 's03.jpg', start: 29.41, end: 34.08},
  {src: 's04.jpg', start: 34.08, end: 36.19, drift: 1},
  {src: 's05.jpg', start: 36.19, end: 42.78},
  {src: 's06.jpg', start: 42.78, end: 49.03, drift: -1},
  {src: 's07.jpg', start: 49.03, end: 53.05},
  {src: 'A.jpg', start: 53.05, end: 61.31, drift: 1},
  {src: 's08.jpg', start: 61.31, end: 68.6},
  {src: 'B.jpg', start: 68.6, end: 72.86, drift: -1},
  {src: 'C.jpg', start: 72.86, end: 80.39},
  {src: 's14.jpg', start: 80.39, end: 85.77, drift: 1},
  {src: 's09.jpg', start: 85.77, end: 99.7},
  {src: 's11.jpg', start: 99.7, end: 108.03, drift: -1},
  {src: 'D.jpg', start: 108.03, end: 110.93},
  {src: 's12.jpg', start: 110.93, end: 124.15},
  {src: 's13.jpg', start: 124.15, end: 128.49, drift: 1},
  {src: 'E.jpg', start: 128.49, end: 136.3},
  // The card fades in after "young lady"; each sentence appears as it is read.
  {src: 'quote.jpg', start: 136.3, end: 149.6, enter: 'fade', still: true, bg: '#fff',
    reveal: [{t: 137.3, y0: 470, y1: 728}, {t: 140.3, y0: 728, y1: 974}, {t: 143.6, y0: 974, y1: 1470}]},
  {src: 'F.jpg', start: 149.6, end: 154.6, enter: 'fade'},
  {src: 'end.jpg', start: 154.6, end: 160, enter: 'fade', still: true},
];
export const TOTAL = PANELS[PANELS.length - 1].end;

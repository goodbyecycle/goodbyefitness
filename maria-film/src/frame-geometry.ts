/**
 * Measured true-content geometry of the 18 supplied storyboard frames.
 *
 * Each file is a 1920x1080 canvas, but the real artwork is a square or portrait
 * image centred inside blurred pillarbox bars. These are the measured content
 * boxes (detected by per-column high-frequency energy), kept here so the
 * outpaint/regeneration pass has exact numbers to work from.
 *
 * None of the 18 are natively 16:9. Until they are, image-to-video will animate
 * the blurred bars along with the artwork.
 */
export type Geometry = {id: number; x0: number; x1: number; width: number; aspect: number; barPct: number};

export const FRAME_GEOMETRY: Geometry[] = [
  {id:  1, x0: 416, x1: 1504, width: 1089, aspect: 1.008, barPct: 43.3},
  {id:  2, x0: 494, x1: 1424, width:  931, aspect: 0.862, barPct: 51.5},
  {id:  3, x0: 533, x1: 1373, width:  841, aspect: 0.779, barPct: 56.2},
  {id:  4, x0: 523, x1: 1308, width:  786, aspect: 0.728, barPct: 59.1},
  {id:  5, x0: 534, x1: 1384, width:  851, aspect: 0.788, barPct: 55.7},
  {id:  6, x0: 533, x1: 1386, width:  854, aspect: 0.791, barPct: 55.5},
  {id:  7, x0: 443, x1: 1478, width: 1036, aspect: 0.959, barPct: 46.0},
  {id:  8, x0: 529, x1: 1390, width:  862, aspect: 0.798, barPct: 55.1},
  {id:  9, x0: 344, x1: 1575, width: 1232, aspect: 1.141, barPct: 35.8},
  {id: 10, x0: 642, x1: 1276, width:  635, aspect: 0.588, barPct: 66.9},
  {id: 11, x0: 570, x1: 1348, width:  779, aspect: 0.721, barPct: 59.4},
  {id: 12, x0: 524, x1: 1394, width:  871, aspect: 0.806, barPct: 54.6},
  {id: 13, x0: 442, x1: 1480, width: 1039, aspect: 0.962, barPct: 45.9},
  {id: 14, x0: 436, x1: 1484, width: 1049, aspect: 0.971, barPct: 45.4},
  {id: 15, x0: 498, x1: 1420, width:  923, aspect: 0.855, barPct: 51.9},
  {id: 16, x0: 358, x1: 1561, width: 1204, aspect: 1.115, barPct: 37.3},
  {id: 17, x0: 364, x1: 1559, width: 1196, aspect: 1.107, barPct: 37.7},
  {id: 18, x0: 416, x1: 1503, width: 1088, aspect: 1.007, barPct: 43.3},
];

/**
 * MARIA - THE LONG WAY HERE
 * Single source of truth for scene timing.
 *
 * Durations are derived from the actual coffee-cup voiceover in the production
 * package (503 words / 97 lines / 18 ellipsis pauses), distributed across scenes
 * by the package's own per-scene "Edit / VO note" cues, then read at 145 wpm with
 * a 0.20s beat per line break, 0.35s extra per ellipsis, and 0.6s of headroom.
 *
 * The original package specified 150s. That target predates the VO: at any
 * natural narration pace the script cannot be read in 150s. Runtime extended.
 *
 * To retime the film, edit ONLY this file.
 */

export const FPS = 30;
export const WIDTH = 1920;
export const HEIGHT = 1080;

export type Scene = {
  /** 1-18, matches Scene_NN_YouTube_1920x1080.jpg */
  id: number;
  title: string;
  /** seconds */
  duration: number;
  /** VO line numbers from section 5 of the production package, inclusive */
  voLines: [number, number] | null;
};

export const SCENES: Scene[] = [
  {id:  1, title: 'Coffee at sunrise',                duration: 12.5, voLines: [1, 5]},
  {id:  2, title: 'Maria overlooking Copper Canyon',  duration: 11.0, voLines: [16, 18]},
  {id:  3, title: 'Train and bike travel',            duration:  6.0, voLines: [19, 19]},
  {id:  4, title: 'Maria on the train',               duration:  8.0, voLines: null},
  {id:  5, title: 'Maria meets Betty',                duration:  8.5, voLines: [20, 20]},
  {id:  6, title: 'Utah desert campsite',             duration:  4.5, voLines: [21, 21]},
  {id:  7, title: 'Maria at camp with coffee',        duration:  8.0, voLines: [22, 22]},
  {id:  8, title: 'Arrival at Blue Buffalo Stampede', duration: 17.0, voLines: [6, 11]},
  {id:  9, title: 'The women study the line',         duration: 14.0, voLines: [12, 15]},
  {id: 10, title: 'Maria looks toward the jump',      duration: 23.0, voLines: [23, 30]},
  {id: 11, title: 'Helmet / commitment close-up',     duration: 23.5, voLines: [31, 39]},
  // 30.0 is the Seedance 2.5 per-generation ceiling; VO for this block wants 31.0.
  // The half-second is absorbed by the head of scene 13.
  {id: 12, title: 'Maria starts the run',             duration: 30.0, voLines: [40, 54]},
  {id: 13, title: 'Takeoff',                          duration:  8.0, voLines: [55, 56]},
  {id: 14, title: 'Off-axis backflip',                duration: 18.5, voLines: [57, 65]},
  {id: 15, title: 'Landing and ride-out',             duration:  9.5, voLines: [66, 71]},
  {id: 16, title: 'The four women celebrate',         duration:  8.0, voLines: [72, 75]},
  {id: 17, title: 'Back at the table',                duration: 20.5, voLines: [76, 85]},
  {id: 18, title: 'Coffee-cup sunset ending',         duration: 27.5, voLines: [86, 97]},
];

export const frames = (seconds: number) => Math.round(seconds * FPS);

/** Cumulative start frame for each scene. */
export const TIMELINE = SCENES.reduce<{scene: Scene; from: number; durationInFrames: number}[]>(
  (acc, scene) => {
    const prev = acc[acc.length - 1];
    const from = prev ? prev.from + prev.durationInFrames : 0;
    acc.push({scene, from, durationInFrames: frames(scene.duration)});
    return acc;
  },
  [],
);

export const TOTAL_FRAMES = TIMELINE.reduce((n, s) => n + s.durationInFrames, 0);

/** Padded scene number: 1 -> "01" */
export const pad = (id: number) => String(id).padStart(2, '0');

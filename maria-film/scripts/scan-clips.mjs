import {readdirSync, writeFileSync, existsSync} from 'node:fs';

const clipDir = 'public/clips';
const found = existsSync(clipDir)
  ? readdirSync(clipDir)
      .map((f) => f.match(/^Scene_(\d{2})\.mp4$/))
      .filter(Boolean)
      .map((m) => Number(m[1]))
      .sort((a, b) => a - b)
  : [];

const hasNarration = existsSync('public/audio/narration.mp3');
const hasMusic = existsSync('public/audio/music.mp3');

writeFileSync(
  'src/clips-manifest.ts',
  `/**
 * GENERATED - do not edit by hand. Run \`npm run scan\` after dropping assets in.
 *
 *   public/clips/Scene_01.mp4 ... Scene_18.mp4   Seedance clips
 *   public/audio/narration.mp3                   ElevenLabs VO (timing spine)
 *   public/audio/music.mp3                       score bed
 *
 * Scenes listed here render their clip; every other scene falls back to the
 * storyboard still, so the composition renders as a correctly-timed animatic
 * before any clip exists.
 */
export const AVAILABLE_CLIPS: number[] = [${found.join(', ')}];
export const HAS_NARRATION = ${hasNarration};
export const HAS_MUSIC = ${hasMusic};
`,
);

console.log(
  `clips ${found.length}/18${found.length ? ' (' + found.join(', ') + ')' : ''} | ` +
    `narration ${hasNarration ? 'yes' : 'no'} | music ${hasMusic ? 'yes' : 'no'}`,
);

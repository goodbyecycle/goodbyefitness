import React from 'react';
import {AbsoluteFill, Audio, Sequence, staticFile} from 'remotion';
import {FPS, TIMELINE, TOTAL_FRAMES} from './edit-map';
import {AVAILABLE_CLIPS, HAS_MUSIC, HAS_NARRATION} from './clips-manifest';
import {Scene} from './Scene';
import {EndTitles} from './EndTitles';

/** Music sits 8 dB under narration once the VO exists; ~0.4 -> ~0.16 linear. */
const MUSIC_BED = 0.4;
const MUSIC_DUCKED = 0.16;

export const Maria: React.FC = () => {
  const last = TIMELINE[TIMELINE.length - 1];

  return (
    <AbsoluteFill style={{backgroundColor: '#0A0A0A'}}>
      {TIMELINE.map(({scene, from, durationInFrames}) => (
        <Sequence
          key={scene.id}
          from={from}
          durationInFrames={durationInFrames}
          name={`${String(scene.id).padStart(2, '0')} ${scene.title}`}
        >
          <Scene scene={scene} durationInFrames={durationInFrames} />
        </Sequence>
      ))}

      {/*
        Titles ride the tail of scene 18. The package requires the cup to hold
        nearly still for the final 2s, so the first line lands 6s before the end.
      */}
      <Sequence from={last.from} durationInFrames={last.durationInFrames} name="End titles">
        <EndTitles
          startFrame={last.durationInFrames - Math.round(FPS * 6)}
          sceneDuration={last.durationInFrames}
        />
      </Sequence>

      {/* Narration is the master timing track - everything else syncs to it. */}
      {HAS_NARRATION ? <Audio src={staticFile('audio/narration.mp3')} /> : null}
      {HAS_MUSIC ? (
        <Audio
          src={staticFile('audio/music.mp3')}
          volume={HAS_NARRATION ? MUSIC_DUCKED : MUSIC_BED}
        />
      ) : null}
    </AbsoluteFill>
  );
};

export const meta = {
  totalFrames: TOTAL_FRAMES,
  clipsReady: AVAILABLE_CLIPS.length,
};

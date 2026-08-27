import React from 'react';
import {AbsoluteFill, Img, OffthreadVideo, staticFile, useCurrentFrame, interpolate} from 'remotion';
import {pad, type Scene as SceneType} from './edit-map';
import {AVAILABLE_CLIPS} from './clips-manifest';

/**
 * One scene. Renders the Seedance clip when it exists, otherwise the storyboard
 * still with a slow push so the animatic reads as motion rather than a slideshow.
 */
export const Scene: React.FC<{scene: SceneType; durationInFrames: number}> = ({
  scene,
  durationInFrames,
}) => {
  const frame = useCurrentFrame();
  const hasClip = AVAILABLE_CLIPS.includes(scene.id);

  if (hasClip) {
    return (
      <AbsoluteFill style={{backgroundColor: '#0A0A0A'}}>
        <OffthreadVideo src={staticFile(`clips/Scene_${pad(scene.id)}.mp4`)} />
      </AbsoluteFill>
    );
  }

  // Animatic fallback: 1.0 -> 1.06 push across the scene.
  const scale = interpolate(frame, [0, durationInFrames], [1, 1.06], {
    extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill style={{backgroundColor: '#0A0A0A'}}>
      <Img
        src={staticFile(`frames/Scene_${pad(scene.id)}_YouTube_1920x1080.jpg`)}
        style={{width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${scale})`}}
      />
    </AbsoluteFill>
  );
};

import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {FPS} from './edit-map';

const LINE_ONE = 'BECAUSE EVERY COFFEE HAS A STORY.';
const LINE_TWO = 'AND THIS ONE BELONGED TO MARIA.';

/**
 * Overlaid on the tail of scene 18. The package requires the cup to hold nearly
 * still for at least the final 2s, and titles no more elaborate than a gentle fade.
 *
 * `startFrame` is relative to the start of scene 18.
 */
export const EndTitles: React.FC<{startFrame: number; sceneDuration: number}> = ({
  startFrame,
  sceneDuration,
}) => {
  const frame = useCurrentFrame();
  const fade = Math.round(FPS * 0.8);

  const one = interpolate(frame, [startFrame, startFrame + fade], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const twoStart = startFrame + Math.round(FPS * 2.6);
  const two = interpolate(frame, [twoStart, twoStart + fade], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  // Both lines fade out together over the last 1.2s of the film.
  const outStart = sceneDuration - Math.round(FPS * 1.2);
  const out = interpolate(frame, [outStart, sceneDuration], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const base: React.CSSProperties = {
    color: '#F2EDE4',
    fontFamily: 'Helvetica, Arial, sans-serif',
    fontSize: 46,
    letterSpacing: 4,
    textAlign: 'center',
  };

  return (
    <AbsoluteFill
      style={{justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 140, gap: 22}}
    >
      <div style={{...base, opacity: one * out}}>{LINE_ONE}</div>
      <div style={{...base, opacity: two * out}}>{LINE_TWO}</div>
    </AbsoluteFill>
  );
};

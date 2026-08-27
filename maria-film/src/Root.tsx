import React from 'react';
import {Composition} from 'remotion';
import {FPS, HEIGHT, TOTAL_FRAMES, WIDTH} from './edit-map';
import {Maria} from './Maria';

export const RemotionRoot: React.FC = () => (
  <Composition
    id="Maria"
    component={Maria}
    durationInFrames={TOTAL_FRAMES}
    fps={FPS}
    width={WIDTH}
    height={HEIGHT}
  />
);

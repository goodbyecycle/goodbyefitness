import {registerRoot, Composition} from 'remotion';
import {Book} from './Book';
import {PANELS, FPS, TOTAL} from './timeline';

const Root = () => (
  <>
    <Composition id="Ep2" component={Book} fps={FPS} width={1080} height={1920}
      durationInFrames={Math.round(TOTAL * FPS)} defaultProps={{panels: PANELS}} />
    <Composition id="Ep2Preview" component={Book} fps={FPS} width={1080} height={1920}
      durationInFrames={33 * FPS} defaultProps={{panels: PANELS}} />
  </>
);
registerRoot(Root);

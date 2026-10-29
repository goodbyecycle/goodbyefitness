import {AbsoluteFill, Img, Audio, Sequence, staticFile, useCurrentFrame, useVideoConfig, interpolate, Easing} from 'remotion';
import {TURN, VO_FILE} from './timeline';
import {CAPTIONS} from './captions';

// One still: slow push in with a little drift so the page never feels frozen.
const Panel = ({p, t}) => {
  const k = Math.min(1, Math.max(0, (t - p.start) / (p.end - p.start)));
  const s = 1.04 + 0.07 * k;
  const dx = (p.drift ?? 0) * 30 * k;
  return (
    <AbsoluteFill style={{background: p.bg ?? '#000', overflow: 'hidden'}}>
      <Img src={staticFile(p.src)} style={{width: '100%', height: '100%', objectFit: p.fit ?? 'cover',
        transform: p.still ? 'none' : `scale(${s}) translateX(${dx}px)`}} />
      {p.reveal?.map((r) => (
        <div key={r.t} style={{position: 'absolute', left: 0, right: 0, top: r.y0, height: r.y1 - r.y0,
          background: p.bg, opacity: interpolate(t, [r.t, r.t + 0.6], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}} />
      ))}
    </AbsoluteFill>
  );
};

// Film grain over everything.
const Grain = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{mixBlendMode: 'overlay', opacity: 0.22, pointerEvents: 'none'}}>
      <svg width="100%" height="100%">
        <filter id="g"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed={f % 30} /></filter>
        <rect width="100%" height="100%" filter="url(#g)" />
      </svg>
    </AbsoluteFill>
  );
};

// The page on top lifts from the right edge and swings over the spine (left edge).
const Turn = ({from, to, t, p}) => {
  const e = Easing.inOut(Easing.cubic)(p);
  const angle = -180 * e;
  const shade = Math.sin(Math.PI * e);
  return (
    <AbsoluteFill style={{perspective: 2600}}>
      <Panel p={to} t={t} />
      <AbsoluteFill style={{background: `linear-gradient(90deg, rgba(0,0,0,${0.55 * shade}) 0%, rgba(0,0,0,0) ${30 + 60 * e}%)`}} />
      <AbsoluteFill style={{transformOrigin: 'left center', transform: `rotateY(${angle}deg)`,
        backfaceVisibility: 'hidden', boxShadow: `${-40 * shade}px 0 80px rgba(0,0,0,${0.7 * shade})`}}>
        <Panel p={from} t={t} />
        <AbsoluteFill style={{background: `linear-gradient(270deg, rgba(255,255,255,${0.18 * shade}) 0%, rgba(0,0,0,${0.45 * shade}) 100%)`}} />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// Subtitles: royal blue words with a thick white outline, lower third.
const Captions = ({t}) => {
  const c = CAPTIONS.find((x) => t >= x.s && t < x.e);
  if (!c) return null;
  const pop = interpolate(t, [c.s, c.s + 0.12], [0.9, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{justifyContent: 'flex-start', alignItems: 'center', paddingTop: 1300}}>
      <div style={{maxWidth: 920, textAlign: 'center', fontFamily: 'Montserrat', fontWeight: 800, fontSize: 82,
        lineHeight: 1.12, color: '#1f45ff', WebkitTextStroke: '14px #fff', paintOrder: 'stroke fill',
        filter: 'drop-shadow(0 6px 10px rgba(0,0,0,0.55))', transform: `scale(${pop})`}}>{c.text}</div>
    </AbsoluteFill>
  );
};

export const Book = ({panels}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  let i = panels.findIndex((p) => t < p.end);
  if (i < 0) i = panels.length - 1;
  const cur = panels[i];
  const next = panels[i + 1];
  const prev = panels[i - 1];
  const turns = (p) => p && (p.enter ?? 'turn') === 'turn';
  let body;
  if (turns(next) && t > cur.end - TURN / 2) {
    body = <Turn from={cur} to={next} t={t} p={(t - (cur.end - TURN / 2)) / TURN} />;
  } else if (prev && turns(cur) && t < cur.start + TURN / 2) {
    body = <Turn from={prev} to={cur} t={t} p={(t - (cur.start - TURN / 2)) / TURN} />;
  } else {
    const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'};
    const fadeIn = cur.enter === 'fade' ? interpolate(t, [cur.start, cur.start + 1.2], [0, 1], clamp) : 1;
    const fadeOut = next && next.enter === 'fade' ? interpolate(t, [cur.end - 1.2, cur.end], [1, 0], clamp) : 1;
    body = <AbsoluteFill style={{opacity: fadeIn * fadeOut}}><Panel p={cur} t={t} />{cur.overlay?.(t)}</AbsoluteFill>;
  }
  return (
    <AbsoluteFill style={{background: '#000'}}>
      {body}
      {/* grain added in ffmpeg after render */}
      <Captions t={t} />
      <Audio src={staticFile(VO_FILE)} />
      {panels.slice(1).map((p) => (p.enter ?? 'turn') === 'turn' ? (
        <Sequence key={p.src + p.start} from={Math.round((p.start - TURN / 2) * fps)} durationInFrames={fps * 2}>
          <Audio src={staticFile('flip.wav')} volume={0.55} />
        </Sequence>
      ) : null)}
    </AbsoluteFill>
  );
};

// A generic scene that renders with any timeline: every keyword lands as a card on its word.
// It is the place to start, not the film: replace it with scenes that draw each keyword's verb.
import React from 'react';
import {AbsoluteFill, Audio, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {Caption} from './comp/Caption';
import {BEATS} from './beats';
import {E, life, ramp, springTo} from './lib/anim';

export const PAPER = '#F4EFE5', INK = '#1F1D1A', BLUE = '#2E49D4';

export const Main: React.FC = () => {
  const {fps, width, height} = useVideoConfig();
  const t = useCurrentFrame() / fps;
  const s = Math.min(width, height) / 1080;
  return (
    <AbsoluteFill style={{background: PAPER}}>
      <Audio src={staticFile('narration.wav')} />
      {BEATS.map((b, i) => {
        const seen = life(t, b.appear, b.leave);
        if (seen <= 0) return null;
        // Slides in from below and settles exactly on the beat, with about 3% overshoot.
        const drop = springTo(t, b.land - 0.4, b.land);
        const ring = ramp(t, b.land, 0.5, E.enter);
        return (
          <div
            key={i}
            style={{
              position: 'absolute',
              left: width / 2,
              top: height * 0.44,
              transform: `translate(-50%, -50%) translateY(${(1 - drop) * 140 * s}px)`,
              opacity: seen,
            }}
          >
            <div
              style={{
                position: 'absolute',
                inset: -24 * s * ring,
                border: `${4 * s}px solid ${BLUE}`,
                borderRadius: 36 * s,
                opacity: (1 - ring) * 0.8,
              }}
            />
            <div
              style={{
                padding: `${36 * s}px ${72 * s}px`,
                borderRadius: 28 * s,
                background: '#FFFFFF',
                border: `${5 * s}px solid ${INK}`,
                color: drop > 0.5 ? BLUE : INK,
                fontFamily: '"Noto Sans SC", "Noto Sans CJK SC", "PingFang SC", "Microsoft YaHei", sans-serif',
                fontSize: 120 * s,
                fontWeight: 700,
                whiteSpace: 'nowrap',
              }}
            >
              {b.word}
            </div>
          </div>
        );
      })}
      <Caption t={t} />
    </AbsoluteFill>
  );
};

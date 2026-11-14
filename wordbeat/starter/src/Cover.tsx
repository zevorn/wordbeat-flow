// The cover still: one subject and one line, centered so a 4:3 crop of a 16:9 cover keeps it.
// Replace the line with the film's own, drawn in the film's own style.
import React from 'react';
import {AbsoluteFill, useVideoConfig} from 'remotion';
import {BLUE, INK, PAPER} from './Main';
import {keywords} from './lib/time';

export const Cover: React.FC = () => {
  const {width, height} = useVideoConfig();
  const s = Math.min(width, height) / 1080;
  return (
    <AbsoluteFill style={{background: PAPER, alignItems: 'center', justifyContent: 'center'}}>
      <div
        style={{
          maxWidth: Math.min(width, (height * 4) / 3) * 0.8,
          textAlign: 'center',
          color: INK,
          fontFamily: '"Noto Sans SC", "Noto Sans CJK SC", "PingFang SC", "Microsoft YaHei", sans-serif',
          fontSize: 140 * s,
          fontWeight: 800,
          lineHeight: 1.2,
        }}
      >
        <span style={{color: BLUE}}>{keywords[0]?.word ?? ''}</span>
      </div>
    </AbsoluteFill>
  );
};

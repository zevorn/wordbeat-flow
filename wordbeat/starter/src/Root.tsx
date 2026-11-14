import React from 'react';
import {Composition, Still} from 'remotion';
import {Cover} from './Cover';
import {Main} from './Main';
import FRAME from './data/frame.json';
import {tl} from './lib/time';

export const FPS = 60;

// The film is exactly as long as the timeline, so picture and voice always end together.
// frame.json holds the width and height the flow's orientation param asks for.
export const Root: React.FC = () => (
  <>
    <Composition
      id="Main"
      component={Main}
      durationInFrames={Math.ceil(tl.total * FPS)}
      fps={FPS}
      width={FRAME.width}
      height={FRAME.height}
    />
    <Still id="Cover" component={Cover} width={FRAME.width} height={FRAME.height} />
  </>
);

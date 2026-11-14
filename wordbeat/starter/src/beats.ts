// The beat table: the moment every motion lands. The picture (Main.tsx) and the sound effects
// (scripts/cues.ts) both read their times from here, so sound and picture share one clock.
// Rules: land a motion with hit(); show a new element no later than appearBy(); motions take
// 0.25 to 0.5 s. Replace this generic table with the film's own beats.
import {APPEAR, LEAD, keywords} from './lib/time';

// One beat per keyword of the script: the card for it appears early enough to be seen and lands
// 3 frames before the word is spoken.
export const BEATS = keywords.map((k, i) => ({
  word: k.word,
  appear: k.t - APPEAR - 0.35,
  land: k.t - LEAD,
  leave: i + 1 < keywords.length ? keywords[i + 1].t - APPEAR - 0.35 : k.e + 2,
}));

// Sound cues: t is when the sound's peak must land; kind is a folder under audio/sfx/.
export type Cue = {t: number; kind: string; gain: number; pan?: number};
export const CUES: Cue[] = BEATS.flatMap((b) => [
  {t: b.appear + 0.15, kind: 'soft_in', gain: -16},
  {t: b.land, kind: 'pop', gain: -10},
]);

// Recorded sounds played as they are (a demo, an A/B example): src is a path under public/,
// from where in the file to start, dur how long, gain in dB after matching the narration.
export type Clip = {t: number; src: string; from?: number; dur?: number; gain?: number};
export const CLIPS: Clip[] = [];

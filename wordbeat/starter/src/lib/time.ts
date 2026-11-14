// The timing API: every moment tied to the narration comes from timeline.json, never from a
// count of characters. timeline.py writes it: each line's start and end, each spoken unit's
// start and end (one Chinese character, or one English or numeric word), and the keywords.
import TL from '../data/timeline.json';

export type Word = {u: string; s: number; e: number};
export type Cap = {c: string; s: number; e: number; k?: number};
export type Line = {
  i: number;
  sec: string | null;
  start: number;
  end: number;
  pause: number;
  say: string;
  show: string;
  real: boolean;
  words: Word[];
  cap: Cap[];
};
export type Keyword = {line: number; word: string; t: number; e: number};

export const tl = TL as unknown as {
  fps: number;
  total: number;
  lines: Line[];
  sections: Record<string, {start: number; end: number; first: number; last: number}>;
  gaps: {name: string; start: number; end: number}[];
  keywords: Keyword[];
};
export const lines = tl.lines;
export const keywords = tl.keywords ?? [];

// ---- Timing constants at 60 fps ----
// A motion lands 3 frames (50 ms) before its keyword's first character. ITU-R BT.1359: sound
// ahead by about 45 ms is noticed, picture ahead only at about 125 ms, so early beats late.
export const LEAD = 3 / 60;
// Tolerance: 6 frames early to 1 frame late.
export const LEAD_MIN = -1 / 60,
  LEAD_MAX = 6 / 60;
// A new element's first frame comes at least 12 frames before its keyword: the eye needs about
// 200 ms to get there.
export const APPEAR = 12 / 60;

// Spoken units, split as timeline.py splits them.
export const splitUnits = (s: string) => s.match(/[A-Za-z0-9][A-Za-z0-9.\-']*|[㐀-鿿]/g) ?? [];

// The n-th line (from 0) containing text. Throws when there is none: never a made-up time.
export const line = (text: string, n = 0) => {
  const ls = lines.filter((l) => l.say.includes(text) || l.show.includes(text));
  if (!ls[n]) throw new Error(`no line number ${n} contains "${text}"`);
  return ls[n];
};

const find = (l: Line, word: string, n: number, edge: 's' | 'e', counted: {k: number}) => {
  const units = l.words.map((w) => w.u.toLowerCase());
  const target = splitUnits(word).map((u) => u.toLowerCase());
  for (let i = 0; i + target.length <= units.length; i++) {
    if (target.every((u, j) => units[i + j] === u)) {
      if (counted.k === n) return edge === 's' ? l.words[i].s : l.words[i + target.length - 1].e;
      counted.k++;
    }
  }
  return null;
};

// A word within one line: edge 's' is its first unit's start, 'e' its last unit's end.
export const atIn = (l: Line, word: string, n = 0, edge: 's' | 'e' = 's') => {
  const t = find(l, word, n, edge, {k: 0});
  if (t === null) throw new Error(`line ${l.i} has no occurrence ${n} of "${word}"`);
  return t;
};

// The n-th occurrence of a word in the whole film.
export const at = (word: string, n = 0, edge: 's' | 'e' = 's') => {
  const counted = {k: 0};
  for (const l of lines) {
    const t = find(l, word, n, edge, counted);
    if (t !== null) return t;
  }
  throw new Error(`the film has no occurrence ${n} of "${word}"`);
};

// When a motion must land.
export const hit = (word: string, n = 0) => at(word, n) - LEAD;
// When a new element must have appeared.
export const appearBy = (word: string, n = 0) => at(word, n) - APPEAR;
// A keyword marked with *asterisks* in the script.
export const kw = (word: string) => {
  const k = keywords.find((x) => x.word === word);
  if (!k) throw new Error(`the script marks no keyword "${word}"`);
  return k;
};

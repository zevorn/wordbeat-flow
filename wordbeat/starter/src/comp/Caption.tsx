// Captions: each character darkens when it is heard, and the keyword changes color.
// Chinese: lines are cut at punctuation into captions of at most 16 characters (the Netflix
// simplified Chinese limit); commas and full stops are dropped, ? and ! kept.
// English: cut at punctuation, long phrases cut again between words, about 54 characters at
// most, a keyword never split; commas inside a caption stay.
// Both switch on the narration as it is heard: a caption is not replaced before its voice has
// died away, and the next one is up just before its voice starts.
import React from 'react';
import {useVideoConfig} from 'remotion';
import FRAME from '../data/frame.json';
import VOICE from '../data/voice_loud.json';
import {E, clamp, inv, lerp} from '../lib/anim';
import {type Cap, lines} from '../lib/time';

const EN = (FRAME as {lang?: string}).lang === 'en';
export type Chunk = {chars: Cap[]; show: number; hide: number; first: number};
const MAX = EN ? 30 : 16;
const BREAK = new Set('，。？！；：、,.?!;:');
const DROP = new Set('。，、；：,.;:');
const width = (cs: Cap[]) => cs.reduce((a, c) => a + (/[A-Za-z0-9 .\-'":]/.test(c.c) ? 0.55 : BREAK.has(c.c) ? 0 : 1), 0);

// Where the narration is audible, in 10 ms steps: the flow writes it with voice_loud.py, measured
// as caption_check.py measures it. Empty, the captions follow the aligner's times alone.
const HOP = (VOICE as {hop: number}).hop;
const LOUD = (VOICE as {loud: string}).loud;
const N = LOUD.length;
const loud = (k: number) => LOUD.charCodeAt(k) === 49;
// Where the voice starts near t: step back into silence, then forward to the first audible step.
const onsetNear = (t: number, back = 0.25, fwd = 0.25): number | null => {
  const i0 = Math.max(0, Math.floor((t - back) / HOP)),
    i1 = Math.min(N, Math.floor((t + fwd) / HOP));
  let k = i0;
  while (k < i1 && loud(k)) k++;
  while (k < i1 && !loud(k)) k++;
  return k < i1 ? k * HOP : null;
};
// Where the voice dies away near t: the last audible step before t + fwd.
const offsetNear = (t: number, fwd = 0.3, back = 0.25): number | null => {
  const i0 = Math.max(0, Math.floor((t - back) / HOP)),
    i1 = Math.min(N, Math.floor((t + fwd) / HOP));
  let k = i1 - 1;
  while (k > i0 && !loud(k)) k--;
  return k > i0 ? (k + 1) * HOP : null;
};
// A clear onset within 0.15 s of t: silence, then at least 0.1 s of voice. A breath or a lip noise
// of a few tens of milliseconds does not count.
const voicedOnset = (t: number): number | null => {
  const i0 = Math.max(0, Math.floor((t - 0.15) / HOP)),
    i1 = Math.min(N, Math.floor((t + 0.15) / HOP));
  for (let k = i0 + 1; k < i1; k++) {
    if (loud(k) && !loud(k - 1)) {
      let run = 0;
      while (k + run < N && loud(k + run)) run++;
      if (run * HOP >= 0.1) return k * HOP;
    }
  }
  return null;
};

// One line as phrases, each ending at punctuation. A title in 《》 stays whole, and in English a
// colon ends a phrase only before a lowercase word, not inside a name.
const phrasesOf = (cap: Cap[]) => {
  const phrases: Cap[][] = [];
  let cur: Cap[] = [];
  let inTitle = 0;
  const nextWord = (i: number) => cap.slice(i + 1).find((x) => x.c !== ' ')?.c ?? '';
  cap.forEach((c, i) => {
    if (c.c === '《') {
      if (cur.length) phrases.push(cur);
      cur = [];
      inTitle++;
    }
    if (c.c === '》') inTitle = Math.max(0, inTitle - 1);
    cur.push(c);
    const nameColon = EN && c.c === ':' && /[A-Z]/.test(nextWord(i));
    if (BREAK.has(c.c) && !inTitle && !nameColon) {
      phrases.push(cur);
      cur = [];
    }
  });
  if (cur.length) phrases.push(cur);
  return phrases;
};
// English words, each keeping the space after it.
const toWords = (p: Cap[]) => {
  const ws: Cap[][] = [];
  let cur: Cap[] = [];
  for (const c of p) {
    cur.push(c);
    if (c.c === ' ') {
      ws.push(cur);
      cur = [];
    }
  }
  if (cur.length) ws.push(cur);
  return ws;
};
const trim = (cs: Cap[]) => {
  let a = 0,
    b = cs.length;
  while (a < b && cs[a].c === ' ') a++;
  while (b > a && cs[b - 1].c === ' ') b--;
  return cs.slice(a, b);
};

const chunksOf = (cap: Cap[]): Cap[][] => {
  const out: Cap[][] = [];
  let acc: Cap[] = [];
  const flush = () => {
    const c = trim(acc);
    if (c.length) out.push(c);
    acc = [];
  };
  for (const p of phrasesOf(cap)) {
    if (width(acc) + width(p) <= MAX) acc = acc.concat(p);
    else {
      flush();
      if (width(p) <= MAX) acc = p;
      else if (!EN)
        for (let i = 0; i < p.length; i += MAX) {
          acc = p.slice(i, i + MAX);
          flush();
        }
      else {
        // A long English phrase fills captions word by word, as evenly as it can, never splitting
        // a keyword.
        const ws = toWords(p);
        const target = width(p) / Math.ceil(width(p) / MAX);
        for (const w of ws) {
          const keepTogether = acc.length > 0 && !!acc[acc.length - 1].k && !!w[0].k;
          const tooLong = width(acc) + width(w) > MAX;
          const balanced = width(acc) >= target && width(acc) + width(w) > target * 1.1;
          if (acc.length && (tooLong || (balanced && !keepTogether))) flush();
          acc = acc.concat(w);
        }
      }
    }
  }
  flush();
  return out;
};

const visible = (cs: Cap[]) => cs.filter((c) => !BREAK.has(c.c) && c.c !== ' ');

const build = (): Chunk[] => {
  const out: Chunk[] = lines.flatMap((l) => chunksOf(l.cap)).map((chars) => ({chars, show: 0, hide: 0, first: 0}));
  for (const ch of out) {
    const v = visible(ch.chars);
    ch.show = (v[0] ?? ch.chars[0]).s - 0.1;
    ch.hide = (v[v.length - 1] ?? ch.chars[0]).e + 0.7;
    // The first character lights when its voice is heard: where the aligner puts it more than
    // 0.08 s before a clear onset, it lights from that onset instead.
    const s = (v[0] ?? ch.chars[0]).s;
    const on = voicedOnset(s);
    ch.first = on !== null && on - s > 0.08 ? on - 0.04 : s;
  }
  // The first caption is up before its voice is audible.
  const f0 = out[0] ? visible(out[0].chars)[0] : undefined;
  const on0 = f0 ? onsetNear(f0.s) : null;
  if (on0 !== null) out[0].show = Math.min(out[0].show, on0 - 0.05);
  // A caption never replaces the previous one before that one's last character has been heard
  // out; the aligner's end times run a few tens of milliseconds early, hence the 0.08 s.
  for (let i = 1; i < out.length; i++) {
    const pv = visible(out[i - 1].chars);
    const lastEnd = (pv[pv.length - 1] ?? out[i - 1].chars[0]).e;
    const first = out[i].first;
    out[i].show = Math.max(out[i].show, Math.min(lastEnd + 0.08, first - 0.02));
    // Then on the voice itself: up before the next phrase is audible, never before the previous
    // phrase has died away.
    const on = onsetNear(first);
    if (on !== null) out[i].show = Math.min(out[i].show, on - 0.05);
    const off = offsetNear(lastEnd, Math.max(0.02, Math.min(0.3, first - 0.03 - lastEnd)));
    if (off !== null) out[i].show = Math.max(out[i].show, off);
  }
  for (let i = 0; i < out.length - 1; i++) {
    out[i].hide = Math.min(out[i].hide, out[i + 1].show);
    // Less than 0.25 s apart: run straight on instead of blinking empty.
    if (out[i + 1].show - out[i].hide < 0.25) out[i].hide = out[i + 1].show;
  }
  return out;
};
export const CHUNKS = build();

// What scripts/caps.ts exports for caption_check.py --caps: the text each caption shows and when.
export const captionTimes = () =>
  CHUNKS.map((ch) => {
    const v = visible(ch.chars);
    return {
      text: ch.chars.map((c) => c.c).join(''),
      show: ch.show,
      hide: ch.hide,
      first: ch.first,
      last: (v[v.length - 1] ?? ch.chars[0]).e,
    };
  });

export const Caption: React.FC<{t: number; ink?: string; key_?: string; band?: string; font?: string}> = ({
  t,
  ink = '#1F1D1A',
  key_ = '#2E49D4',
  band = 'rgba(251,248,241,0.9)',
  font = '"Noto Sans SC", "Noto Sans CJK SC", "PingFang SC", "Microsoft YaHei", sans-serif',
}) => {
  const {width: w, height: h} = useVideoConfig();
  const s = Math.min(w, h) / 1080;
  const ch = CHUNKS.find((c) => t >= c.show && t < c.hide);
  if (!ch) return null;
  const vis = E.smooth(inv(ch.show, ch.show + 0.1, t));
  const chars = ch.chars.filter((c, i, a) => !(DROP.has(c.c) && i === a.length - 1));
  return (
    <div
      style={{
        position: 'absolute',
        left: w / 2,
        top: h - 74 * s,
        transform: 'translate(-50%, -50%)',
        opacity: vis,
        padding: `${10 * s}px ${30 * s}px ${12 * s}px`,
        borderRadius: 14 * s,
        background: band,
        fontFamily: font,
        fontSize: 44 * s,
        lineHeight: 1.25,
        whiteSpace: EN ? 'pre' : 'nowrap',
      }}
    >
      {chars.map((c, i) => {
        if (!EN && DROP.has(c.c)) return <span key={i} style={{display: 'inline-block', width: '0.6em'}} />;
        const k = clamp((t - Math.max(c.s, ch.first) + 0.03) / 0.08);
        return (
          <span key={i} style={{color: c.k && k > 0 ? key_ : ink, opacity: lerp(0.42, 1, k)}}>
            {c.c}
          </span>
        );
      })}
    </div>
  );
};

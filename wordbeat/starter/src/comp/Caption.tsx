// Captions: each character darkens when it is spoken, and the keyword changes color.
// Long lines are cut at punctuation into captions of at most 16 characters (the Netflix
// simplified Chinese limit); commas and full stops are dropped, ? and ! are kept.
import React from 'react';
import {useVideoConfig} from 'remotion';
import {E, clamp, inv, lerp} from '../lib/anim';
import {type Cap, lines} from '../lib/time';

export type Chunk = {chars: Cap[]; show: number; hide: number};
const MAX = 16;
const BREAK = new Set('，。？！；：、,.?!;:');
const DROP = new Set('。，、；：,.;:');
const width = (cs: Cap[]) => cs.reduce((a, c) => a + (/[A-Za-z0-9 .\-']/.test(c.c) ? 0.55 : BREAK.has(c.c) ? 0 : 1), 0);

const build = (): Chunk[] => {
  const out: Chunk[] = [];
  for (const l of lines) {
    const phrases: Cap[][] = [];
    let cur: Cap[] = [];
    for (const c of l.cap) {
      cur.push(c);
      if (BREAK.has(c.c)) {
        phrases.push(cur);
        cur = [];
      }
    }
    if (cur.length) phrases.push(cur);
    let acc: Cap[] = [];
    const flush = () => {
      if (acc.length) out.push({chars: acc, show: 0, hide: 0});
      acc = [];
    };
    for (const p of phrases) {
      if (width(acc) + width(p) <= MAX) acc = acc.concat(p);
      else {
        flush();
        if (width(p) <= MAX) acc = p;
        else
          for (let i = 0; i < p.length; i += MAX) {
            acc = p.slice(i, i + MAX);
            flush();
          }
      }
    }
    flush();
  }
  for (const ch of out) {
    const v = ch.chars.filter((c) => !BREAK.has(c.c));
    ch.show = (v[0] ?? ch.chars[0]).s - 0.1;
    ch.hide = (v[v.length - 1] ?? ch.chars[0]).e + 0.7;
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
    const spoken = ch.chars.filter((c) => !BREAK.has(c.c));
    return {
      text: ch.chars.map((c) => c.c).join(''),
      show: ch.show,
      hide: ch.hide,
      first: (spoken[0] ?? ch.chars[0]).s,
      last: (spoken[spoken.length - 1] ?? ch.chars[0]).e,
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
        whiteSpace: 'nowrap',
      }}
    >
      {chars.map((c, i) => {
        if (DROP.has(c.c)) return <span key={i} style={{display: 'inline-block', width: '0.6em'}} />;
        const k = clamp((t - c.s + 0.03) / 0.08);
        return (
          <span key={i} style={{color: c.k && k > 0 ? key_ : ink, opacity: lerp(0.42, 1, k)}}>
            {c.c}
          </span>
        );
      })}
    </div>
  );
};

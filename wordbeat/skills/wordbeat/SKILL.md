---
name: wordbeat
description: Rules for making a word-synced explainer video in the wordbeat flow - the script format, readings, timing constants, drawing verbs on keywords, captions, sound, and how every stage is measured. Use on every wordbeat turn.
---

# wordbeat

A beat-synced video lands its cuts on the drum; a wordbeat video lands its motions on the
narration's keywords. An agent writing animation code cannot hear, so the order is reversed:
**the voice comes first, the picture follows it.** The second each character is spoken is
measured first (timeline.json); the frame each motion lands on is looked up from that table,
never estimated.

The flow runs every heavy job and every check itself, after your turn: voice generation,
alignment, Remotion renders, ACE-Step, the mix. You write and judge; you do not run those.

## Project layout

```
script.txt          the narration, in the format below
vo/lines/           one voiced line per L###.wav, its take's scores in L###.json
vo/polyphone/       polyphonic characters that may be misread (zh): flagged.txt, flagged.wav
vo_paced/           the lines with even pauses; narration.wav is the whole narration
timeline.json       every line and character with start and end seconds; keywords; sections; gaps
film/               the Remotion project (copied from the starter)
  src/data/timeline.json   kept in sync by the flow
  public/narration.wav     kept in sync by the flow
  src/beats.ts             the beat table: every motion's time comes from here
audio/music_brief.json   the music brief (music stage)
audio/music.wav          the music bed the flow renders from it
audio/sfx/<kind>/*.wav   sound effect files by kind (pop, whoosh, tick, ...), if any
out/                     sample.mp4, final.mp4, cover.png, publish.md
.wordbeat/reports/       every check's JSON report
.wordbeat/review/        contact sheets: the frames around every keyword
```

## 1. Script (script.txt)

```
# a comment
[section name]
One sentence per line, with exactly one *keyword* between asterisks. | 0.43
Write the reading when it differs from the caption: {F F M peg=>FFmpeg}. | 0.4
@gap 5 demo
```

- `| 0.43` is the silence heard after the line, in seconds (default 0.4). The voice stage makes
  the heard silence equal it.
- `@gap seconds name`: a stretch without narration; the name lands in timeline.json's gaps.
- `[section]`: a chapter; timeline.json gives each its start and end.
- A line containing `【】` is a placeholder: not voiced, timed by its length.

Rules, and why:

| Rule | Why |
| --- | --- |
| At most 22 characters between two punctuation marks; mix long and short sentences | A breath that runs out changes the voice; all-short sounds like slogans |
| Exactly one keyword per line, and at most one per caption | The picture lands on it; two landings leave the viewer unsure where to look |
| Keywords are verbs or changes, never a single character | The picture draws verbs; a lone character reads as nothing on screen |
| Never put a sentence the voice says on screen as text | Hearing and reading the same words lowers understanding (redundancy principle) |
| In the first 30 seconds: a misconception the viewer may hold, one concrete number, and what the video teaches | Viewers leave early unless they know what they will get |
| Write readings for names, English and numbers: `{seventeen thousand=>17,000}` | The voice model reads them wrong otherwise |
| Avoid "最后" and "总之" before the last section | Viewers hear an ending and leave |
| No dashes, no "不是……而是……" pattern, none of: 最强 颠覆 一键 零门槛 总结一下 赋能 干货满满 保姆级 | lint_script.py rejects them |

Say it completely: keep subjects, objects, measure words and connectives; prefer two-character
verbs, mixed with single ones as speech does ("测过" → "测试过"); use spoken links ("我们先来看看",
"说白了", "接下来"); follow a long explanation with a short conclusion. One idiom or saying per
section at most, at its conclusion, eight to ten in a film, and only where it fits the point.

Pauses follow meaning, not punctuation:

| Silence (s) | Where |
| --- | --- |
| 0.34-0.40 | the same thought continues; an answer right after a question; a demo follows |
| 0.43 | between ordinary sentences |
| 0.47-0.52 | a new layer of the same paragraph |
| 0.56-0.64 | a paragraph or a conclusion ends |
| 0.7 | after a saying that sums up, to let it land |
| 0.95 | a big turn, such as naming the method after the problem |
| 1.2 | after the last line of the film |

Separate chapters with `@gap 1.1 name` for a chapter card. Vary neighbouring pauses a little
(0.43, 0.47, 0.43).

English scripts: no full stop at the end of a line; numbers as readings.

## 2. Voice

The flow voices each line several times with the cloned voice, has Whisper read every take back,
and keeps the best: the match to the script first, then speed (Chinese 2.5-8.5 characters a
second, English 2.0-3.9 words a second), then pitch movement. Lines are cached by their
reading: change a line and only that line is voiced again.

Judging a line's read-back:
- A homophone Whisper wrote differently (轻/清, 托/拖, 锈/绣) is not an error; the match drops to
  0.85-0.95 for it.
- A misread polyphonic character, a misread acronym, or a word read wrong is: write the reading
  `{reading=>shown}`.
- Correct readings that sound like something else (不断去试 heard as 不断去世) need the line
  reworded.
- polyphone.py's flags are mostly false alarms and it can miss real ones; decide from the
  context and the score, and ask the person when it matters.

Readings to avoid when writing (the misread reading in brackets):

| Avoid | Write |
| --- | --- |
| 拗口 (ào/niù) | 磕磕绊绊, 不顺口 |
| 长高 (zhǎng/cháng) | 拔高 |
| 数十句 (shù/shǔ) | 几十句 |
| 一目了然 (liǎo/le) | 一眼就能看懂 |
| 它就还你 (huán/hái) | 它也只能做出 |
| 就得写成, 还得靠 (děi/de) | 就要写成, 还要靠 |
| 当例子 (dàng/dāng) | 作为例子 |
| 用不着 (zháo/zhe) | 不需要 |
| 空当 (kòng/kōng) | 停顿的地方 |

Polyphonic characters inside idioms and terms (差之毫厘, 重叠动作) are usually read right; keep
them, and list them for the person to hear.

## 3. Picture (film/)

Settle a style first; when unsure, browse https://github.com/syydaniel/awesome-code-animation.
Credit any library you use (Rough.js, Shiki, D3, three.js) in a corner of the frame.

**Draw the verb, not the noun.** Find the change each keyword names and make that change finish
on the keyword:

| Verb | Draw | Lands when |
| --- | --- | --- |
| grow, rise, add | it swells, a bar rises, beside a reference | it reaches size |
| shrink, fall, compress | it tightens, what is squeezed out fades | it reaches size |
| split | it cracks along a line and the halves part | the halves are apart |
| merge | pieces close in and their edges vanish | one piece |
| filter, keep | most of a field dims, the kept stays lit | the dimming ends |
| connect, depend | lines join one by one | the last one joins |
| copy | an identical one slides out of the first | the copy settles |
| replace | the old pushes out, the new comes in at its place | the new settles |
| repeat | a loop returns to its start, the second faster | back at the start |
| compare | two side by side, the difference lit | the light comes on |

**Timing constants (60 fps)** - use the starter's `src/lib/time.ts` and `src/lib/anim.ts`:

| Constant | Value | Why |
| --- | --- | --- |
| motion lands | 3 frames (50 ms) before the keyword's first character, `hit()` | sound ahead by ~45 ms is noticed, picture ahead only at ~125 ms |
| tolerance | 6 frames early to 1 frame late | late by 2 frames nears the threshold |
| new element appears | at least 12 frames before its keyword, `appearBy()` | the eye needs ~200 ms to get there |
| durations | small 6-12 frames, card 18, across the screen 27-42 | weight grows with distance |
| springs | damping ratio ~0.75 (~3% overshoot), `springTo()` | Remotion's default overshoots ~16% and looks like a toy |
| opacity and color | never overshoot | an overshooting opacity flashes |

**The keyword frame must move clearly more than the second before it.** kazi_check.py counts a
hit when the motion from 0.35 s before to 0.15 s after the keyword is at least 1.5 times the
motion of the second before, plus 0.1% of the frame. It fails when:
- a line changes a card only at its start while its keyword sits mid-line;
- the whole scene drifts or spins at a constant rate, so the keyword frame is like any other;
- the motion comes after the word is said.

Raise the hit rate with local effects only: one component bouncing, a small ring of light, a
burst of colored fragments beside it. Never flash, shake, punch or zoom the whole frame: large
camera orbits and push-ins dropped a film's hit rate to 33%.

**Layout.** At most 4 new pieces of information on screen at once; only keywords as on-screen
text, sentences belong to captions. Move the camera with ease-in-out curves over 0.6-1.2 s.

What a person watching a sample found wanting, and what picture_check.py now measures:

- **Fill the frame.** Lay every scene out over the whole frame, centered above the caption band,
  the main element at least half the frame wide. A scene in a thin band with most of the frame
  empty reads thin: the picture must cover at least 10% of the frame above the captions (median
  over the film); films people liked cover 12-47%.
- **Readable on a phone.** On-screen words at least 48 px, keyword labels at least 64 px, titles
  at least 96 px, at 1920x1080.
- **Nothing dead between keywords.** Keep something alive at low intensity: a playhead moving
  with the narration, slow camera drift, a breathing glow. Save the big motion for the keyword.
  picture_check.py points at every stretch of more than 3 s where almost nothing moves.
- **One thread through the film.** One element (a block, a character, the waveform) carries
  through every scene, and each scene hands over to the next through it: the last element of one
  scene becomes the first of the next. No hard cuts between unrelated layouts.
- **Depth and color.** A foreground, a middle and a background layer (vignette, a faint grid in
  perspective, a glow behind the active element), and accent colors used consistently for the
  same things throughout.

**The person's direction.** direction.md in the project holds what the person wants, written at
any time; every turn's prompt carries it. Follow it over your own taste, and rework earlier work
it names.

Keep every position in one layout table shared by the render and a check, and add
`"layout": "tsx scripts/layout_check.ts"` to package.json once the film has one; the flow runs
it before every render and it must fail (exit 1) on overlaps. Check, in every camera position:
components do not overlap and keep a gap; connecting lines end on component surfaces, cross no
component and no other line; text is not covered, not cut off at the frame edge, not over the
caption band. Fade lines out before the components they join move away. Labels that a reused web
animation brings count as overlaps too.

For three.js scenes (`@remotion/three`): the flow renders with the GL backend its `gl` param names; load textures
before the canvas mounts, use `NoToneMapping` with ambient light around 0.5, and keep text panels
within |x| < 5, |y| < 3.4.

**Captions** (`src/comp/Caption.tsx`): at most 16 characters a caption, cut at punctuation, commas
and full stops dropped, question and exclamation marks kept; at most 9 characters a second; each
character darkens when it is spoken and the keyword changes color. Switch captions by the voice
actually heard: the next caption appears 0.05 s before its first word is voiced, never before
the previous caption's voice ends. Breaths of 20-60 ms are not speech.

**Background words**: a very faint large word or idiom (4-6% opacity) behind each section, moving
with the camera, never a single character.

**Cover**: register a still composition `id="Cover"` in Root.tsx: one subject, one line, readable
as a thumbnail, text centered so a 4:3 crop keeps it.

**Contact sheets**: after every render the flow tiles four frames around each keyword (0.45 s and
0.15 s before, 0.05 s and 0.25 s after) into `.wordbeat/review/*_keys_NN.png`. Open them and look:
what is on screen when the word lands, whether anything overlaps, whether text is covered.
Numbers that pass do not excuse a picture that looks wrong.

## 4. Sound

- **Music** sits 12-18 LU under the voice while it speaks and 6 LU under in the gaps; the mix
  ducks it from the word timings (down 0.2 s before a line, up only for gaps over 1.2 s). Stop
  the music 2-4 times in a film for the most important lines. At most three active voices.
- **Sound effects** come from the beat table: `CUES` in beats.ts (`npm run cues` writes
  film/out/cues.json; the flow thins them to about 22 a minute). Four layers: landings on
  keywords (loudest, still 10 dB under the voice), transitions, foley, ambience. Every effect
  fades in and out over at least 5 ms; rotate variants; fewer is better. Put files in
  `audio/sfx/<kind>/`; without them the mix synthesizes placeholder effects.
- Sounds played as they are (a demo voice, an A/B example) go in `CLIPS` in beats.ts, their
  files in film/public/.
- The final mix is -14 LUFS with a true peak at or below -1 dBTP, 48 kHz.
- Write everything to run on Linux, macOS and Windows alike: no platform-only fonts without a
  fallback (load web fonts with `@remotion/google-fonts` or files in film/public), no absolute
  paths, no shell commands in the film's code.

## 5. Checks and publishing

The flow measures the final film with kazi_check.py (hit rate, chance, lift, black frames,
one-frame flashes, 6 s without motion, loudness, true peak, audio track, length) and
caption_check.py (each caption against the voice heard). The reports are in .wordbeat/reports/.

out/publish.md holds: a title that says what the viewer gets; a one-line description; chapter
marks `mm:ss label` from timeline.json's sections; the tools used; a note that the voice is
AI-generated.

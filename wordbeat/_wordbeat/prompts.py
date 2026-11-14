from _wordbeat.config import Config
from _wordbeat.project import TOOLKIT

SIZES = {"landscape": (1920, 1080), "portrait": (1080, 1920)}

FRAME = """You are {role}, one of two agents who take turns making a word-synced explainer video \
("wordbeat"): the picture lands a motion on every keyword of the voice-over, on time, and \
measurements prove it. Each turn is a fresh session. You and the other agent share only the \
project directory, the check report and the handoff notes below. Follow the `wordbeat` skill you \
carry: it holds the script format, the timing constants and the rules every stage is held to.

The person's brief:
{task}

Project directory: {root} (every path below is relative to it)
Narration language: {lang}. Target length: about {minutes:g} minutes. Frame: {width}x{height} at 60 fps.
Toolkit: {toolkit}, run with `{python}`; `{python} {toolkit}/lint_script.py script.txt` is the \
script check, light enough to run yourself."""

STAGES = {
    "script": """## Stage: script

Write or revise script.txt, the narration as the voice will speak it, in the format the skill \
describes: one line per sentence, exactly one *keyword* per line, {{reading=>shown}} where the \
spoken and the shown text differ, `| seconds` for the silence after a line, [section] headings, \
and `@gap seconds name` for stretches without narration. Write for the ear: say in the first \
30 seconds what the viewer will get, make each keyword a verb or a change the picture can show, \
and avoid the polyphonic characters the skill lists. The script is in {language}; keep it so.

The check runs the toolkit's lint_script.py: every problem it reports must be gone. It also \
estimates the length at 5 characters a second; land within a fifth of the target.""",
    "voice": """## Stage: voice

The flow has voiced every line of script.txt (several takes each, the best kept after Whisper \
read it back), evened the pauses, timed every character into timeline.json, and listed the \
polyphonic characters that may be misread. Your job is to make every line read right.

For each line under "to judge", compare what Whisper heard with what was said. A homophone \
Whisper wrote differently is not an error, nor is a number it wrote in digits (四千八百 as 4800, \
二点零 as 2.0): such lines match as low as 0.6 and are read right. A misread word, a misread polyphonic character, an \
acronym read as one word, or a phrase that sounds like something else is: fix it in script.txt, \
by writing the reading as {{reading=>shown}} or by rewording the line, keeping the shown text and \
the keyword. For each flagged polyphonic character, decide from its context and score whether \
the reading is wrong, and fix it the same way. Only lines whose reading changes are voiced again.

Do not edit vo/, vo_paced/ or timeline.json: the flow writes them.""",
    "sample": """## Stage: sample

Build the opening {sample:g} seconds of the film in film/, a Remotion project the flow copied \
from the wordbeat starter. The flow keeps film/src/data/timeline.json, film/src/data/frame.json \
({width}x{height}) and film/public/narration.wav up to date; do not edit them. The starter \
renders a generic card on every keyword, a placeholder to replace. Settle the visual style \
first. Then write film/src/beats.ts, the beat table every motion takes its time from, and the \
scenes. Draw the verb of each keyword, land each motion with hit() 3 frames before the \
keyword's first character, bring new elements in with appearBy(), and keep at most 4 new pieces \
of information on screen. Keep the narration's <Audio>, the captions, the Main composition at \
60 fps and the "Cover" still in Root.tsx; make the cover the film's own.

After your turn the flow renders the first {sample:g} seconds at half size, measures them with \
kazi_check.py and tiles the frames around every keyword into contact sheets. The sample must \
pass `npx tsc --noEmit`, `npm run layout` if package.json defines it, hit at least {rate:.0%} \
of its keywords more often than chance, and have no black frame, no one-frame flash and no \
{static:g} seconds without motion. Look at the contact sheets yourself: elements overlapping, \
text covered or cut off at the frame's edge, and a picture that reads like a slide deck fail \
the stage even when the numbers pass.""",
    "film": """## Stage: film

Build the rest of the film, to the end of timeline.json, in the style the sample settled; keep \
the sample's opening as the person approved it unless the report says otherwise. The flow \
renders the whole film at half size after your turn and holds it to the sample's checks, and \
to a length within {slack:g} s of the timeline. Look at the contact sheets for every keyword, \
as in the sample.""",
    "music": """## Stage: music

Write audio/music_brief.json, the brief the flow sends to ACE-Step to render the music bed under \
the narration. One object for the whole film:

{{"prompt": "calm felt piano and soft strings, instrumental", "bpm": 76, "keyscale": "D major", "seed": 4021}}

or segments that meet end to start and cover 0 to timeline.json's total ({total:.2f} s), each \
at least 10 s long, split at section boundaries (timeline.json's sections) where the mood turns:

{{"crossfade": 1.5, "segments": [{{"start": 0, "end": 62.4, "prompt": "...", "bpm": 76, \
"keyscale": "D major", "seed": 4021}}, ...]}}

Fields: prompt (required), bpm, keyscale, seed, steps, thinking, guidance_scale, shift, model. \
Write instrumental prompts that suit the picture's world, with at most three voices and \
nothing that competes with speech. The flow renders the brief to audio/music.wav and measures \
it: as long as the timeline, no clipping, a true peak at or below 0 dBTP. The mix ducks it \
under the voice later. You cannot listen, so judge by the measurements and keep the brief \
steady; change a seed when a render fails a measurement.""",
    "finish": """## Stage: finish

The flow exports the sound cues (`npm run cues`), thins them, renders the whole film at full \
size, mixes narration, music and sound effects into out/final.mp4, measures it with \
kazi_check.py and caption_check.py, renders the "Cover" still to out/cover.png, and tiles the \
keyword frames again. Fix what the checks find, wherever it is: film/src for missed keywords and \
captions, the CUES and CLIPS in film/src/beats.ts for sound, audio/sfx/<kind>/*.wav for effect \
files. Then write out/publish.md: a title that says what the viewer gets, a one-line \
description, chapter marks from timeline.json's sections as `mm:ss label`, the tools used, and \
a note that the voice is AI-generated.{caps}

The film passes when its keyword checks pass as in the film stage, its loudness is between \
-16.5 and -12.5 LUFS with a true peak at or below -1 dBTP, its length matches the timeline, no \
caption disappears before its last word ends, out/cover.png exists and out/publish.md is \
written.""",
}

CAPS_EN = """ The captions are English, so caption_check needs the captions the picture shows: \
add an npm script "caps" that writes film/out/caps.json, one entry per caption with its text, \
show, hide, first and last times."""

HEAVY = """## What the flow runs, not you

After your turn the flow runs this stage's heavy jobs itself, one at a time: voice generation, \
alignment, Remotion renders, ACE-Step, the mix and every check. Do not run any of them, in the \
foreground or the background. Light commands are fine: reading files, `npx tsc --noEmit`, a \
layout check, pulling a few frames out of a video that already exists."""

ASK = """When a decision belongs to the person, such as how a polyphonic character must be read \
or a style choice the brief leaves open, ask your user with your question tool: the question \
reaches the person, and their answer comes back in this turn. Ask rarely, and never what you can \
find out yourself."""

END = """Finish by answering in the Turn shape. Set stage_done only when you would change nothing \
more. The stage moves on only when the other agent, in the next turn, checks your work and \
agrees without changing a file."""

HUMAN_SAID = """The person reviewed this stage at its gate. Their notes follow, possibly in Chinese; \
follow them exactly, and keep every edit they made by hand.

"""

NOBODY_HERE = "Nobody is here to answer. Decide yourself, and give your reason in the handoff."

RULES_HEAD = "Standing rules the person set earlier in this run. Follow every one:\n"

GATES = {
    "script": "The agents agree the script is ready. Read it below, then decide.",
    "voice": "The narration is voiced and timed. Listen to it (it is open for you), then decide.",
    "sample": "The sample is rendered at full size. Watch it (it is open for you), then decide.",
    "finish": "The film is finished and measured. Watch it (it is open for you), then decide.",
}


def size(config: Config) -> tuple[int, int]:
    return SIZES[config.orientation]


def stage_brief(stage: str, config: Config, total: float = 0.0) -> str:
    width, height = size(config)
    return STAGES[stage].format(
        language="Chinese" if config.lang == "zh" else "English",
        sample=config.sample_seconds,
        width=width,
        height=height,
        rate=config.min_kazi_rate,
        static=6,
        slack=0.5,
        total=total,
        caps=CAPS_EN if config.lang == "en" else "",
    )


def turn(
    *,
    role: str,
    other: str,
    task: str,
    root: str,
    config: Config,
    stage: str,
    total: float,
    last: dict | None,
    human: str,
    passed: bool,
    summary: str,
    images: list[str],
) -> str:
    width, height = size(config)
    parts = [
        FRAME.format(role=role, task=task.strip() or "(none given)", root=root, lang=config.lang,
                     minutes=config.minutes, width=width, height=height, toolkit=TOOLKIT, python=config.python),
        stage_brief(stage, config, total),
    ]
    if human:
        parts.append("## The person's notes at this stage's gate\n\n" + HUMAN_SAID + human)
    if last:
        changed = "changed files" if last.get("changed") else "changed no file"
        parts.append(
            f"## The previous turn, by {last['by']} ({changed}, stage_done={last['stage_done']})\n\n"
            f"Its handoff:\n{last['handoff']}\n\nWhat it found wrong in the turn before it:\n"
            f"{last['issues'] or '(nothing)'}\n\nCheck its work yourself before you build on it: "
            "read the files it changed, the check report and the images. A claim in a handoff is not evidence."
        )
    else:
        parts.append(f"## The previous turn\n\nThis is the stage's first turn; {other} takes the next one.")
    state = "they pass" if passed else "they fail"
    parts.append(f"## The checks after the last change ({state})\n\n{summary}")
    if images:
        parts.append("Look at these images with your file-reading tool:\n" + "\n".join(f"- {i}" for i in images))
    parts += [HEAVY, ASK, END]
    return "\n\n".join(parts)


def revise(notes: str, *, kept: bool, full: str) -> str:
    """The person's notes, sent into the session that last changed the stage's work."""
    head = HUMAN_SAID + notes + "\n\n"
    if kept:
        return head + "Make the changes now, in the same project, then answer in the Turn shape.\n\n" + END
    return head + full


def gate(stage: str, intro: str, view: str, summary: str, last: dict | None, opened: list[str]) -> str:
    parts = [f"wordbeat · {stage} gate", intro or GATES.get(stage, "")]
    if view:
        parts.append(view)
    parts.append("Checks:\n" + summary)
    if last:
        parts.append(f"The agents' last handoff ({last['by']}):\n{last['handoff']}")
    if opened:
        parts.append("Opened for you: " + ", ".join(opened))
    return "\n\n".join(parts)


def stuck(stage: str, turns: int) -> str:
    return (
        f"The agents did not agree that the {stage} stage is done within {turns} turns. "
        "approve accepts the stage as it stands; revise sends your notes to them and gives them "
        "another round of turns; back returns to the previous stage."
    )

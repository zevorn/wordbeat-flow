from dataclasses import dataclass, field

# The bounds the toolkit's own checks and the skill hold a film to.
STATIC_LIMIT = 6.0
LENGTH_SLACK = 0.5
LUFS_RANGE = (-16.5, -12.5)
TRUE_PEAK_MAX = -1.0
MUSIC_PEAK_MAX = 0.0
VOICE_MATCH = 0.9
# The share of the frame above the captions the picture uses, median over the film. Finished films
# the person approved measured 0.12 to 0.47; a sample the person found thin and empty, 0.08.
FILL_MIN = 0.10
LULL_NOTE = 3.0
SPEED = {"zh": (2.5, 8.5), "en": (2.0, 3.9)}


@dataclass
class Verdict:
    """Failures stop a stage; notes are for the agents and the person to judge."""

    failures: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures

    def text(self) -> str:
        lines = [f"- FAIL: {f}" for f in self.failures] + [f"- {n}" for n in self.notes]
        return "\n".join(lines) if lines else "- nothing to report"


def picture(report: dict, *, min_rate: float, total: float | None = None) -> Verdict:
    """kazi_check.py's report on a render: keyword hits and what no film may have."""
    v = Verdict()
    if "kazi_rate" not in report:
        v.failures.append("no keyword falls inside the rendered video")
    else:
        hits, n, rate = report["hits"], report["keywords"], report["kazi_rate"]
        chance, lift = report["chance"], report["lift"]
        line = f"keyword hit rate {hits}/{n} = {rate:.0%}, chance {chance:.0%}, lift {lift:+.0%}"
        if rate < min_rate:
            v.failures.append(f"{line}; at least {min_rate:.0%} is needed")
        elif lift <= 0:
            v.failures.append(f"{line}; the picture must hit keywords more often than chance")
        else:
            v.notes.append(line)
        for row in report.get("detail", []):
            if not row["hit"]:
                v.notes.append(
                    f"missed {row['t']:.2f}s 「{row['word']}」: motion {row['near']:.2f}% around it, "
                    f"{row['before']:.2f}% the second before (needs 1.5x + 0.1%)"
                )
    if report.get("black_frames"):
        v.failures.append(f"{report['black_frames']} black frames")
    if report.get("flash_frames"):
        at = ", ".join(f"{t:.2f}s" for t in report["flash_frames"][:8])
        v.failures.append(f"{len(report['flash_frames'])} frames flash for one frame: {at}")
    if report.get("longest_static", 0) > STATIC_LIMIT:
        v.failures.append(f"the picture stands still for {report['longest_static']:.1f} s (at most {STATIC_LIMIT:.0f})")
    if total is not None and abs(report["duration"] - total) > LENGTH_SLACK:
        v.failures.append(f"the video is {report['duration']:.2f} s, the timeline {total:.2f} s")
    return v


def fill(report: dict) -> Verdict:
    """picture_check.py's report: whether the picture uses the frame, and where it goes quiet."""
    v = Verdict()
    line = f"the picture fills {report['fill_median']:.0%} of the frame (median), {report['fill_p10']:.0%} at its emptiest"
    if report["fill_median"] < FILL_MIN:
        v.failures.append(f"{line}; at least {FILL_MIN:.0%} is needed: lay scenes out over the whole frame, bigger")
    else:
        v.notes.append(line)
    if report["longest_lull"] > LULL_NOTE:
        v.notes.append(
            f"to judge: almost nothing moves for {report['longest_lull']:.1f} s from {report['lull_at']:.1f} s; "
            "keep something alive between keywords"
        )
    return v


def sound(report: dict) -> Verdict:
    """kazi_check.py's report on the final mix: an audio track at a streaming loudness."""
    v = Verdict()
    if not report.get("audio_streams"):
        v.failures.append("the video has no audio track")
        return v
    lufs, peak = report.get("lufs"), report.get("true_peak")
    if lufs is None or not LUFS_RANGE[0] <= lufs <= LUFS_RANGE[1]:
        v.failures.append(f"loudness {lufs} LUFS, outside {LUFS_RANGE[0]} to {LUFS_RANGE[1]}")
    if peak is not None and peak > TRUE_PEAK_MAX:
        v.failures.append(f"true peak {peak} dBTP, above {TRUE_PEAK_MAX}")
    if not v.failures:
        v.notes.append(f"loudness {lufs} LUFS, true peak {peak} dBTP")
    return v


def captions(report: dict) -> Verdict:
    """caption_check.py's report. Only a caption gone before its words end fails: the onset
    measures mistake breaths for speech, so the rest is for judging."""
    v = Verdict()
    for gap, line in report.get("hidden_early", []):
        v.failures.append(f"line {line}: a caption disappears {-gap:.2f} s before its last word ends")
    v.notes.append(f"{report.get('captions', 0)} captions, appearing {report.get('show_median')} s from the voice onset")
    for gap, line, text in report.get("shown_late", [])[:10]:
        v.notes.append(f"line {line}: 「{text}」 appears {gap:.2f} s after the voice starts (a breath can fake this)")
    for gap, line, text in report.get("shown_too_early", [])[:10]:
        v.notes.append(f"line {line}: 「{text}」 appears {-gap:.2f} s before the voice starts")
    if report.get("light_off"):
        v.notes.append(f"{report['light_off']} captions light their first character more than 0.08 s off the voice")
    for line, text, shown in report.get("short", [])[:10]:
        v.notes.append(f"line {line}: 「{text}」 shows for only {shown} s")
    return v


def voice(lines: list[dict], lang: str) -> Verdict:
    """The best take kept for every line, as voice.py wrote it into vo/lines/L###.json. A low match
    is for judging, never a failure: Whisper writes 四千八百 as 4800 and homophones its own way, so a
    line read right can match 0.6."""
    v = Verdict()
    low, high = SPEED[lang]
    for line in lines:
        ratio, cps = line.get("ratio"), line.get("cps")
        if ratio is None:
            v.failures.append(f"line {line['i']} has no voiced take")
            continue
        if ratio < VOICE_MATCH or not low <= cps <= high:
            v.notes.append(
                f"to judge: line {line['i']}: said 「{line['say']}」, Whisper heard 「{line.get('heard', '')}」, "
                f"match {ratio:.2f}, {cps} per second"
            )
    return v


def music(report: dict) -> Verdict:
    """music_check.py's report on the music bed."""
    v = Verdict()
    if report.get("short_by", 0) > 0.05:
        v.failures.append(f"the music is {report['duration']} s, {report['short_by']} s short of the timeline")
    if report.get("clipped_samples"):
        v.failures.append(f"{report['clipped_samples']} clipped samples")
    peak = report.get("true_peak")
    if peak is not None and peak > MUSIC_PEAK_MAX:
        v.failures.append(f"true peak {peak} dBTP, above {MUSIC_PEAK_MAX}")
    v.notes.append(
        f"{report['duration']} s, {report['sample_rate']} Hz, {report['channels']} channels, {report.get('lufs')} LUFS, "
        f"true peak {peak} dBTP, longest silence {report.get('longest_silence')} s"
    )
    return v

import json
from pathlib import Path

from _wordbeat import judge

DATA = Path(__file__).parent / "data"


def load(name: str) -> dict:
    return json.loads((DATA / name).read_text("utf-8"))


def test_a_finished_film_passes_picture_and_sound() -> None:
    report = load("kazi_final_pass.json")
    picture = judge.picture(report, min_rate=0.9, total=160.28)
    sound = judge.sound(report)
    assert picture.passed, picture.text()
    assert sound.passed, sound.text()
    assert not any(n.startswith("missed") for n in picture.notes)


def test_a_draft_fails_on_its_hit_rate_and_names_each_miss() -> None:
    report = load("kazi_v2_low.json")
    picture = judge.picture(report, min_rate=0.9)
    assert not picture.passed
    assert "14/26" in picture.failures[0]
    missed = [n for n in picture.notes if n.startswith("missed")]
    assert len(missed) == report["keywords"] - report["hits"]


def test_a_draft_mix_fails_on_loudness() -> None:
    sound = judge.sound(load("kazi_v2_low.json"))
    assert not sound.passed
    assert "-18.8" in sound.failures[0]


def test_a_film_off_the_timeline_fails_on_length() -> None:
    picture = judge.picture(load("kazi_final_pass.json"), min_rate=0.9, total=158.0)
    assert any("the timeline 158.00 s" in f for f in picture.failures)


def test_a_sample_without_keywords_fails() -> None:
    report = {k: v for k, v in load("kazi_final_pass.json").items() if k not in ("kazi_rate", "detail")}
    assert "no keyword" in judge.picture(report, min_rate=0.9).failures[0]


def test_numbers_whisper_writes_in_digits_are_judged_not_failed() -> None:
    lines = [json.loads(p.read_text("utf-8")) for p in sorted((DATA / "voice_lines").glob("L*.json"))]
    verdict = judge.voice(lines, "zh")
    assert verdict.passed, verdict.text()
    judged = "\n".join(verdict.notes)
    # 将近四千八百位贡献者 matched 0.6 against "4800" and was read right.
    assert "line 34:" in judged
    assert "line 1:" not in judged


def test_a_film_people_liked_fills_enough_of_the_frame() -> None:
    verdict = judge.fill(load("fill_flame_chase_final.json"))
    assert verdict.passed, verdict.text()
    # Its quietest stretch, 3.7 s, is pointed out for judging but does not fail it.
    assert any("3.7 s" in n for n in verdict.notes)


def test_a_thin_sample_fails_on_fill() -> None:
    verdict = judge.fill(load("fill_thin_sample.json"))
    assert not verdict.passed
    assert "8%" in verdict.failures[0]


def test_a_line_without_a_take_fails() -> None:
    verdict = judge.voice([{"i": 7, "say": "x"}], "zh")
    assert verdict.failures == ["line 7 has no voiced take"]

import asyncio
import json
import math

from _wordbeat import judge
from _wordbeat.config import Config
from _wordbeat.models import Report
from _wordbeat.project import STARTER, TOOLKIT, Project, q

FPS = 60
REPORTS = ".wordbeat/reports"
REVIEW = ".wordbeat/review"
BROWSER_TRIES = 5
FILM_INPUTS = ["film/src", "film/scripts", "film/public", "film/package.json", "timeline.json"]


def failed(what: str, said: str) -> Report:
    return Report(False, f"- FAIL: {what}\n\n```\n{said}\n```")


async def total(p: Project) -> float:
    if not await p.exists("timeline.json"):
        return 0.0
    return float((await p.read_json("timeline.json"))["total"])


class Stage:
    name = ""
    gate = False
    watch: tuple[str, ...] = ()

    def active(self, config: Config) -> bool:
        return True

    def agents(self, config: Config) -> bool:
        return True

    async def prepare(self, p: Project) -> None:
        await p.sh(f"mkdir -p {REPORTS} {REVIEW}")

    async def check(self, p: Project) -> Report:
        raise NotImplementedError

    async def before_gate(self, p: Project, report: Report) -> Report:
        return report

    async def view(self, p: Project, report: Report) -> str:
        return ""


class Script(Stage):
    name, gate, watch = "script", True, ("script.txt",)

    async def check(self, p: Project) -> Report:
        if not await p.exists("script.txt"):
            return Report(False, "- FAIL: script.txt does not exist yet")
        code, said = await p.tool("lint_script.py", "script.txt", "--json", f"{REPORTS}/lint.json")
        if code != 0:
            return failed("lint_script.py could not read script.txt", said)
        lint = await p.read_json(f"{REPORTS}/lint.json")
        target = p.config.minutes * 60
        v = judge.Verdict(failures=[f"lint: {x}" for x in lint["problems"]])
        v.notes.append(f"estimated length {lint['seconds']:.0f} s against a target of {target:.0f} s")
        v.notes += [f"section {k or '(opening)'}: {s:.0f} s" for k, s in lint["sections"].items()]
        return Report(v.passed, v.text())

    async def view(self, p: Project, report: Report) -> str:
        text = await p.read_text("script.txt")
        numbered = "\n".join(f"{n:>3}  {line}" for n, line in enumerate(text.splitlines(), 1))
        return f"script.txt:\n\n{numbered}"


class Voice(Stage):
    name, gate, watch = "voice", True, ("script.txt",)

    async def prepare(self, p: Project) -> None:
        await super().prepare(p)
        if not (p.config.voice_ref or p.config.narration):
            raise ValueError("the voice stage needs voice_ref (a voice to clone) or narration (a recording)")

    async def check(self, p: Project) -> Report:
        c = p.config
        lang = f"--lang {c.lang} --backend {c.speech_backend}"
        if c.narration:
            rec = p.given(c.narration)
            code, said = await p.step(
                "narration",
                ["script.txt", rec],
                f"mkdir -p vo_paced && ffmpeg -v error -y -i {q(rec)} -ac 1 -ar 24000 vo_paced/narration.wav && "
                + p.python("timeline.py", "script.txt", "-", "timeline.json", "--whole", "vo_paced/narration.wav", lang),
                ["timeline.json", "vo_paced/narration.wav"],
            )
            if code != 0:
                return failed("timing the narration failed", said)
            return Report(True, f"- the narration recording is timed into timeline.json, {await total(p):.1f} s",
                          previews=["vo_paced/narration.wav"])
        ref = p.given(c.voice_ref)
        jobs = [
            ("voice", ["script.txt", ref],
             p.python("voice.py", "script.txt", "vo", "--ref", q(ref), "--takes", str(c.takes), lang), ["vo/lines"]),
        ]
        src = "vo"
        if c.tempo != 1.0:
            jobs.append(("tempo", ["vo/lines"], p.python("tempo.py", "vo", "vo_fast", "--tempo", str(c.tempo)), ["vo_fast"]))
            src = "vo_fast"
        jobs += [
            ("pace", [f"{src}/lines"], p.python("pace.py", src, "vo_paced", "--report", "vo_paced/report.tsv"),
             ["vo_paced/lines"]),
            ("timeline", ["script.txt", "vo_paced/lines"],
             p.python("timeline.py", "script.txt", "vo_paced", "timeline.json", "--wav", "vo_paced/narration.wav",
                      "--speech-gap", lang),
             ["timeline.json", "vo_paced/narration.wav"]),
        ]
        if c.lang == "zh":
            jobs.append(("polyphone", ["timeline.json", "vo_paced/narration.wav"],
                         p.python("polyphone.py", "timeline.json", "vo_paced/narration.wav", "--out", "vo/polyphone",
                                  "--backend", c.speech_backend),
                         ["vo/polyphone/flagged.txt"]))
        for key, inputs, script, outputs in jobs:
            code, said = await p.step(key, inputs, script, outputs)
            if code != 0:
                return failed(f"{key} failed", said)
        tl = await p.read_json("timeline.json")
        lines = []
        for line in tl["lines"]:
            if not line.get("real"):
                continue
            meta = f"vo/lines/L{line['i']:03d}.json"
            lines.append({**line, **(await p.read_json(meta) if await p.exists(meta) else {})})
        v = judge.voice(lines, c.lang)
        v.notes.insert(0, f"{len(lines)} lines voiced, {tl['total']:.1f} s in all")
        previews = ["vo_paced/narration.wav"]
        if await p.exists("vo/polyphone/flagged.txt"):
            flagged = [x for x in (await p.read_text("vo/polyphone/flagged.txt")).splitlines() if x.strip()]
            v.notes += [f"polyphonic, to judge: {x}" for x in flagged]
            if flagged:
                previews.append("vo/polyphone/flagged.wav")
        return Report(v.passed, v.text(), previews=previews)

    async def view(self, p: Project, report: Report) -> str:
        tl = await p.read_json("timeline.json")
        rows = []
        for line in tl["lines"]:
            meta = f"vo/lines/L{line['i']:03d}.json"
            m = await p.read_json(meta) if await p.exists(meta) else {}
            rows.append(f"L{line['i']:03d}  {line['start']:7.2f}s  match {m.get('ratio', '-')}  "
                        f"{m.get('cps', '-')}/s  {line['say']}")
        return "Every line, where it starts and how well Whisper heard it:\n\n" + "\n".join(rows)


class Picture(Stage):
    """The film in film/, rendered at half size and measured."""

    watch = ("film/src", "film/scripts", "film/package.json", "film/public")
    gate = False
    whole = True

    async def prepare(self, p: Project) -> None:
        await super().prepare(p)
        if not await p.exists("film/package.json"):
            code, said = await p.sh(f"cp -R {q(str(STARTER))} film")
            if code != 0:
                raise RuntimeError(f"copying the starter failed: {said}")
        if not await p.exists("film/node_modules"):
            print("wordbeat · installing the Remotion project", flush=True)
            code, said = await p.sh("cd film && npm ci --no-audit --no-fund", heavy=True)
            if code != 0:
                raise RuntimeError(f"npm ci failed in film/: {said}")
        # Remotion renders with its own headless Chrome, downloaded on first use; fetch it here, where a
        # dropped connection can be tried again, rather than inside the first render.
        for tried in range(BROWSER_TRIES):
            code, said = await p.sh("cd film && npx remotion browser ensure", heavy=True)
            if code == 0:
                break
            print(f"wordbeat · fetching Remotion's browser failed, try {tried + 1} of {BROWSER_TRIES}", flush=True)
            await asyncio.sleep(30)
        else:
            raise RuntimeError(f"Remotion's headless browser could not be fetched: {said}")

    async def sync(self, p: Project) -> None:
        """The film's copies of the timeline and the narration, where the narration is audible, and the
        frame size and language the params ask for."""
        width, height = (1920, 1080) if p.config.orientation == "landscape" else (1080, 1920)
        frame = q(json.dumps({"width": width, "height": height, "lang": p.config.lang}))
        code, said = await p.sh(
            "mkdir -p film/src/data film/public && cp timeline.json film/src/data/timeline.json && "
            "cp vo_paced/narration.wav film/public/narration.wav && "
            f"printf '%s\\n' {frame} > film/src/data/frame.json && "
            + p.python("voice_loud.py", "vo_paced/narration.wav", "film/src/data/voice_loud.json")
        )
        if code != 0:
            raise RuntimeError(f"syncing film/ with the narration failed: {said}")

    async def code(self, p: Project) -> Report | None:
        code, said = await p.sh("cd film && npx tsc --noEmit")
        if code != 0:
            return failed("`npx tsc --noEmit` fails in film/", said)
        if "layout" in await p.scripts():
            code, said = await p.sh("cd film && npm run layout")
            if code != 0:
                return failed("`npm run layout` fails in film/", said)
        return None

    async def measure(
        self, p: Project, video: str, name: str, length: float | None
    ) -> tuple[judge.Verdict, list[str], dict]:
        """kazi_check.py and the keyword contact sheets: the verdict, the sheets, the raw report."""
        code, said = await p.tool("kazi_check.py", q(video), "--timeline", "timeline.json",
                                  "--json", f"{REPORTS}/{name}.json", "--quiet", heavy=True)
        if code != 0:
            return judge.Verdict(failures=[f"kazi_check.py failed: {said}"]), [], {}
        report = await p.read_json(f"{REPORTS}/{name}.json")
        v = judge.picture(report, min_rate=p.config.min_kazi_rate, total=length)
        v.notes.append(f"details: {REPORTS}/{name}.json")
        code, said = await p.tool("keysheet.py", q(video), "timeline.json", f"{REVIEW}/{name}_keys", heavy=True)
        if code != 0:
            v.notes.append(f"keysheet.py failed: {said}")
            return v, [], report
        return v, (await p.read_json(f"{REVIEW}/{name}_keys.json"))["sheets"], report

    def frames(self, p: Project, length: float) -> int:
        return math.ceil(min(p.config.sample_seconds, length) * FPS) - 1

    async def check(self, p: Project) -> Report:
        await self.sync(p)
        bad = await self.code(p)
        if bad:
            return bad
        length = await total(p)
        name = "film" if self.whole else "sample"
        span = "" if self.whole else f" --frames=0-{self.frames(p, length)}"
        video = f"film/out/{name}_half.mp4"
        code, said = await p.step(
            f"{name}_render", FILM_INPUTS,
            f"cd film && npx remotion render src/index.ts Main out/{name}_half.mp4 --scale=0.5{span} "
            f"--gl={p.config.gl} --concurrency={p.config.concurrency} --log=error",
            [video],
        )
        if code != 0:
            return failed(f"rendering the {name} failed", said)
        v, sheets, _ = await self.measure(p, video, name, length if self.whole else None)
        return Report(v.passed, v.text(), previews=[video], images=sheets)


class Sample(Picture):
    name, gate, whole = "sample", True, False

    async def before_gate(self, p: Project, report: Report) -> Report:
        length = await total(p)
        code, said = await p.step(
            "sample_full", FILM_INPUTS,
            f"mkdir -p out && cd film && npx remotion render src/index.ts Main ../out/sample.mp4 "
            f"--frames=0-{self.frames(p, length)} --gl={p.config.gl} --concurrency={p.config.concurrency} "
            "--crf=17 --log=error",
            ["out/sample.mp4"],
        )
        if code != 0:
            return Report(report.passed, report.summary + f"\n- the full-size sample failed to render: {said}",
                          report.previews, report.images)
        return Report(report.passed, report.summary, ["out/sample.mp4", *report.images], report.images)


class Film(Picture):
    name, gate, whole = "film", False, True


class Music(Stage):
    name, gate, watch = "music", False, ("audio/music_brief.json",)

    def active(self, config: Config) -> bool:
        return config.music != "none"

    def agents(self, config: Config) -> bool:
        return config.music == "ace"

    async def prepare(self, p: Project) -> None:
        await super().prepare(p)
        if p.config.music == "ace":
            code, _ = await p.sh(f"curl -sf --max-time 10 {q(p.config.ace_url)}/health")
            if code != 0:
                raise RuntimeError(
                    f"the ACE-Step API does not answer at {p.config.ace_url}; start it (acestep-api) and resume the run"
                )

    async def check(self, p: Project) -> Report:
        c = p.config
        length = await total(p)
        if c.music == "file":
            src = p.given(c.music_file)
            code, said = await p.step(
                "music_file", [src],
                f"mkdir -p audio && ffmpeg -v error -y -i {q(src)} -ar 48000 -ac 2 -c:a pcm_s24le audio/music.wav",
                ["audio/music.wav"],
            )
        elif not await p.exists("audio/music_brief.json"):
            return Report(False, "- FAIL: audio/music_brief.json does not exist yet")
        else:
            model = f" --model {q(c.ace_model)}" if c.ace_model else ""
            code, said = await p.step(
                "music", ["audio/music_brief.json", "timeline.json"],
                p.python("ace_music.py", "audio/music_brief.json", "audio/music.wav", "--duration", f"{length:.3f}",
                         "--url", q(c.ace_url), "--steps", str(c.ace_steps), "--cache", "audio/ace") + model,
                ["audio/music.wav"],
            )
        if code != 0:
            return failed("rendering the music failed", said)
        code, said = await p.tool("music_check.py", "audio/music.wav", "--timeline", "timeline.json",
                                  "--json", f"{REPORTS}/music.json")
        if code != 0:
            return failed("music_check.py failed", said)
        v = judge.music(await p.read_json(f"{REPORTS}/music.json"))
        return Report(v.passed, v.text(), previews=["audio/music.wav"])


class Finish(Picture):
    name, gate, whole = "finish", True, True
    watch = ("film/src", "film/scripts", "film/package.json", "film/public", "audio/sfx", "out/publish.md")

    async def check(self, p: Project) -> Report:
        c = p.config
        await self.sync(p)
        bad = await self.code(p)
        if bad:
            return bad
        length = await total(p)
        scripts = await p.scripts()
        v = judge.Verdict()
        mix = ["--timeline", "timeline.json", "--voice", "vo_paced/narration.wav"]
        if c.music != "none" and await p.exists("audio/music.wav"):
            mix += ["--music", "audio/music.wav"]
        if "cues" in scripts:
            code, said = await p.step("cues", FILM_INPUTS, "cd film && npm run cues", ["film/out/cues.json"])
            if code != 0:
                return failed("`npm run cues` failed", said)
            code, said = await p.tool("thin_cues.py", "film/out/cues.json", "film/out/cues_thin.json")
            if code != 0:
                return failed("thin_cues.py failed", said)
            if await p.exists("audio/sfx"):
                mix += ["--cues", "film/out/cues_thin.json", "--sfx-dir", "audio/sfx"]
            else:
                v.notes.append("audio/sfx/ does not exist, so the cues are mixed with the toolkit's synthesized effects")
                mix += ["--cues", "film/out/cues_thin.json"]
            if await p.exists("film/out/clips.json"):
                mix += ["--clips", "film/out/clips.json", "--clip-root", "film/public"]
        caps = []
        if "caps" in scripts:
            code, said = await p.step("caps", FILM_INPUTS, "cd film && npm run caps", ["film/out/caps.json"])
            if code != 0:
                return failed("`npm run caps` failed", said)
            caps = ["--caps", "film/out/caps.json"]
        elif c.lang == "en":
            v.failures.append("English captions need an npm script `caps` that writes film/out/caps.json")
        code, said = await p.step(
            "render", FILM_INPUTS,
            f"cd film && npx remotion render src/index.ts Main out/video.mp4 --gl={c.gl} "
            f"--concurrency={c.concurrency} --crf=17 --log=error",
            ["film/out/video.mp4"],
        )
        if code != 0:
            return failed("rendering the film failed", said)
        mix += ["--out", "audio/mix.wav", "--stems", "audio/stems", "--video", "film/out/video.mp4",
                "--final", "out/final.mp4"]
        code, said = await p.step(
            "mix",
            ["film/out/video.mp4", "vo_paced/narration.wav", "audio/music.wav", "audio/sfx", "film/out/cues_thin.json",
             "film/out/clips.json", "timeline.json"],
            "mkdir -p out audio && " + p.python("mix.py", *mix),
            ["out/final.mp4", "audio/mix.wav"],
        )
        if code != 0:
            return failed("mix.py failed", said)
        pic, sheets, measured = await self.measure(p, "out/final.mp4", "final", length)
        snd = judge.sound(measured) if measured else judge.Verdict()
        code, said = await p.tool("caption_check.py", "timeline.json", "vo_paced/narration.wav", *caps,
                                  "--json", f"{REPORTS}/captions.json")
        cap = judge.captions(await p.read_json(f"{REPORTS}/captions.json")) if code == 0 else \
            judge.Verdict(failures=[f"caption_check.py failed: {said}"])
        code, said = await p.sh("grep -rqs 'id=\"Cover\"' film/src")
        if code != 0:
            v.failures.append("film/src registers no still composition with the id \"Cover\"")
        else:
            code, said = await p.step(
                "cover", FILM_INPUTS,
                "mkdir -p out && cd film && npx remotion still src/index.ts Cover ../out/cover.png --log=error",
                ["out/cover.png"],
            )
            if code != 0:
                v.failures.append(f"rendering the Cover still failed: {said}")
        if not await p.exists("out/publish.md"):
            v.failures.append("out/publish.md is not written yet")
        failures = pic.failures + snd.failures + cap.failures + v.failures
        notes = pic.notes + snd.notes + cap.notes + v.notes
        summary = judge.Verdict(failures, notes).text()
        return Report(not failures, summary, previews=["out/final.mp4", "out/cover.png"], images=sheets)

    async def view(self, p: Project, report: Report) -> str:
        if not await p.exists("out/publish.md"):
            return ""
        return "out/publish.md:\n\n" + await p.read_text("out/publish.md")


STAGES: dict[str, Stage] = {s.name: s for s in (Script(), Voice(), Sample(), Film(), Music(), Finish())}
ORDER = ("script", "voice", "sample", "film", "music", "finish")


async def preflight(p: Project, order: tuple[str, ...]) -> None:
    """Refuses the run before any agent starts when the machine lacks a program or package a stage needs."""
    c = p.config
    stages = [s for s in order if STAGES[s].active(c)]
    if c.narration:
        stages = ["narration" if s == "voice" else s for s in stages]
    code, said = await p.tool("preflight.py", "--stages", ",".join(stages), "--backend", c.speech_backend,
                              "--master", c.master if "finish" in order else "none")
    if code != 0:
        raise RuntimeError(f"preflight.py could not run with {c.python}: {said}")
    missing = json.loads(said.strip().splitlines()[-1])["missing"]
    if missing:
        raise RuntimeError("this machine lacks:\n" + "\n".join(f"- {m}" for m in missing))


async def master(p: Project) -> str:
    """The 4K master after the final gate, and Dolby Vision 8.4 and HLG from it when asked."""
    c = p.config
    script = (f"cd film && bash {q(str(TOOLKIT / 'master.sh'))} Main 8 {c.concurrency} src/data/timeline.json")
    code, said = await p.step("master", FILM_INPUTS, script, ["film/out/master/base_4k.mp4"])
    if code != 0:
        raise RuntimeError(f"the 4K master failed: {said}")
    mux = ("if ffmpeg -hide_banner -encoders 2>/dev/null | grep -q ' aac_at '; then A='-c:a aac_at -aac_at_mode cbr'; "
           "else A='-c:a aac'; fi; ffmpeg -v error -y -i film/out/master/base_4k.mp4 -i audio/mix.wav -map 0:v:0 -map 1:a:0 "
           "-c:v libx264 -preset faster -crf 15 -pix_fmt yuv420p "
           "-bsf:v h264_metadata=colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1 "
           "-colorspace bt709 -color_primaries bt709 -color_trc bt709 $A -b:a 320k -movflags +faststart out/final_4k.mp4")
    code, said = await p.step("final_4k", ["film/out/master/base_4k.mp4", "audio/mix.wav"], mux, ["out/final_4k.mp4"])
    if code != 0:
        raise RuntimeError(f"encoding out/final_4k.mp4 failed: {said}")
    made = ["out/final_4k.mp4"]
    if c.master == "hdr":
        hdr = (f"PY={q(c.python)} zsh {q(str(TOOLKIT / 'hdr' / 'hdr_encode.sh'))} "
               "film/out/master/base_4k.mp4 audio/mix.wav out/hdr")
        code, said = await p.step("hdr", ["film/out/master/base_4k.mp4", "audio/mix.wav"], hdr, ["out/hdr/kazi_dv84.mp4"])
        if code != 0:
            raise RuntimeError(f"the HDR encode failed: {said}")
        made += ["out/hdr/kazi_dv84.mp4", "out/hdr/kazi_hlg.mp4"]
    return ", ".join(made)

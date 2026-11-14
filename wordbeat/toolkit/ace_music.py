import argparse
import hashlib
import itertools
import json
import subprocess
import time
from pathlib import Path

import requests

# ACE-Step's REST API generates 10 to 600 seconds per task.
SHORTEST, LONGEST = 10.0, 600.0

ap = argparse.ArgumentParser(description="Render a music bed from a brief with a running ACE-Step API.")
ap.add_argument("brief", help="JSON: {prompt, bpm?, keyscale?, seed?, ...} or {segments: [{start, end, prompt, ...}], crossfade?}")
ap.add_argument("out", help="the music bed to write: 48 kHz stereo 24-bit WAV, exactly --duration long")
ap.add_argument("--duration", type=float, required=True)
ap.add_argument("--url", default="http://127.0.0.1:8001")
ap.add_argument("--steps", type=int, default=8)
ap.add_argument("--model", default="")
ap.add_argument("--cache", default="audio/ace")
ap.add_argument("--timeout", type=float, default=3600)
a = ap.parse_args()

brief = json.loads(Path(a.brief).read_text("utf-8"))
fade = float(brief.get("crossfade", 1.5))
segments = brief.get("segments") or [{**{k: v for k, v in brief.items() if k != "crossfade"}, "start": 0, "end": a.duration}]
segments = sorted(segments, key=lambda s: float(s["start"]))
if abs(float(segments[0]["start"])) > 0.01 or abs(float(segments[-1]["end"]) - a.duration) > 0.5:
    raise SystemExit(f"segments must cover 0 to {a.duration:.2f} s")
for prev, nxt in itertools.pairwise(segments):
    if abs(float(prev["end"]) - float(nxt["start"])) > 0.01:
        raise SystemExit(f"segments must meet: one ends at {prev['end']}, the next starts at {nxt['start']}")


def request(seg: dict, seconds: float) -> dict:
    body = {
        "prompt": seg["prompt"],
        "lyrics": "[Instrumental]",
        "audio_duration": round(max(SHORTEST, seconds), 2),
        "inference_steps": int(seg.get("steps", a.steps)),
        "audio_format": "wav",
        "batch_size": 1,
        "thinking": bool(seg.get("thinking", False)),
    }
    if seg.get("bpm"):
        body["bpm"] = int(seg["bpm"])
    if seg.get("keyscale"):
        body["key_scale"] = seg["keyscale"]
    if seg.get("seed") is not None:
        body["seed"], body["use_random_seed"] = int(seg["seed"]), False
    for k in ("guidance_scale", "shift"):
        if seg.get(k) is not None:
            body[k] = seg[k]
    if seg.get("model") or a.model:
        body["model"] = seg.get("model") or a.model
    return body


def generate(body: dict, dest: Path) -> None:
    r = requests.post(f"{a.url}/release_task", json=body, timeout=60)
    r.raise_for_status()
    task = r.json()["data"]["task_id"]
    deadline = time.time() + a.timeout
    while True:
        q = requests.post(f"{a.url}/query_result", json={"task_id_list": [task]}, timeout=60)
        q.raise_for_status()
        item = q.json()["data"][0]
        if item["status"] == 1:
            break
        if item["status"] == 2:
            raise SystemExit(f"ACE-Step failed the task {task}: {item.get('result')}")
        if time.time() > deadline:
            raise SystemExit(f"ACE-Step did not finish the task {task} in {a.timeout:.0f} s")
        time.sleep(3)
    result = json.loads(item["result"])
    url = result[0]["file"]
    audio = requests.get(url if url.startswith("http") else f"{a.url}{url}", timeout=600)
    audio.raise_for_status()
    dest.write_bytes(audio.content)


cache = Path(a.cache)
cache.mkdir(parents=True, exist_ok=True)
parts, lengths = [], []
for i, seg in enumerate(segments):
    length = float(seg["end"]) - float(seg["start"])
    if length > LONGEST:
        raise SystemExit(f"segment {i + 1} is {length:.1f} s; ACE-Step makes at most {LONGEST:.0f} s, split it")
    if len(segments) > 1 and length < SHORTEST:
        raise SystemExit(f"segment {i + 1} is {length:.1f} s; make every segment at least {SHORTEST:.0f} s")
    lengths.append(length + (fade if i + 1 < len(segments) else 0))
    body = request(seg, lengths[-1])
    key = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:16]
    dest = cache / f"{key}.wav"
    if not dest.exists():
        print(f"segment {i + 1}/{len(segments)}: {body['audio_duration']} s, {seg['prompt'][:60]}", flush=True)
        generate(body, dest)
    else:
        print(f"segment {i + 1}/{len(segments)}: cached {dest}", flush=True)
    parts.append(dest)

cmd = ["ffmpeg", "-v", "error", "-y"]
for p in parts:
    cmd += ["-i", str(p)]
# Each part is cut to the length its segment asked for, so the crossfades fall where the brief says.
chain = [f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{n:.3f},asetpts=PTS-STARTPTS[p{i}]"
         for i, n in enumerate(lengths)]
last = "[p0]"
for i in range(1, len(parts)):
    label = f"[x{i}]"
    chain.append(f"{last}[p{i}]acrossfade=d={fade}:c1=tri:c2=tri{label}")
    last = label
tail = max(0.0, a.duration - 2.0)
chain.append(f"{last}apad,atrim=0:{a.duration},"
             f"afade=t=out:st={tail}:d={a.duration - tail}[out]")
Path(a.out).parent.mkdir(parents=True, exist_ok=True)
subprocess.run([*cmd, "-filter_complex", ";".join(chain), "-map", "[out]", "-c:a", "pcm_s24le", a.out], check=True)
(Path(a.out).with_suffix(".json")).write_text(json.dumps({"segments": segments, "parts": [str(p) for p in parts]},
                                                         ensure_ascii=False, indent=1), "utf-8")
print(f"wrote {a.out}")

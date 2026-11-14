import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import speech

ap = argparse.ArgumentParser(description="List what this machine lacks for the wordbeat stages asked for.")
ap.add_argument("--stages", default="script,voice,sample,film,music,finish")
ap.add_argument("--backend", default="auto", choices=["auto", "mlx", "torch"])
ap.add_argument("--master", default="none", choices=["none", "4k", "hdr"])
a = ap.parse_args()
stages = set(a.stages.split(","))
missing = []


def program(name: str, why: str) -> None:
    if shutil.which(name) is None:
        missing.append(f"the program {name} ({why})")


def module(name: str, pip: str, why: str) -> None:
    if importlib.util.find_spec(name) is None:
        missing.append(f"the Python package {pip} ({why}); pip install {pip}")


module("numpy", "numpy", "every check")
module("soundfile", "soundfile", "audio files")
if stages & {"voice", "narration", "sample", "film", "music", "finish"}:
    program("ffmpeg", "audio and video")
    program("ffprobe", "audio and video")
    for mod, pip in (("scipy", "scipy"), ("librosa", "librosa"), ("pyloudnorm", "pyloudnorm"), ("PIL", "Pillow")):
        module(mod, pip, "measuring audio and video")
backend = speech.pick(a.backend)
if "voice" in stages:
    module("pypinyin", "pypinyin", "finding polyphonic characters")
    if backend == "mlx":
        module("mlx_audio", "mlx-audio", "voice and alignment on Apple silicon")
        module("mlx_whisper", "mlx-whisper", "reading takes back on Apple silicon")
    else:
        module("torch", "torch", "voice, read-back and alignment")
        module("qwen_tts", "qwen-tts", "Qwen3-TTS voice cloning")
        module("qwen_asr", "qwen-asr", "Qwen3-ForcedAligner timing")
        module("whisper", "openai-whisper", "reading takes back")
if "narration" in stages:
    if backend == "mlx":
        module("mlx_audio", "mlx-audio", "alignment on Apple silicon")
    else:
        module("torch", "torch", "alignment")
        module("qwen_asr", "qwen-asr", "Qwen3-ForcedAligner timing")
if stages & {"sample", "film", "finish"}:
    program("node", "Remotion, 20 or newer")
    program("npm", "Remotion")
    program("npx", "Remotion")
    if shutil.which("node"):
        version = subprocess.run(["node", "-v"], capture_output=True, text=True).stdout.strip()
        if not version.startswith("v") or int(version[1:].split(".")[0]) < 20:
            missing.append(f"Node.js 20 or newer (this is {version})")
if "music" in stages:
    module("requests", "requests", "the ACE-Step API")
    program("curl", "reaching the ACE-Step API")
if a.master == "hdr":
    program("zsh", "the HDR encode script")
    program("dovi_tool", "Dolby Vision metadata")
    program("MP4Box", "packing Dolby Vision MP4 (GPAC)")
print(json.dumps({"backend": backend, "missing": missing}, ensure_ascii=False))

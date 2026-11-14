import argparse
import json
import re
import subprocess
from pathlib import Path

import numpy as np
import pyloudnorm as pyln
import soundfile as sf

ap = argparse.ArgumentParser(description="Measure a music bed: length, loudness, true peak, clipping, silence.")
ap.add_argument("wav")
ap.add_argument("--timeline", default="")
ap.add_argument("--json", default="")
a = ap.parse_args()

y, sr = sf.read(a.wav, dtype="float64", always_2d=True)
length = len(y) / sr
mono = y.mean(1)
report = {
    "file": a.wav,
    "sample_rate": sr,
    "channels": y.shape[1],
    "duration": round(length, 3),
    "lufs": round(float(pyln.Meter(sr).integrated_loudness(y)), 2) if length >= 0.5 else None,
    "clipped_samples": int((np.abs(y) >= 0.999).sum()),
}
# True peak as ffmpeg's ebur128 measures it, the same meter kazi_check uses for the final mix.
r = subprocess.run(["ffmpeg", "-nostats", "-i", a.wav, "-af", "ebur128=peak=true", "-f", "null", "-"],
                   capture_output=True, text=True)
peaks = re.findall(r"Peak:\s+(-?[\d.]+|-inf) dBFS", r.stderr)
report["true_peak"] = float(peaks[-1]) if peaks and peaks[-1] != "-inf" else None
# Longest stretch below -50 dBFS, in 50 ms windows.
hop = int(0.05 * sr)
if hop and len(mono) >= hop:
    frames = mono[: len(mono) // hop * hop].reshape(-1, hop)
    quiet = 20 * np.log10(np.sqrt((frames**2).mean(1)) + 1e-12) < -50
    run = best = 0
    for q in quiet:
        run = run + 1 if q else 0
        best = max(best, run)
    report["longest_silence"] = round(best * 0.05, 2)
if a.timeline:
    total = json.loads(Path(a.timeline).read_text("utf-8"))["total"]
    report["timeline_total"] = total
    report["short_by"] = round(max(0.0, total - length), 3)
if a.json:
    Path(a.json).parent.mkdir(parents=True, exist_ok=True)
    Path(a.json).write_text(json.dumps(report, ensure_ascii=False, indent=1), "utf-8")
print(json.dumps(report, ensure_ascii=False))

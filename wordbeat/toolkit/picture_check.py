import argparse
import json
import subprocess
from pathlib import Path

import numpy as np

# Two things a frame-by-frame keyword check cannot see: how much of the frame the picture uses,
# and how long it goes almost still between keywords.
W, H = 192, 108
CAPTION_BAND = 0.14  # the bottom share of the frame the captions own, left out of the fill
COLOR_STEP = 24  # colors closer than this (0-255 per channel) count as the background


def frames(video: str, fps: float):
    cmd = ["ffmpeg", "-v", "error", "-i", video, "-vf", f"fps={fps},scale={W}:{H}", "-f", "rawvideo",
           "-pix_fmt", "rgb24", "-"]
    with subprocess.Popen(cmd, stdout=subprocess.PIPE) as proc:
        size = W * H * 3
        while chunk := proc.stdout.read(size):
            if len(chunk) < size:
                break
            yield np.frombuffer(chunk, np.uint8).reshape(H, W, 3)


def fill(frame: np.ndarray) -> float:
    """Share of the frame above the caption band that differs from its most common color."""
    body = frame[: int(H * (1 - CAPTION_BAND))].reshape(-1, 3).astype(np.int16)
    keys, counts = np.unique(body // COLOR_STEP, axis=0, return_counts=True)
    background = (keys[counts.argmax()] * COLOR_STEP + COLOR_STEP // 2).astype(np.int16)
    return float((np.abs(body - background).max(1) > COLOR_STEP).mean())


ap = argparse.ArgumentParser(description="Measure how much of the frame a film uses and its longest lull.")
ap.add_argument("video")
ap.add_argument("--fps", type=float, default=10)
ap.add_argument("--lull", type=float, default=0.002, help="motion (mean frame difference, 0-1) below this is a lull")
ap.add_argument("--json", default="")
a = ap.parse_args()

fills, motion, prev = [], [], None
for f in frames(a.video, a.fps):
    fills.append(fill(f))
    gray = f.mean(2) / 255
    motion.append(float(np.abs(gray - prev).mean()) if prev is not None else 1.0)
    prev = gray
fills_a = np.array(fills)
run = longest = at = start = 0
for i, m in enumerate(motion):
    if m < a.lull:
        if run == 0:
            start = i
        run += 1
        if run > longest:
            longest, at = run, start
    else:
        run = 0
report = {
    "video": a.video,
    "seconds": round(len(fills) / a.fps, 2),
    "fill_median": round(float(np.median(fills_a)), 3),
    "fill_p10": round(float(np.percentile(fills_a, 10)), 3),
    "sparse_seconds": round(float((fills_a < 0.15).sum()) / a.fps, 1),
    "longest_lull": round(longest / a.fps, 2),
    "lull_at": round(at / a.fps, 2),
}
if a.json:
    Path(a.json).parent.mkdir(parents=True, exist_ok=True)
    Path(a.json).write_text(json.dumps(report, indent=1), "utf-8")
print(json.dumps(report))

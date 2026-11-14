import argparse
import io
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Seconds around each keyword's first character, as kazi_check judges a hit.
AROUND = (-0.45, -0.15, 0.05, 0.25)
ROWS = 8
FONTS = (
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
)


def duration(video: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video],
        capture_output=True, text=True, check=True,
    ).stdout
    return float(out.strip())


def frame(video: str, t: float, width: int) -> Image.Image:
    png = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{max(0.0, t):.3f}", "-i", video,
         "-frames:v", "1", "-vf", f"scale={width}:-2", "-f", "image2pipe", "-vcodec", "png", "-"],
        capture_output=True, check=True,
    ).stdout
    return Image.open(io.BytesIO(png)).convert("RGB")


def font(size: int, path: str) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in ((path,) if path else ()) + FONTS:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default(size)


def keywords(timeline: dict) -> list[dict]:
    return [{"word": k["word"], "t": float(k["t"])} for k in timeline.get("keywords", [])]


ap = argparse.ArgumentParser(description="Tile the frames around every keyword into contact sheets.")
ap.add_argument("video")
ap.add_argument("timeline")
ap.add_argument("out", help="output prefix: <out>_01.png, <out>_02.png, ... and <out>.json")
ap.add_argument("--offset", type=float, default=0.0, help="timeline second that the video's first frame shows")
ap.add_argument("--width", type=int, default=480)
ap.add_argument("--font", default="")
a = ap.parse_args()

tl = json.loads(Path(a.timeline).read_text("utf-8"))
length = duration(a.video)
kws = [{**k, "t": k["t"] - a.offset} for k in keywords(tl)]
kws = [k for k in kws if 0 <= k["t"] <= length]
label = font(max(14, a.width // 22), a.font)
out = Path(a.out)
out.parent.mkdir(parents=True, exist_ok=True)
sheets = []
for start in range(0, len(kws), ROWS):
    rows = []
    for n, k in enumerate(kws[start:start + ROWS], start):
        tiles = [frame(a.video, k["t"] + d, a.width) for d in AROUND]
        w, h = tiles[0].size
        bar = label.size if hasattr(label, "size") else 14
        row = Image.new("RGB", (w * len(tiles), h + bar + 10), "white")
        for i, tile in enumerate(tiles):
            row.paste(tile, (i * w, bar + 10))
        text = f"#{n + 1}  {k['t'] + a.offset:.2f}s  {k['word']}   (" + ", ".join(f"{d:+.2f}s" for d in AROUND) + ")"
        ImageDraw.Draw(row).text((6, 4), text, fill="black", font=label)
        rows.append(row)
    sheet = Image.new("RGB", (rows[0].width, sum(r.height for r in rows)), "white")
    y = 0
    for row in rows:
        sheet.paste(row, (0, y))
        y += row.height
    path = out.with_name(f"{out.name}_{len(sheets) + 1:02d}.png")
    sheet.save(path)
    sheets.append(str(path))
out.with_name(f"{out.name}.json").write_text(
    json.dumps({"sheets": sheets, "keywords": len(kws), "around": AROUND}, ensure_ascii=False, indent=1), "utf-8"
)
print(f"{len(kws)} keywords, {len(sheets)} sheets")
for s in sheets:
    print(s)

import json
import sys

import numpy as np
import soundfile as sf

# Where the narration is audible, in 10 ms steps, measured the way kazi's caption_check measures it
# (RMS against the loud part of the whole take, quieter than -32 dB counts as silence), so the caption
# component can switch captions on the voice itself instead of on the aligner's word times.
# Usage: python voice_loud.py narration.wav out.json
y, sr = sf.read(sys.argv[1], dtype="float32", always_2d=True)
y = y.mean(1)
HOP = 0.01
h = int(HOP * sr)
n = len(y) // h
r = np.sqrt(np.mean(y[:n * h].reshape(n, h) ** 2, 1) + 1e-12)
db = 20 * np.log10(r / np.percentile(r, 95))
loud = np.convolve(db > -32, np.ones(3), "same") >= 2
json.dump({"hop": HOP, "loud": "".join("1" if v else "0" for v in loud)}, open(sys.argv[2], "w"))
print(f"{n} steps, {loud.mean() * 100:.1f}% audible -> {sys.argv[2]}")

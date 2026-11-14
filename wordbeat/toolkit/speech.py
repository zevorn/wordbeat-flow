from __future__ import annotations

import platform
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

# numpy, soundfile and the model packages load where they are used, so preflight.py can import
# this module on a machine that lacks them and report what is missing.

# The same three models on two backends: MLX on Apple silicon, PyTorch everywhere else
# (CUDA, Apple's MPS, or the CPU).
MODELS = {
    "mlx": {"tts": "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16", "asr": "mlx-community/whisper-large-v3-turbo"},
    "torch": {"tts": "Qwen/Qwen3-TTS-12Hz-1.7B-Base", "asr": "turbo"},
}
ALIGNER = "Qwen/Qwen3-ForcedAligner-0.6B"
LANGUAGE = {"zh": "Chinese", "en": "English"}


def pick(choice: str = "auto") -> str:
    """The backend to run: the one asked for, or MLX on Apple silicon where it is installed, else PyTorch."""
    if choice != "auto":
        return choice
    if sys.platform == "darwin" and platform.machine() == "arm64":
        try:
            import mlx_audio  # noqa: F401
            import mlx_whisper  # noqa: F401

            return "mlx"
        except ImportError:
            pass
    return "torch"


def torch_device(whisper: bool = False) -> str:
    import torch

    if torch.cuda.is_available():
        return "cuda:0"
    # openai-whisper runs ops MPS lacks, so Whisper stays on the CPU there.
    if not whisper and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def torch_dtype(device: str):
    import torch

    return torch.bfloat16 if device.startswith("cuda") else torch.float32


class Voice:
    """Qwen3-TTS Base cloning one reference voice."""

    def __init__(self, backend: str, model: str, ref: Path, ref_text: str) -> None:
        self.backend, self.ref, self.ref_text = backend, ref, ref_text
        self.model = model or MODELS[backend]["tts"]
        if backend == "mlx":
            from mlx_audio.tts.utils import load_model

            self.tts = load_model(self.model)
        else:
            from qwen_tts import Qwen3TTSModel

            device = torch_device()
            self.tts = Qwen3TTSModel.from_pretrained(self.model, device_map=device, dtype=torch_dtype(device))
            self.prompt = self.tts.create_voice_clone_prompt(
                ref_audio=str(ref), ref_text=ref_text, x_vector_only_mode=False
            )

    def say(self, text: str, lang: str, max_tokens: int, prefix: Path) -> tuple[np.ndarray, int]:
        """One take of one line: mono samples and their rate."""
        import numpy as np
        import soundfile as sf

        if self.backend == "mlx":
            from mlx_audio.tts.generate import generate_audio

            for old in prefix.parent.glob(f"{prefix.name}*.wav"):
                old.unlink()
            generate_audio(text=text, model=self.tts, ref_audio=str(self.ref), ref_text=self.ref_text,
                           lang_code=lang, file_prefix=str(prefix), verbose=False, max_tokens=max_tokens)
            y, sr = sf.read(next(prefix.parent.glob(f"{prefix.name}*.wav")), dtype="float32", always_2d=True)
            return y[:, 0], sr
        wavs, sr = self.tts.generate_voice_clone(
            text=text, language=LANGUAGE[lang], voice_clone_prompt=self.prompt, max_new_tokens=max_tokens
        )
        y = np.asarray(wavs[0], dtype=np.float32)
        return (y if y.ndim == 1 else y.mean(-1)), int(sr)


class Ears:
    """Whisper large-v3-turbo, reading a take back."""

    def __init__(self, backend: str, model: str = "") -> None:
        self.backend = backend
        self.model = model or MODELS[backend]["asr"]
        if backend == "torch":
            import whisper

            self.device = torch_device(whisper=True)
            self.whisper = whisper.load_model(self.model, device=self.device)

    def hear(self, path: Path, lang: str, hint: str) -> str:
        if self.backend == "mlx":
            import mlx_whisper

            return mlx_whisper.transcribe(str(path), path_or_hf_repo=self.model, language=lang, initial_prompt=hint,
                                          condition_on_previous_text=False)["text"].strip()
        return self.whisper.transcribe(str(path), language=lang, initial_prompt=hint, condition_on_previous_text=False,
                                       fp16=self.device.startswith("cuda"))["text"].strip()


class Aligner:
    """Qwen3-ForcedAligner: the start and end of every character or word of a known text."""

    def __init__(self, backend: str, model: str = "") -> None:
        self.backend = backend
        self.model = model or ALIGNER
        if backend == "mlx":
            from mlx_audio.stt import load

            self.aligner = load(self.model)
        else:
            from qwen_asr import Qwen3ForcedAligner

            device = torch_device()
            self.aligner = Qwen3ForcedAligner.from_pretrained(self.model, dtype=torch_dtype(device), device_map=device)

    def align(self, wav: Path, text: str, lang: str) -> list[dict]:
        if self.backend == "mlx":
            r = self.aligner.generate(str(wav), text=text, language=LANGUAGE[lang])
            if hasattr(r, "segments"):
                return [{"t": x["text"], "s": round(float(x["start"]), 3), "e": round(float(x["end"]), 3)}
                        for x in r.segments]
            items = r
        else:
            items = self.aligner.align(audio=str(wav), text=text, language=LANGUAGE[lang])[0]
        return [{"t": x.text, "s": round(float(x.start_time), 3), "e": round(float(x.end_time), 3)} for x in items]


class Scorer:
    """Whisper's log probability of candidate transcripts for one stretch of 16 kHz audio."""

    def __init__(self, backend: str, model: str = "", language: str = "zh") -> None:
        self.backend = backend
        self.model_name = model or MODELS[backend]["asr"]
        if backend == "mlx":
            from mlx_whisper.load_models import load_model
            from mlx_whisper.tokenizer import get_tokenizer

            self.model = load_model(self.model_name)
        else:
            import whisper
            from whisper.tokenizer import get_tokenizer

            self.device = torch_device(whisper=True)
            self.model = whisper.load_model(self.model_name, device=self.device)
        self.tok = get_tokenizer(self.model.is_multilingual, num_languages=self.model.num_languages,
                                 language=language, task="transcribe")
        self.prompt = list(self.tok.sot_sequence_including_notimestamps)

    def score(self, seg: np.ndarray, texts: list[str]) -> list[float]:
        if self.backend == "mlx":
            return self._mlx(seg, texts)
        return self._torch(seg, texts)

    def _mlx(self, seg: np.ndarray, texts: list[str]) -> list[float]:
        import mlx.core as mx
        import numpy as np
        from mlx_whisper.audio import N_FRAMES, N_SAMPLES, log_mel_spectrogram, pad_or_trim

        seg = np.pad(seg, (0, max(0, N_SAMPLES - len(seg))))[:N_SAMPLES]
        mel = log_mel_spectrogram(mx.array(seg), n_mels=self.model.dims.n_mels)
        feats = self.model.embed_audio(pad_or_trim(mel, N_FRAMES, axis=-2)[None])
        out = []
        for t in texts:
            ids = [*self.tok.encode(t), self.tok.eot]
            lp = self.model.logits(mx.array([self.prompt + ids]), feats)[0]
            lp = lp - mx.logsumexp(lp, axis=-1, keepdims=True)
            n = len(self.prompt)
            out.append(float(sum(lp[n - 1 + j, ids[j]].item() for j in range(len(ids)))))
        return out

    def _torch(self, seg: np.ndarray, texts: list[str]) -> list[float]:
        import numpy as np
        import torch
        from whisper.audio import N_FRAMES, N_SAMPLES, log_mel_spectrogram, pad_or_trim

        seg = np.pad(seg, (0, max(0, N_SAMPLES - len(seg))))[:N_SAMPLES]
        out = []
        with torch.no_grad():
            mel = log_mel_spectrogram(torch.from_numpy(seg.astype(np.float32)), n_mels=self.model.dims.n_mels)
            feats = self.model.embed_audio(pad_or_trim(mel, N_FRAMES)[None].to(self.device))
            for t in texts:
                ids = [*self.tok.encode(t), self.tok.eot]
                x = torch.tensor([self.prompt + ids], device=self.device)
                lp = self.model.logits(x, feats)[0].float().log_softmax(-1)
                n = len(self.prompt)
                out.append(float(sum(lp[n - 1 + j, ids[j]].item() for j in range(len(ids)))))
        return out

from typing import Literal

from hmz.flows import FlowParams
from pydantic import ConfigDict, Field, model_validator

FILM = {"section": "film  ·  what the video is"}
TOOLS = {"section": "tools  ·  where the toolkit runs"}
CHECKS = {"section": "checks  ·  what counts as done"}
MUSIC = {"section": "music  ·  the bed under the voice"}
PEOPLE = {"section": "people  ·  how the run involves you"}


class Config(FlowParams):
    model_config = ConfigDict(frozen=True)

    project: str = Field(
        default=".",
        description="project directory, relative to the workspace or absolute",
        json_schema_extra=FILM,
    )
    lang: Literal["zh", "en"] = Field(
        default="zh", description="language of the narration and captions", json_schema_extra=FILM
    )
    minutes: float = Field(
        default=2.0, gt=0, le=60, description="target length in minutes", json_schema_extra=FILM
    )
    orientation: Literal["landscape", "portrait"] = Field(
        default="landscape", description="1920x1080 or 1080x1920", json_schema_extra=FILM
    )
    voice_ref: str = Field(
        default="",
        description="reference recording of the voice to clone; its transcript is the .txt beside it",
        json_schema_extra=FILM,
    )
    narration: str = Field(
        default="",
        description="a finished narration recording to time instead of generating one",
        json_schema_extra=FILM,
    )
    takes: int = Field(
        default=4, ge=1, le=8, description="takes generated per line, the best kept", json_schema_extra=FILM
    )
    tempo: float = Field(
        default=1.0, ge=0.8, le=1.3, description="speed the narration up or down without changing pitch",
        json_schema_extra=FILM,
    )
    master: Literal["none", "4k", "hdr"] = Field(
        default="none",
        description="after the final gate: also a 4K master, or 4K plus Dolby Vision 8.4 and HLG",
        json_schema_extra=FILM,
    )

    python: str = Field(
        default="python3",
        description="Python with the toolkit's requirements (toolkit/requirements.txt, Pillow, requests)",
        json_schema_extra=TOOLS,
    )
    speech_backend: Literal["auto", "mlx", "torch"] = Field(
        default="auto",
        description="voice, read-back and alignment: mlx on Apple silicon, torch (CUDA, MPS or CPU) anywhere; "
        "auto picks mlx where it is installed",
        json_schema_extra=TOOLS,
    )
    gl: Literal["angle", "swangle", "egl", "vulkan", "swiftshader"] = Field(
        default="angle",
        description="Remotion's OpenGL renderer; swangle on a machine without a GPU",
        json_schema_extra=TOOLS,
    )
    hf_home: str = Field(
        default="", description="HF_HOME for the voice and alignment models; empty keeps yours",
        json_schema_extra=TOOLS,
    )
    concurrency: int = Field(
        default=4, ge=1, le=16, description="Remotion render concurrency", json_schema_extra=TOOLS
    )
    harness_retries: int = Field(
        default=6,
        ge=0,
        le=50,
        description="times a turn is tried again when an agent's CLI fails it, waiting 30 s, then twice as "
        "long each time, at most 10 minutes",
        json_schema_extra=TOOLS,
    )
    heavy_timeout: float = Field(
        default=0, ge=0, description="seconds one heavy job may take; zero for no limit", json_schema_extra=TOOLS
    )

    sample_seconds: float = Field(
        default=25, ge=5, le=120, description="length of the sample shown at the third gate",
        json_schema_extra=CHECKS,
    )
    min_kazi_rate: float = Field(
        default=0.9, ge=0, le=1, description="share of keywords the picture must hit", json_schema_extra=CHECKS
    )
    max_turns: int = Field(
        default=12, ge=2, le=200, description="turns per stage before the person decides", json_schema_extra=CHECKS
    )

    music: Literal["ace", "file", "none"] = Field(
        default="ace",
        description="ace: the agents brief a running ACE-Step API; file: music_file; none: no music",
        json_schema_extra=MUSIC,
    )
    music_file: str = Field(default="", description="the music bed when music=file", json_schema_extra=MUSIC)
    ace_url: str = Field(
        default="http://127.0.0.1:8001", description="ACE-Step REST API", json_schema_extra=MUSIC
    )
    ace_steps: int = Field(
        default=8, ge=1, le=200, description="ACE-Step inference steps", json_schema_extra=MUSIC
    )
    ace_model: str = Field(
        default="", description="ACE-Step DiT model; empty for the server's default", json_schema_extra=MUSIC
    )

    gates: Literal["ask", "auto"] = Field(
        default="ask",
        description="ask: stop at each gate for you (and pause when nobody is there); auto: the agents decide",
        json_schema_extra=PEOPLE,
    )
    preview_open: bool = Field(
        default=True, description="open the audio, video and images to judge before each gate asks",
        json_schema_extra=PEOPLE,
    )

    @model_validator(mode="after")
    def _settles(self) -> "Config":
        if self.music == "file" and not self.music_file:
            raise ValueError("music=file needs music_file")
        if self.voice_ref and self.narration:
            raise ValueError("give voice_ref to generate the narration, or narration to use yours, not both")
        return self

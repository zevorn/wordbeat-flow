from dataclasses import asdict, dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Turn(BaseModel):
    """What one agent's turn comes to."""

    model_config = ConfigDict(extra="forbid")

    previous_ok: bool = Field(
        description="True if the previous turn's work holds up after you checked it yourself in the "
        "files, the check report and the images; True as well on the stage's first turn. "
        "False if you found anything wrong in it, even if you fixed it."
    )
    issues: str = Field(
        description="What is wrong in the previous turn's work, each with its file and line, or its "
        "timestamp. Empty when nothing is."
    )
    stage_done: bool = Field(
        description="True only if this stage is finished: its checks pass, the person's notes are all "
        "followed, and you would change nothing more. False if anything is left to do."
    )
    handoff: str = Field(
        description="A note to the next agent, passed on word for word: what you did and why, what you "
        "are unsure of, and what is left."
    )


class Gate(BaseModel):
    """What the person decides at a gate."""

    decision: Literal["approve", "revise", "back"] = Field(
        description="approve: move on; revise: rework this stage with your notes; "
        "back: return to the previous stage with your notes"
    )
    notes: str = Field(default="", description="Your notes, by line number or timestamp")
    keep: bool = Field(default=False, description="Should every later stage follow these notes too?")


@dataclass
class Report:
    """A stage's checks: whether they pass, and what to tell the agents and the person."""

    passed: bool
    summary: str
    previews: list[str] = field(default_factory=list)
    images: list[str] = field(default_factory=list)

    def dump(self) -> dict:
        return asdict(self)

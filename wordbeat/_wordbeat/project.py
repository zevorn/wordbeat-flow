import hashlib
import json
import os
import shlex
import sys
from pathlib import Path, PurePosixPath
from typing import Any

from hmz.flows import EnvCommandTimeout

from _wordbeat.config import Config

HERE = Path(__file__).resolve().parent.parent
TOOLKIT = HERE / "toolkit"
STARTER = HERE / "starter"
TAIL = 4000

q = shlex.quote


def tail(text: str, size: int = TAIL) -> str:
    text = text.strip()
    return text if len(text) <= size else "…" + text[-size:]


class Project:
    """The project directory in the workspace, and the toolkit run in it."""

    def __init__(self, workspace: Any, config: Config, state: Any) -> None:
        self.workspace = workspace
        self.config = config
        self.state = state
        here = PurePosixPath(str(workspace.workdir))
        self.root = here / os.path.expanduser(config.project)

    def given(self, path: str) -> str:
        """A path from the params, which are relative to the workspace, as an absolute one."""
        return str(PurePosixPath(str(self.workspace.workdir)) / os.path.expanduser(path))

    def at(self, path: str) -> str:
        return str(self.root / path)

    async def sh(self, script: str, *, heavy: bool = False) -> tuple[int, str]:
        """Runs a bash script in the project directory: its exit status and the end of its output."""
        timeout = self.config.heavy_timeout if heavy else 0
        try:
            code, out, err = await self.workspace.exec(f"cd {q(str(self.root))} && {script}", timeout=timeout)
        except EnvCommandTimeout:
            return 124, f"timed out after {timeout:.0f} s: {script}"
        return code, tail(out + err)

    def python(self, tool: str, *args: str) -> str:
        """The command line that runs one toolkit script with the configured Python."""
        env = f"env HF_HOME={q(self.given(self.config.hf_home))} " if self.config.hf_home else ""
        words = " ".join(args)
        return f"{env}{q(self.config.python)} -I {q(str(TOOLKIT / tool))} {words}".rstrip()

    async def tool(self, tool: str, *args: str, heavy: bool = False) -> tuple[int, str]:
        return await self.sh(self.python(tool, *args), heavy=heavy)

    async def exists(self, path: str) -> bool:
        code, _ = await self.sh(f"test -e {q(path)}")
        return code == 0

    async def read_text(self, path: str) -> str:
        return (await self.workspace.read(self.at(path))).decode("utf-8")

    async def read_json(self, path: str) -> Any:
        return json.loads(await self.read_text(path))

    async def fingerprint(self, *paths: str) -> str:
        code, out = await self.tool("fingerprint.py", *(q(p) for p in paths))
        if code != 0:
            raise RuntimeError(f"fingerprint.py failed: {out}")
        return out.strip().splitlines()[-1]

    async def step(self, key: str, inputs: list[str], script: str, outputs: list[str]) -> tuple[int, str]:
        """Runs a heavy job unless its inputs and command are the same as when it last succeeded."""
        stamp = await self.fingerprint(*inputs) + hashlib.sha256(script.encode()).hexdigest()[:16]
        steps = dict(self.state.get("steps") or {})
        if steps.get(key) == stamp and all([await self.exists(o) for o in outputs]):
            return 0, "unchanged since the last run"
        print(f"wordbeat · running {key}", flush=True)
        steps.pop(key, None)
        code, said = await self.sh(script, heavy=True)
        if code == 0:
            steps[key] = stamp
        self.state["steps"] = steps
        return code, said

    async def open(self, paths: list[str]) -> None:
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        for path in paths:
            if await self.exists(path):
                await self.sh(f"{opener} {q(path)} >/dev/null 2>&1 || true")

    async def scripts(self) -> dict[str, str]:
        """The npm scripts film/package.json defines."""
        if not await self.exists("film/package.json"):
            return {}
        return (await self.read_json("film/package.json")).get("scripts", {})

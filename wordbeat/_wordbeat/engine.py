import asyncio
from typing import Any

from hmz.flows import (
    AskUserHookParams,
    AskUserHookResult,
    HarnessError,
    HarnessNotInstalled,
    HarnessRefused,
    ModelUnavailable,
    OutworlderAway,
    SessionError,
    SessionStartHookParams,
    SessionStartHookResult,
    StateNotSerializable,
    UnsupportedOperation,
)

from _wordbeat import prompts
from _wordbeat.config import Config
from _wordbeat.models import Gate, Report, Turn
from _wordbeat.project import Project
from _wordbeat.stages import STAGES, Stage, master, preflight, total

ROLES = ("first_chaser", "second_chaser")
# Failures that waiting cannot mend: a CLI that is not installed, a model the account cannot run,
# a refused credential, a session used wrongly.
FINAL = (HarnessNotInstalled, ModelUnavailable, HarnessRefused, SessionError, UnsupportedOperation)
RETRY_FIRST, RETRY_MOST = 30, 600
# Per-stage keys a stage clears when it ends; its kept session and author stay for a return to it.
PASSING = ("claim", "turns", "ready", "human", "inject", "last")


class Paused(RuntimeError):
    """A gate needs the person and nobody is there: the run stops, and a picked-up run asks again."""

    def __init__(self, stage: str) -> None:
        super().__init__(
            f"wordbeat is waiting at the {stage} gate and nobody is here to decide. Pick the run up "
            "(/resume) at the prompt to answer it, or run it with -p gates=auto."
        )


class Stuck(RuntimeError):
    """A stage cannot finish without the person, and the run may not ask them."""


class Engine:
    """Two agents take turns on each stage until both agree and its checks pass."""

    def __init__(self, task: str, agents: Any, envs: Any, config: Config, state: Any) -> None:
        self.task = task
        self.config = config
        self.state = state
        self.chasers = (agents["first_chaser"], agents["second_chaser"])
        self.human = agents["human"]
        self.workspace = envs["workspace"]
        self.project = Project(self.workspace, config, state)
        self.listening = None
        self.current = ROLES[0]
        self.stage = ""
        for chaser in self.chasers:
            chaser.on_ask_user(self._asked)
            chaser.on_session_start(self._rules)

    def get(self, key: str, default: Any = None) -> Any:
        value = self.state.get(key)
        return default if value is None else value

    def key(self, stage: str, name: str) -> str:
        return f"{stage}.{name}"

    async def _listen(self) -> Any:
        if self.listening is None:
            self.listening = await self.human.spawn()
        return self.listening

    async def _asked(self, params: AskUserHookParams) -> AskUserHookResult:
        """An agent's mid-turn question goes to the person; the answer returns into that turn."""
        if self.human.away:
            return AskUserHookResult(answer=prompts.NOBODY_HERE)
        offered = "".join(f"\n  · {o}" for o in params.options)
        asked = f"{self.current} asks, in the {self.stage} stage:\n\n{params.question}"
        if offered:
            asked += f"\n\nThe answers it offers:{offered}"
        try:
            said = await self.human.run(asked, session=await self._listen())
        except OutworlderAway:
            said = ""
        return AskUserHookResult(answer=said.strip() or prompts.NOBODY_HERE)

    async def _rules(self, params: SessionStartHookParams) -> SessionStartHookResult:
        """Every new session starts with the standing rules the person set at earlier gates."""
        rules = self.get("rules", [])
        if not rules:
            return SessionStartHookResult()
        return SessionStartHookResult(context=prompts.RULES_HEAD + "\n".join(f"- {r}" for r in rules))

    async def check(self, stage: Stage) -> Report:
        report = await stage.check(self.project)
        self.state[self.key(stage.name, "report")] = report.dump()
        print(f"wordbeat · {stage.name} checks {'pass' if report.passed else 'fail'}", flush=True)
        return report

    def keep(self, stage: str, idx: int, session: Any) -> None:
        """Keeps the session that last changed the stage's work, for the person's notes to reach."""
        self.state[self.key(stage, "author")] = idx
        try:
            self.state[self.key(stage, "session")] = session
        except StateNotSerializable:
            if self.key(stage, "session") in self.state:
                del self.state[self.key(stage, "session")]

    async def prompt(self, stage: Stage, idx: int, report: Report) -> str:
        return prompts.turn(
            role=ROLES[idx],
            other=ROLES[1 - idx],
            task=self.task,
            root=str(self.project.root),
            config=self.config,
            stage=stage.name,
            total=await total(self.project),
            last=self.get(self.key(stage.name, "last")),
            human=self.get(self.key(stage.name, "human"), ""),
            passed=report.passed,
            summary=report.summary,
            images=report.images,
        )

    async def attempt(self, idx: int, session: Any, prompt: str) -> Turn:
        """One agent's turn, tried again after a wait when its CLI fails it: a provider that drops
        the connection for a while must not end a run hours long."""
        for tried in range(self.config.harness_retries + 1):
            try:
                return await self.chasers[idx].run(prompt, session=session, env=self.workspace, output_schema=Turn)
            except FINAL:
                raise
            except HarnessError as error:
                if tried == self.config.harness_retries:
                    raise
                wait = min(RETRY_FIRST * 2**tried, RETRY_MOST)
                print(f"wordbeat · {ROLES[idx]}'s turn failed ({error}); trying again in {wait} s", flush=True)
                await asyncio.sleep(wait)
        raise AssertionError("unreachable")

    async def take(self, stage: Stage, idx: int, session: Any, prompt: str, report: Report) -> tuple[Report, Turn, bool]:
        """One turn of one agent: what it said, whether it changed the work, and the checks after."""
        s = stage.name
        self.current = ROLES[idx]
        before = await self.project.fingerprint(*stage.watch)
        turn = await self.attempt(idx, session, prompt)
        changed = before != await self.project.fingerprint(*stage.watch)
        self.state["turn"] = 1 - idx
        self.state[self.key(s, "turns")] = self.get(self.key(s, "turns"), 0) + 1
        self.state[self.key(s, "last")] = {"by": ROLES[idx], "changed": changed, **turn.model_dump()}
        if changed or self.key(s, "session") not in self.state:
            self.keep(s, idx, session)
        if changed:
            report = await self.check(stage)
        return report, turn, changed

    async def turn(self, stage: Stage, report: Report) -> tuple[Report, bool]:
        """The next agent's turn; whether the stage has converged after it."""
        s = stage.name
        idx = self.get("turn", 0)
        session = await self.chasers[idx].spawn()
        report, turn, changed = await self.take(stage, idx, session, await self.prompt(stage, idx, report), report)
        claim = self.get(self.key(s, "claim"))
        converged = False
        if changed:
            claim = idx if turn.stage_done else None
        elif claim is not None and claim != idx and turn.previous_ok and turn.stage_done:
            converged = True
        else:
            claim = idx if turn.stage_done else None
        if converged and not report.passed:
            converged, claim = False, None
        self.state[self.key(s, "claim")] = claim
        return report, converged

    async def inject(self, stage: Stage, report: Report) -> Report:
        """The person's notes go into the session of the agent that last changed this stage's work."""
        s = stage.name
        idx = self.get(self.key(s, "author"), 1 - self.get("turn", 0))
        kept = self.key(s, "session") in self.state
        session = self.state[self.key(s, "session")] if kept else await self.chasers[idx].spawn()
        full = await self.prompt(stage, idx, report)
        asked = prompts.revise(self.get(self.key(s, "human"), ""), kept=kept, full=full)
        report, turn, changed = await self.take(stage, idx, session, asked, report)
        if not changed:
            self.keep(s, idx, session)
        self.state[self.key(s, "claim")] = idx if turn.stage_done else None
        self.state[self.key(s, "inject")] = False
        return report

    async def ask(self, stage: Stage, report: Report, intro: str) -> Gate:
        """Puts the stage to the person; Paused when nobody is there."""
        if self.human.away:
            raise Paused(stage.name)
        report = await stage.before_gate(self.project, report)
        view = await stage.view(self.project, report)
        opened = []
        if self.config.preview_open:
            opened = [p for p in report.previews if await self.project.exists(p)]
            await self.project.open(opened)
        asked = prompts.gate(stage.name, intro, view, report.summary, self.get(self.key(stage.name, "last")), opened)
        try:
            answer = await self.human.run(asked, session=await self._listen(), output_schema=Gate)
        except OutworlderAway as away:
            raise Paused(stage.name) from away
        notes = answer.notes.strip()
        if answer.keep and notes:
            self.state["rules"] = [*self.get("rules", []), notes]
        if answer.decision == "revise":
            self.state[self.key(stage.name, "human")] = notes or "Rework this stage; the person gave no details."
            self.state[self.key(stage.name, "inject")] = True
            self.state[self.key(stage.name, "ready")] = False
            self.state[self.key(stage.name, "turns")] = 0
        return answer

    def close(self, stage: str) -> None:
        for name in PASSING:
            if self.key(stage, name) in self.state:
                del self.state[self.key(stage, name)]

    async def run_stage(self, stage: Stage) -> tuple[str, str]:
        """Runs one stage to its end: ("done", "") or ("back", the person's notes)."""
        s = stage.name
        self.stage = s
        if not stage.active(self.config):
            return "done", ""
        print(f"wordbeat · stage {s}", flush=True)
        await stage.prepare(self.project)
        report = await self.check(stage)
        if not stage.agents(self.config):
            if not report.passed:
                raise Stuck(f"{s}: {report.summary}")
            return "done", ""
        while True:
            if self.get(self.key(s, "inject")):
                report = await self.inject(stage, report)
            while not self.get(self.key(s, "ready")):
                if self.get(self.key(s, "turns"), 0) >= self.config.max_turns:
                    if self.config.gates == "auto":
                        raise Stuck(f"{s}: the agents did not agree within {self.config.max_turns} turns\n{report.summary}")
                    answer = await self.ask(stage, report, prompts.stuck(s, self.config.max_turns))
                    if answer.decision == "approve":
                        self.close(s)
                        return "done", ""
                    if answer.decision == "back":
                        self.close(s)
                        return "back", answer.notes
                    report = await self.inject(stage, report)
                    continue
                report, converged = await self.turn(stage, report)
                if converged:
                    self.state[self.key(s, "ready")] = True
            if not stage.gate or self.config.gates == "auto":
                self.close(s)
                return "done", ""
            answer = await self.ask(stage, report, "")
            if answer.decision == "approve":
                self.close(s)
                return "done", ""
            if answer.decision == "back":
                self.close(s)
                return "back", answer.notes

    async def drive(self, order: tuple[str, ...], position: str) -> str:
        """Runs the stages in order from where the run stands, stepping back when the person says so."""
        await preflight(self.project, order)
        i = self.get(position, 0)
        while i < len(order):
            outcome, notes = await self.run_stage(STAGES[order[i]])
            if outcome == "back":
                target = i - 1
                while target >= 0 and not STAGES[order[target]].active(self.config):
                    target -= 1
                target = max(target, 0) if target >= 0 else i
                name = order[target]
                self.state[self.key(name, "human")] = notes.strip() or "The person sent this stage back without details."
                self.state[self.key(name, "inject")] = True
                self.state[self.key(name, "turns")] = 0
                i = target
            else:
                i += 1
            self.state[position] = i
        if "finish" in order and self.config.master != "none" and not self.get("mastered"):
            made = await master(self.project)
            self.state["mastered"] = True
            print(f"wordbeat · mastered {made}", flush=True)
        last = self.get(self.key(order[-1], "report"))
        return last["summary"] if last else "done"

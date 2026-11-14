from hmz.flows import (
    Agent,
    AgentCollection,
    AskUserHookAgentMixin,
    BashEnvMixin,
    EnvCollection,
    FilesEnvMixin,
    FlowContext,
    LocalEnv,
    MemoryEnvMixin,
    Outworlder,
    Permission,
    PermissionKind,
    flow,
)

from _wordbeat.config import Config
from _wordbeat.engine import Engine
from _wordbeat.stages import ORDER

# The agents run npm and npx, whose caches sit in the home directory, and read the web for
# libraries and styles.
CHASER_PERMISSION = Permission(
    local=PermissionKind.ALL,
    user=PermissionKind.ALL,
    system=PermissionKind.READ,
    online=PermissionKind.ALL,
)


class Chaser(Agent, AskUserHookAgentMixin):
    """Takes turns with the other chaser on every stage: writes, builds, and checks the other's work."""

    _permission = CHASER_PERMISSION
    _skills = ("wordbeat",)


class Agents(AgentCollection):
    first_chaser: Chaser
    second_chaser: Chaser
    human: Outworlder


class Workspace(LocalEnv, BashEnvMixin, FilesEnvMixin, MemoryEnvMixin):
    """The directory the run starts in, holding the project; the flow runs the toolkit there."""

    # ACE-Step waits for 12 GB to be free before each job; the renders and models need room beside it.
    _memory = 16 * 2**30


class Envs(EnvCollection):
    workspace: Workspace


async def _run(order: tuple[str, ...], task: str, agents: Agents, envs: Envs, params: Config, ctx: FlowContext) -> str:
    engine = Engine(task, agents, envs, params, ctx.state)
    said = await engine.drive(order, "position:" + "+".join(order))
    print(said, flush=True)
    return said


@flow(agents=Agents, envs=Envs, params=Config, resumable=True)
async def wordbeat(task: str, *, agents: Agents, envs: Envs, params: Config, ctx: FlowContext) -> str:
    """A word-synced explainer video from a brief: two agents take turns on every stage, measured."""
    return await _run(ORDER, task, agents, envs, params, ctx)


@flow(agents=Agents, envs=Envs, params=Config, resumable=True)
async def script(task: str, *, agents: Agents, envs: Envs, params: Config, ctx: FlowContext) -> str:
    """wordbeat's script stage alone: script.txt written, linted and agreed."""
    return await _run(("script",), task, agents, envs, params, ctx)


@flow(agents=Agents, envs=Envs, params=Config, resumable=True)
async def voice(task: str, *, agents: Agents, envs: Envs, params: Config, ctx: FlowContext) -> str:
    """wordbeat's voice stage alone: the narration voiced, timed and every line read right."""
    return await _run(("voice",), task, agents, envs, params, ctx)


@flow(agents=Agents, envs=Envs, params=Config, resumable=True)
async def film(task: str, *, agents: Agents, envs: Envs, params: Config, ctx: FlowContext) -> str:
    """wordbeat's sample and film stages: the picture built, rendered and measured."""
    return await _run(("sample", "film"), task, agents, envs, params, ctx)


@flow(agents=Agents, envs=Envs, params=Config, resumable=True)
async def music(task: str, *, agents: Agents, envs: Envs, params: Config, ctx: FlowContext) -> str:
    """wordbeat's music stage alone: the music bed briefed, rendered and measured."""
    return await _run(("music",), task, agents, envs, params, ctx)


@flow(agents=Agents, envs=Envs, params=Config, resumable=True)
async def finish(task: str, *, agents: Agents, envs: Envs, params: Config, ctx: FlowContext) -> str:
    """wordbeat's finish stage alone: mixed, measured, cover and publish notes written."""
    return await _run(("finish",), task, agents, envs, params, ctx)

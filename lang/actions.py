from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any
from .ast_nodes import Expression
from .context import EvalContext, ExecutionResult
from .errors import CompileError, RuntimeFault


# ------------------------- validadores compartidos ------------------------- 

def _expect_int(value: Any, line: int, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise RuntimeFault(
            line,
            f"{name} debe ser un entero, se recibio {type(value).__name__}",
        )
    return value

def _expect_direction(value: Any, line: int, name: str) -> int:
    value = _expect_int(value, line, name)
    if value not in (-1, 0, 1):
        raise RuntimeFault(
            line,
            f"{name} debe ser -1, 0 o 1, se recibio {value}",
        )
    return value

# ------------------------- base -------------------------

class Action(ABC):
    name: str = ""
    arity: int = 0

    def __init__(self, args: list[Expression], line: int) -> None:
        self.args = args
        self.line = line
        if len(args) != self.arity:
            raise CompileError(
                line,
                f"{self.name} espera {self.arity} argumento(s), "
                f"recibió {len(args)}",
            )

    def _eval_args(self, ctx: EvalContext) -> list[Any]:
        return [arg.evaluate(ctx) for arg in self.args]

    @abstractmethod
    def execute(self, ctx: EvalContext) -> ExecutionResult: ...

    def __repr__(self) -> str:
        return f"{type(self).__name__}({len(self.args)} args)"

# ------------------------- wait(n) -------------------------

class WaitAction(Action):
    name = "wait"
    arity = 1

    def execute(self, ctx: EvalContext) -> ExecutionResult:
        (raw,) = self._eval_args(ctx)
        n = _expect_int(raw, self.line, "n de wait")
        n = max(1, n)
        ctx.creature.wait_ticks = n - 1
        return ExecutionResult(consumed_turn=True)

# ------------------------- move(dx, dy, speed) -------------------------

class MoveAction(Action):
    name = "move"
    arity = 3

    def execute(self, ctx: EvalContext) -> ExecutionResult:
        dx_raw, dy_raw, speed_raw = self._eval_args(ctx)
        dx = _expect_direction(dx_raw, self.line, "dx de move")
        dy = _expect_direction(dy_raw, self.line, "dy de move")
        speed = _expect_int(speed_raw, self.line, "speed de move")
        speed = max(0, speed)

        for _ in range(speed):
            if not ctx.world.step_creature(ctx.creature, dx, dy):
                break

        return ExecutionResult(consumed_turn=True)

# ------------------------- attack(dx, dy, damage) -------------------------

class AttackAction(Action):
    name = "attack"
    arity = 3

    def execute(self, ctx: EvalContext) -> ExecutionResult:
        dx_raw, dy_raw, damage_raw = self._eval_args(ctx)
        dx = _expect_direction(dx_raw, self.line, "dx de attack")
        dy = _expect_direction(dy_raw, self.line, "dy de attack")
        damage = _expect_int(damage_raw, self.line, "damage de attack")

        if dx == 0 and dy == 0:
            # el objetivo es el terreno bajo la propia criatura.
            ctx.world.damage_terrain_at(ctx.creature.x, ctx.creature.y, damage)
        else:
            ctx.world.damage_at(
                ctx.creature.x + dx,
                ctx.creature.y + dy,
                damage,
            )

        return ExecutionResult(consumed_turn=True)

# ------------------------- consume(dx, dy, damage, heal) -------------------------

class ConsumeAction(Action):
    name = "consume"
    arity = 4

    def execute(self, ctx: EvalContext) -> ExecutionResult:
        dx_raw, dy_raw, damage_raw, heal_raw = self._eval_args(ctx)
        dx = _expect_direction(dx_raw, self.line, "dx de consume")
        dy = _expect_direction(dy_raw, self.line, "dy de consume")
        damage = _expect_int(damage_raw, self.line, "damage de consume")
        heal = _expect_int(heal_raw, self.line, "heal de consume")

        if dx == 0 and dy == 0:
            ctx.world.damage_terrain_at(ctx.creature.x, ctx.creature.y, damage)
        else:
            ctx.world.damage_at(
                ctx.creature.x + dx,
                ctx.creature.y + dy,
                damage,
            )

        ctx.creature.health += heal
        return ExecutionResult(consumed_turn=True)

# ------------------------- reproduce(dx, dy, health) -------------------------

class ReproduceAction(Action):
    name = "reproduce"
    arity = 3

    def execute(self, ctx: EvalContext) -> ExecutionResult:
        dx_raw, dy_raw, health_raw = self._eval_args(ctx)
        dx = _expect_direction(dx_raw, self.line, "dx de reproduce")
        dy = _expect_direction(dy_raw, self.line, "dy de reproduce")
        health = _expect_int(health_raw, self.line, "health de reproduce")

        ctx.spawn_creature(dx, dy, health, self.line)
        return ExecutionResult(consumed_turn=True)

# ------------------------- roar(value) -------------------------

class RoarAction(Action):
    name = "roar"
    arity = 1

    def execute(self, ctx: EvalContext) -> ExecutionResult:
        (value,) = self._eval_args(ctx)
        ctx.world.emit_roar(ctx.creature, value)
        return ExecutionResult(consumed_turn=True)

# ------------------------- say(value) -------------------------

class SayAction(Action):
    name = "say"
    arity = 1

    def execute(self, ctx: EvalContext) -> ExecutionResult:
        (value,) = self._eval_args(ctx)
        ctx.world.emit_say(ctx.creature, value)
        # say NO consume turno
        return ExecutionResult(consumed_turn=False)

# ------------------------- registro de acciones para el parser ------------------

ACTIONS: dict[str, type[Action]] = {
    cls.name: cls
    for cls in (
        WaitAction,
        MoveAction,
        AttackAction,
        ConsumeAction,
        ReproduceAction,
        RoarAction,
        SayAction,
    )
}

def make_action(name: str, args: list[Expression], line: int) -> Action:
    """fabrica que usa el parser. Lanza CompileError si la accion no existe."""
    cls = ACTIONS.get(name)
    if cls is None:
        raise CompileError(line, f"acción desconocida: {name!r}")
    return cls(args, line)
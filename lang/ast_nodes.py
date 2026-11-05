from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Protocol
from .context import EvalContext, ExecutionResult
from .errors import CompileError, RuntimeFault

# --------------------- utilidades de evaluacion ---------------------

def _truthy(value: Any) -> bool:
    """falso solo para entero 0 y texto vacio. Todo lo demas es verdadero."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        return value != ""
    return True

def _type_name(value: Any) -> str:
    if isinstance(value, int):
        return "entero"
    if isinstance(value, str):
        return "texto"
    return type(value).__name__

def _apply_binary(op: str, left: Any, right: Any, line: int) -> Any:
    if op == "==":
        if type(left) is not type(right):
            raise RuntimeFault(
                line,
                f"no se puede comparar {_type_name(left)} con {_type_name(right)}",
            )
        return 1 if left == right else 0

    if op == "!=":
        if type(left) is not type(right):
            raise RuntimeFault(
                line,
                f"no se puede comparar {_type_name(left)} con {_type_name(right)}",
            )
        return 1 if left != right else 0

    if not isinstance(left, int) or not isinstance(right, int):
        raise RuntimeFault(
            line,
            f"el operador {op!r} requiere enteros, "
            f"recibió {_type_name(left)} y {_type_name(right)}",
        )

    if op == "+": return left + right
    if op == "-": return left - right
    if op == "*": return left * right
    if op == "/":
        if right == 0:
            raise RuntimeFault(line, "división por cero")
        return left // right
    if op == "%":
        if right == 0:
            raise RuntimeFault(line, "resto por cero")
        return left % right
    if op == "<":  return 1 if left < right else 0
    if op == "<=": return 1 if left <= right else 0
    if op == ">":  return 1 if left > right else 0
    if op == ">=": return 1 if left >= right else 0

    raise RuntimeFault(line, f"operador binario desconocido: {op!r}")

# -------------------- expresiones --------------------

class Expression(ABC):
    line: int

    @abstractmethod
    def evaluate(self, ctx: EvalContext) -> Any: ...

@dataclass
class Literal(Expression):
    value: int | str
    line: int

    def evaluate(self, ctx: EvalContext) -> Any:
        return self.value

@dataclass
class Variable(Expression):
    name: str
    line: int

    def evaluate(self, ctx: EvalContext) -> Any:
        return ctx.resolve_variable(self.name, self.line)

@dataclass
class BinaryOp(Expression):
    op: str
    left: Expression
    right: Expression
    line: int

    def evaluate(self, ctx: EvalContext) -> Any:
        if self.op == "and":
            left = self.left.evaluate(ctx)
            if not _truthy(left):
                return 0
            right = self.right.evaluate(ctx)
            return 1 if _truthy(right) else 0

        if self.op == "or":
            left = self.left.evaluate(ctx)
            if _truthy(left):
                return 1
            right = self.right.evaluate(ctx)
            return 1 if _truthy(right) else 0

        left = self.left.evaluate(ctx)
        right = self.right.evaluate(ctx)
        return _apply_binary(self.op, left, right, self.line)

@dataclass
class UnaryOp(Expression):
    op: str            # "neg" o "not"
    operand: Expression
    line: int

    def evaluate(self, ctx: EvalContext) -> Any:
        value = self.operand.evaluate(ctx)
        if self.op == "not":
            return 0 if _truthy(value) else 1
        if self.op == "neg":
            if not isinstance(value, int):
                raise RuntimeFault(
                    self.line,
                    f"el menos unario requiere un entero, recibió {_type_name(value)}",
                )
            return -value
        raise RuntimeFault(self.line, f"operador unario desconocido: {self.op!r}")

@dataclass
class CallExpr(Expression):
    name: str
    args: list[Expression]
    line: int

    def evaluate(self, ctx: EvalContext) -> Any:
        values = [arg.evaluate(ctx) for arg in self.args]
        return ctx.call_function(self.name, values, self.line)

# ---------------------- instrucciones ----------------------

class Statement(ABC):
    line: int

    @abstractmethod
    def execute(self, ctx: EvalContext) -> ExecutionResult: ...

@dataclass
class LabelStmt(Statement):
    name: str
    line: int

    def execute(self, ctx: EvalContext) -> ExecutionResult:
        # las etiquetas no hacen nada al ejecutarse; el inteprete las resolvio antes.
        return ExecutionResult()

@dataclass
class GotoStmt(Statement):
    target: str
    line: int

    def execute(self, ctx: EvalContext) -> ExecutionResult:
        return ExecutionResult(consumed_turn=False, next_label=self.target)

@dataclass
class IfGotoStmt(Statement):
    condition: Expression
    target: str
    line: int

    def execute(self, ctx: EvalContext) -> ExecutionResult:
        cond = self.condition.evaluate(ctx)
        if _truthy(cond):
            return ExecutionResult(consumed_turn=False, next_label=self.target)
        return ExecutionResult()

@dataclass
class AssignStmt(Statement):
    name: str
    value: Expression
    line: int

    def execute(self, ctx: EvalContext) -> ExecutionResult:
        ctx.set_variable(self.name, self.value.evaluate(ctx))
        return ExecutionResult()

class ExecutableAction(Protocol):
    """protocolo minimo que un Action debe cumplir para vivir en un ActionStmt."""
    name: str
    line: int
    def execute(self, ctx: EvalContext) -> ExecutionResult: ...

@dataclass
class ActionStmt(Statement):
    action: ExecutableAction
    line: int

    def execute(self, ctx: EvalContext) -> ExecutionResult:
        return self.action.execute(ctx)

# -------------------- programa completo --------------------

@dataclass
class Header:
    species: str
    faction: str
    health: int
    vision: int
    lifespan: int

@dataclass
class Program:
    header: Header
    statements: list[Statement] = field(default_factory=list)
    labels: dict[str, int] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        # registrar etiquetas y validar duplicados
        for i, stmt in enumerate(self.statements):
            if isinstance(stmt, LabelStmt):
                if stmt.name in self.labels:
                    raise CompileError(
                        stmt.line,
                        f"etiqueta duplicada: {stmt.name!r}",
                    )
                self.labels[stmt.name] = i

        # la etiqueta start: es obligatoria
        if "start" not in self.labels:
            raise CompileError(None, "falta la etiqueta obligatoria 'start:'")

        # todo goto debe apuntar a una etiqueta existente
        for stmt in self.statements:
            if isinstance(stmt, (GotoStmt, IfGotoStmt)):
                if stmt.target not in self.labels:
                    raise CompileError(
                        stmt.line,
                        f"etiqueta no definida: {stmt.target!r}",
                    )
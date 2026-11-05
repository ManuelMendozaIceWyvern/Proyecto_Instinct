from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class ExecutionResult:
    """lo que devuelve ejecutar un Statement."""
    consumed_turn: bool = False
    next_label: str | None = None


class EvalContext(Protocol):
    """interfaz que el interprete implementa para que los nodos se evaluen."""

    creature: Any
    world: Any

    def resolve_variable(self, name: str, line: int) -> Any:
        """devuelve el valor de una variable propia o percepcion"""
        ...

    def set_variable(self, name: str, value: Any) -> None:
        """asigna una variable propia."""
        ...

    def call_function(self, name: str, args: list[Any], line: int) -> Any:
        """llama a una funcion reservada como see o name."""
        ...

    def spawn_creature(self, dx: int, dy: int, health: int, line: int) -> None:
        """crea una cria de la misma especie en la casilla adyacente.
        Si no puede (casilla ocupada, poca vida...), no hace nada."""
        ...
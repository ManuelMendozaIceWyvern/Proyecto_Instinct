from __future__ import annotations
import random as _random
from typing import Any
from core.world import Creature, World
from .ast_nodes import Program
from .constants import CONSTANTS, PERCEPTION_NAMES
from .context import EvalContext, ExecutionResult
from .errors import RuntimeFault
from .perceptions import compute_perceptions, name_at, random_value, see


class CreatureContext(EvalContext):
    """implementa EvalContext para una criatura concreta en un turno."""
    def __init__(self, creature: Creature, world: World, program: Program) -> None:
        self.creature = creature
        self.world = world
        self.program = program
        self.perceptions: dict[str, Any] = compute_perceptions(creature, world)

    # -------------- variables ------------------------

    def resolve_variable(self, name: str, line: int) -> Any:
        if name == "random":
            return random_value()
        if name in self.creature.variables:
            return self.creature.variables[name]
        if name in self.perceptions:
            return self.perceptions[name]
        if name in CONSTANTS:
            return CONSTANTS[name]
        raise RuntimeFault(line, f"variable no definida: {name!r}")

    def set_variable(self, name: str, value: Any) -> None:
        if name in PERCEPTION_NAMES or name in CONSTANTS:
            raise RuntimeFault(
                None,
                f"no se puede asignar a la percepcion/constante {name!r}",
            )
        self.creature.variables[name] = value

    # --- funciones reservadas ---

    def call_function(self, name: str, args: list[Any], line: int) -> Any:
        if name == "see":
            if len(args) != 2:
                raise RuntimeFault(line, f"see espera 2 argumentos, recibio {len(args)}")
            x, y = args
            if not isinstance(x, int) or not isinstance(y, int):
                raise RuntimeFault(line, "see requiere dos enteros")
            return see(self.creature, self.world, x, y)

        if name == "name":
            if len(args) != 2:
                raise RuntimeFault(line, f"name espera 2 argumentos, recibio {len(args)}")
            x, y = args
            if not isinstance(x, int) or not isinstance(y, int):
                raise RuntimeFault(line, "name requiere dos enteros")
            return name_at(self.creature, self.world, x, y)

        raise RuntimeFault(line, f"funcion desconocida: {name!r}")

    # ------------------------- reproduccion ------------------------------

    def spawn_creature(self, dx: int, dy: int, health: int, line: int) -> None:
        mother = self.creature
        world = self.world

        if dx == 0 and dy == 0:
            return
        if dx not in (-1, 0, 1) or dy not in (-1, 0, 1):
            return
        if mother.health <= health:
            return

        nx, ny = mother.x + dx, mother.y + dy
        if not world.is_walkable(nx, ny):
            return

        child = Creature(
            species=mother.species,
            faction=mother.faction,
            health=health,
            vision=mother.vision,
            lifespan=mother.lifespan,
            x=nx,
            y=ny,
        )
        child.program = self.program
        child.program_counter = self.program.labels["start"]

        if not world.place_creature(child, nx, ny):
            return

        mother.health -= health

class Interpreter:
    """ejecuta el programa de una criatura durante un turno."""

    def __init__(self, max_lines_per_turn: int = 100) -> None:
        self.max_lines = max_lines_per_turn

    def run_turn(self, creature: Creature, world: World) -> None:
        if creature.program is None:
            return

        # Dormida por wait(n)
        if creature.wait_ticks > 0:
            creature.wait_ticks -= 1
            return

        ctx = CreatureContext(creature, world, creature.program)
        program = creature.program
        pc = creature.program_counter
        lines = 0
        consumed = False

        while lines < self.max_lines:
            if pc >= len(program.statements):
                pc = program.labels["start"]

            stmt = program.statements[pc]
            try:
                result: ExecutionResult = stmt.execute(ctx)
            except RuntimeFault as e:
                world.log.append(
                    f"[tick {world.tick_count}] {creature.species} "
                    f"({creature.x},{creature.y}): {e}"
                )
                world.remove_creature(creature)
                return

            lines += 1

            if result.next_label is not None:
                pc = program.labels[result.next_label]
            else:
                pc += 1

            if result.consumed_turn:
                consumed = True
                break

        # Si no consumio turno en 100 líneas, el turno termina igual.
        creature.program_counter = pc
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional


# -------- entidades del mundo---------

class WorldEntity(ABC):
    """clase base para todo lo que ocupa una casilla 
    y puede recibir daño (criaturas, objetos, terreno)"""

    def __init__(self, name: str, char: str) -> None:
        self.name = name
        self.char = char

    @abstractmethod
    def take_damage(self, amount: int) -> None:
        ...

    @abstractmethod
    def is_alive(self) -> bool:
        ...

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.name!r})"

class ResourceEntity(WorldEntity):
    """entidad con una reserva que se puede agotar (objetos)"""

    def __init__(self, name: str, char: str, resource_max: int) -> None:
        super().__init__(name, char)
        self.resource_max = resource_max
        self.reserve = resource_max

    def take_damage(self, amount: int) -> None:
        """asume danno sin llegar a negativo"""
        self.reserve = max(0, self.reserve - amount)

    def is_alive(self) -> bool:
        return self.reserve > 0

class Terrain(ResourceEntity):
    """terreno, no desaparece, se regenera en cada tick."""

    def __init__(self, name: str, char: str, resource_max: int, regen: int) -> None:
        super().__init__(name, char, resource_max)
        self.regen = regen

    def regenerate(self) -> None:
        """se regenera cada tick pero pa q no se pase del max"""
        self.reserve = min(self.resource_max, self.reserve + self.regen)

    def is_alive(self) -> bool:
        # El terreno no muere: con reserva 0 sigue ahí.
        return True

class WorldObject(ResourceEntity):
    """objeto en el terreno. No se regenera y desaparece con reserva <= 0."""

    def __init__(self, name: str, char: str, resource_max: int) -> None:
        super().__init__(name, char, resource_max)

class Creature(WorldEntity):
    """critaura viva"""

    def __init__(
        self,
        species: str,
        faction: str,
        health: int,
        vision: int,
        lifespan: int,
        x: int = 0,
        y: int = 0,
    ) -> None:
        super().__init__(species, "@")
        self.species = species
        self.faction = faction
        self.health = health
        self.vision = vision
        self.lifespan = lifespan
        self.age = 0
        self.x = x
        self.y = y

        # ---- estado del programa (lo rellena el interprete) ----
        self.program = None            # programa de la creature
        self.variables: dict = {}      # variables propias de la criatura
        self.program_counter = 0       # indice de la proxima instruccion
        self.wait_ticks = 0            # si > 0, esta dormida

    def take_damage(self, amount: int) -> None:
        self.health = min(0, self.health - amount)

    def is_alive(self) -> bool:
        return self.health > 0 and self.age < self.lifespan

    def is_same_faction(self, other: "Creature") -> bool:
        return self.faction == other.faction

    def __repr__(self) -> str:
        return (
            f"Creature({self.species!r}, faction={self.faction!r}, "
            f"hp={self.health}, age={self.age})"
        )

# ------------------- Casilla -------------------

class Cell:
    """casilla: siempre tiene terreno, y encima un objeto o una criatura."""

    def __init__(self, x: int, y: int, terrain: Terrain) -> None:
        self.x = x
        self.y = y
        self.terrain = terrain
        self.occupant: Optional[WorldEntity] = None  # WorldObject o Creature

    @property
    def creature(self) -> Optional[Creature]:
        return self.occupant if isinstance(self.occupant, Creature) else None

    @property
    def world_object(self) -> Optional[WorldObject]:
        return self.occupant if isinstance(self.occupant, WorldObject) else None

    @property
    def is_empty(self) -> bool:
        return self.occupant is None

    @property
    def is_walkable(self) -> bool:
        return self.occupant is None

    def __repr__(self) -> str:
        content = self.occupant.char if self.occupant else self.terrain.char
        return f"Cell({self.x},{self.y},{content!r})"

# --------------------- Mundo ---------------------

class World:
    """grilla de casillas + la lista de criaturas vivas."""

    def __init__(self, terrains: list[list[Terrain]]) -> None:
        self.height = len(terrains)
        self.width = len(terrains[0]) if self.height > 0 else 0
        self.tick_count = 0
        self.grid: list[list[Cell]] = [
            [Cell(x, y, terrains[y][x]) for x in range(self.width)]
            for y in range(self.height)
        ]
        self.creatures: list[Creature] = []
        self.roars_last_tick: list[tuple[Creature, object]] = []
        self.roars_this_tick: list[tuple[Creature, object]] = []
        self.log: list[str] = []

    @classmethod
    def filled(cls, width: int, height: int, terrain_factory) -> "World":
        """construye un mundo lleno del mismo terreno (para probar)."""
        terrains = [
            [terrain_factory(x, y) for x in range(width)]
            for y in range(height)
        ]
        return cls(terrains)

    # --- acceso a casillas ---

    def is_inside(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def get_cell(self, x: int, y: int) -> Optional[Cell]:
        if not self.is_inside(x, y):
            return None
        return self.grid[y][x]

    def creature_at(self, x: int, y: int) -> Optional[Creature]:
        cell = self.get_cell(x, y)
        return cell.creature if cell else None

    def object_at(self, x: int, y: int) -> Optional[WorldObject]:
        cell = self.get_cell(x, y)
        return cell.world_object if cell else None

    def terrain_at(self, x: int, y: int) -> Optional[Terrain]:
        cell = self.get_cell(x, y)
        return cell.terrain if cell else None

    def is_walkable(self, x: int, y: int) -> bool:
        cell = self.get_cell(x, y)
        return cell is not None and cell.is_walkable

    # --- gestión de criaturas ---
    
    def place_creature(self, creature: Creature, x: int, y: int) -> bool:
        cell = self.get_cell(x, y)
        if cell is None or not cell.is_empty:
            return False
        creature.x = x
        creature.y = y
        cell.occupant = creature
        self.creatures.append(creature)
        return True

    def step_creature(self, creature: Creature, dx: int, dy: int) -> bool:
        """mueve la criatura 1 casilla en (dx, dy). False si no puede."""
        new_x = creature.x + dx
        new_y = creature.y + dy
        if not self.is_walkable(new_x, new_y):
            return False
        return self.move_creature(creature, new_x, new_y)

    def move_creature(self, creature: Creature, new_x: int, new_y: int) -> bool:
        """mueve la criatura a una casilla vacia"""
        target = self.get_cell(new_x, new_y)
        if target is None or not target.is_empty:
            return False
        old = self.get_cell(creature.x, creature.y)
        if old is not None and old.occupant is creature:
            old.occupant = None
        creature.x = new_x
        creature.y = new_y
        target.occupant = creature
        return True

    def remove_creature(self, creature: Creature) -> None:
        cell = self.get_cell(creature.x, creature.y)
        if cell is not None and cell.occupant is creature:
            cell.occupant = None
        if creature in self.creatures:
            self.creatures.remove(creature)

    def emit_roar(self, creature: Creature, value: object) -> None:
        self.roars_this_tick.append((creature, value))

    def emit_say(self, creature: Creature, value: object) -> None:
        self.log.append(
            f"[tick {self.tick_count}] {creature.species}@{creature.x},{creature.y}: {value}"
        )

    # --- daño / consumo ---
    
    def damage_at(self, x: int, y: int, amount: int) -> None:
        """aplica daño a lo que haya en la casilla, o al terreno si no hay na.
        Afuera del mapa no hace nada."""
        cell = self.get_cell(x, y)
        if cell is None:
            return
        
        target = cell.occupant
        if target is None:
            cell.terrain.take_damage(amount)
            return

        target.take_damage(amount)
        if not target.is_alive():
            cell.occupant = None
            if isinstance(target, Creature) and target in self.creatures:
                self.creatures.remove(target)

    def damage_terrain_at(self, x: int, y: int, amount: int) -> None:
        """daña solo el terreno, ignorando cualquier ocupante."""
        cell = self.get_cell(x, y)
        if cell is not None:
            cell.terrain.take_damage(amount)

    # --- tick ---

    def tick(self) -> None:
        """avanza un tick aplicando las reglas de fin de tick."""
        self._advance_creatures()
        self._remove_dead_creatures()
        self._regenerate_terrain()
        self._remove_empty_objects()
        self.roars_last_tick = self.roars_this_tick
        self.roars_this_tick = []
        self.tick_count += 1

    def _advance_creatures(self) -> None:
        for creature in self.creatures:
            creature.health -= 1
            creature.age += 1

    def _remove_dead_creatures(self) -> None:
        for creature in list(self.creatures):
            if not creature.is_alive():
                self.remove_creature(creature)

    def _regenerate_terrain(self) -> None:
        for row in self.grid:
            for cell in row:
                cell.terrain.regenerate()

    def _remove_empty_objects(self) -> None:
        for row in self.grid:
            for cell in row:
                obj = cell.world_object
                if obj is not None and not obj.is_alive():
                    cell.occupant = None

    # --- conteos utiles para percepciones ---

    def count_creatures(self, exclude: Optional[Creature] = None) -> int:
        return sum(1 for c in self.creatures if c is not exclude)

    def count_allies(self, creature: Creature) -> int:
        return sum(
            1 for c in self.creatures
            if c is not creature and c.faction == creature.faction
        )

    def count_enemies(self, creature: Creature) -> int:
        return sum(
            1 for c in self.creatures
            if c is not creature and c.faction != creature.faction
        )

    # --- render ASCII para depurar ---
    
    def render(self) -> str:
        lines = []
        for row in self.grid:
            lines.append("".join(
                cell.occupant.char if cell.occupant else cell.terrain.char
                for cell in row
            ))
        return "\n".join(lines)
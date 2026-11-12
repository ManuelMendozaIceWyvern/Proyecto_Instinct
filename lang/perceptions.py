from __future__ import annotations
import random as _random
from typing import Any
from core.world import Creature, World
from .constants import NONE


def compute_perceptions(creature: Creature, world: World) -> dict[str, Any]:
    """Calcula todas las percepciones estaticas de una criatura en este turno.
    'random' no se incluye: se evalua cada vez que se lee."""
    c = creature
    w = world
    p: dict[str, Any] = {}

    # -------- sobre si misma --------

    p["health"] = c.health
    p["age"] = c.age
    p["lifespan"] = c.lifespan
    p["vision"] = c.vision
    p["species"] = c.species
    p["faction"] = c.faction
    p["x"] = c.x
    p["y"] = c.y

    cell = w.get_cell(c.x, c.y)
    if cell is not None:
        p["terrain_here"] = cell.terrain.name
        p["reserve_here"] = cell.terrain.reserve
    else:
        p["terrain_here"] = ""
        p["reserve_here"] = 0

    # --- sobre el mundo ---

    p["width"] = w.width
    p["height"] = w.height
    p["tick"] = w.tick_count
    p["total_creatures"] = w.count_creatures(exclude=c)
    p["total_allies"] = w.count_allies(c)
    p["total_enemies"] = w.count_enemies(c)

    # --- sobre lo cercano ---

    allies_near = 0
    enemies_near = 0
    objects_near = 0
    enemy_candidates: list[tuple[int, int, int]] = []
    ally_candidates: list[tuple[int, int, int]] = []
    object_candidates: list[tuple[int, int, int]] = []

    vision = c.vision
    for dy in range(-vision, vision + 1):
        for dx in range(-vision, vision + 1):
            if dx == 0 and dy == 0:
                continue
            dist = max(abs(dx), abs(dy))
            if dist > vision:
                continue
            nx, ny = c.x + dx, c.y + dy
            if not w.is_inside(nx, ny):
                continue
            ncell = w.get_cell(nx, ny)
            if ncell.creature is not None:
                other = ncell.creature
                if other.faction == c.faction:
                    allies_near += 1
                    ally_candidates.append((dist, dx, dy))
                else:
                    enemies_near += 1
                    enemy_candidates.append((dist, dx, dy))
            elif ncell.world_object is not None:
                objects_near += 1
                object_candidates.append((dist, dx, dy))

    p["allies_near"] = allies_near
    p["enemies_near"] = enemies_near
    p["objects_near"] = objects_near

    def _normalize(v: int) -> int:
        if v > 0:
            return 1
        if v < 0:
            return -1
        return 0

    def closest(candidates: list[tuple[int, int, int]]) -> tuple[int, int, int]:
        if not candidates:
            return -1, 0, 0
        # orden determinista: por distancia, luego por dx, luego por dy.
        candidates.sort(key=lambda t: (t[0], t[1], t[2]))
        dist, dx, dy = candidates[0]
        return dist, _normalize(dx), _normalize(dy)

    p["enemy_dist"], p["enemy_dx"], p["enemy_dy"] = closest(enemy_candidates)
    p["ally_dist"], p["ally_dx"], p["ally_dy"] = closest(ally_candidates)
    p["object_dist"], p["object_dx"], p["object_dy"] = closest(object_candidates)

    # --- rugidos del tick anterior ---

    roars_near = 0
    last_roar = ""
    for r_creature, value in w.roars_last_tick:
        if r_creature is c:
            continue
        dist = max(abs(r_creature.x - c.x), abs(r_creature.y - c.y))
        if dist <= vision:
            roars_near += 1
            last_roar = str(value)
    p["roars_near"] = roars_near
    p["last_roar"] = last_roar

    return p

def see(creature: Creature, world: World, x: int, y: int) -> int:
    """implementa see(x, y)."""
    c = creature
    if max(abs(x - c.x), abs(y - c.y)) > c.vision:
        return NONE
    if not world.is_inside(x, y):
        return 1  # OBJECT: el borde se comporta como muro
    cell = world.get_cell(x, y)
    if cell.creature is not None:
        return 2 if cell.creature.faction == c.faction else 3
    if cell.world_object is not None:
        return 1  # OBJECT
    return 0  # GROUND

def name_at(creature: Creature, world: World, x: int, y: int) -> str:
    """implementa name(x, y)."""
    c = creature
    if max(abs(x - c.x), abs(y - c.y)) > c.vision:
        return ""
    if not world.is_inside(x, y):
        return ""
    cell = world.get_cell(x, y)
    if cell.creature is not None:
        return cell.creature.species
    if cell.world_object is not None:
        return cell.world_object.name
    return cell.terrain.name

def random_value() -> int:
    """entero aleatorio entre 0 y 99, distinto cada vez que se lee."""
    return _random.randint(0, 99)
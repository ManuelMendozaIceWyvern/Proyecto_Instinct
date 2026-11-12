from __future__ import annotations
import random as _random
from core.world import World
from .interpreter import Interpreter


class Simulation:
    def __init__(self, world: World, seed: int | None = None) -> None:
        self.world = world
        self.interpreter = Interpreter()
        if seed is not None:
            _random.seed(seed)

    def step(self) -> None:
        """avanza un tick: turnos en orden aleatorio y reglas de fin de tick."""
        creatures = list(self.world.creatures)
        _random.shuffle(creatures)

        for creature in creatures:
            # como puede haber muerto por una accion anterior en este mismo tick reviso
            if creature in self.world.creatures:
                self.interpreter.run_turn(creature, self.world)

        self.world.tick()
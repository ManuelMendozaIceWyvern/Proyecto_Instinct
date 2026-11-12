from __future__ import annotations
import argparse
import time
from pathlib import Path
from core.world import World
from loaders import (
    LoadError,
    build_world,
    creature_from_program,
    load_creatures_from_dir,
    load_objects_from_dir,
    load_terrains_from_dir,
    parse_map_file,
)
from lang.simulation import Simulation

"""ejecuta una simulacion completa desde terminal.
Modos:
  CLI:        python run_simulation.py --map "Plano con piedrita" --creature "Orc@3,2" --ticks 100
  Interactivo: python run_simulation.py"""


class SimulationRunner:
    """carga datos, prepara un mundo y ejecuta ticks."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.terrains: dict = {}
        self.objects: dict = {}
        self.map_data: dict = {}
        self.creatures: dict = {}
        self.errors: list[LoadError] = []

    def load_all(self) -> list[LoadError]:
        self.terrains, e1 = load_terrains_from_dir(self.data_dir / "terrains")
        self.objects, e2 = load_objects_from_dir(
            self.data_dir / "objects", self.terrains
        )
        self.creatures, e4 = load_creatures_from_dir(self.data_dir / "creatures")
        self.errors = e1 + e2 + e4

        maps_dir = self.data_dir / "maps"
        if not maps_dir.is_dir():
            self.errors.append(LoadError(
                str(maps_dir), None, "el directorio de mapas no existe",
            ))
            return self.errors

        for path in sorted(maps_dir.glob("*.map")):
            try:
                md = parse_map_file(path)
            except LoadError as e:
                self.errors.append(e)
                continue
            if md.name in self.map_data:
                self.errors.append(LoadError(
                    str(path), None,
                    f"ya existe un mapa con el nombre {md.name!r}",
                ))
                continue
            self.map_data[md.name] = md

        return self.errors

    def prepare(
        self,
        map_name: str,
        placements: list[tuple[str, int, int]],
    ) -> World:
        if map_name not in self.map_data:
            raise ValueError(f"mapa no encontrado: {map_name!r}")
        md = self.map_data[map_name]
        world = build_world(md, self.terrains, self.objects)

        for species, x, y in placements:
            if species not in self.creatures:
                raise ValueError(f"criatura no encontrada: {species!r}")
            creature = creature_from_program(self.creatures[species])
            if not world.place_creature(creature, x, y):
                raise ValueError(
                    f"no se puede colocar {species} en ({x},{y}): "
                    f"fuera del mapa u ocupada"
                )
        return world

    def run(
        self,
        world: World,
        ticks: int,
        seed: int | None,
        delay: float,
        render: bool,
    ) -> None:
        sim = Simulation(world, seed=seed)

        for _ in range(ticks):
            if render:
                self._print_state(world)
            if not world.creatures:
                if render:
                    print("\nTodas las criaturas han muerto.")
                break
            sim.step()
            if delay > 0:
                time.sleep(delay)

        if render:
            self._print_state(world)
            print(f"\nFin de la simulacion en tick {world.tick_count}.")
        self._print_log(world)

    @staticmethod
    def _print_state(world: World) -> None:
        print(f"\n--- Tick {world.tick_count} ---")
        print(world.render())
        print(f"Criaturas vivas: {len(world.creatures)}")
        for c in world.creatures:
            print(
                f"  {c.species:<10} @({c.x},{c.y}) "
                f"hp={c.health:<4} age={c.age:<4} faction={c.faction}"
            )

    @staticmethod
    def _print_log(world: World) -> None:
        if not world.log:
            print("\n(log vacio)")
            return
        print("\n--- Log ---")
        for line in world.log:
            print(line)

def parse_placement(text: str) -> tuple[str, int, int]:
    species, sep, coords = text.partition("@")
    if not sep:
        raise argparse.ArgumentTypeError(
            f"formato esperado 'Especie@x,y', se recibio {text!r}"
        )
    try:
        x_str, y_str = coords.split(",")
        return species, int(x_str), int(y_str)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"coordenadas invalidas en {text!r}, esperado 'x,y'"
        )

def cli_mode(runner: SimulationRunner, args: argparse.Namespace) -> None:
    try:
        world = runner.prepare(args.map, args.creature or [])
    except ValueError as e:
        print(f"Error: {e}")
        return
    runner.run(world, args.ticks, args.seed, args.delay, render=not args.quiet)

def interactive_mode(runner: SimulationRunner) -> None:
    print("=== Simulacion interactiva ===")
    print(f"\nMapas disponibles: {sorted(runner.map_data)}")
    map_name = input("Mapa: ").strip()
    if map_name not in runner.map_data:
        print(f"Mapa no encontrado: {map_name!r}")
        return

    md = runner.map_data[map_name]
    print(f"\nMapa '{map_name}' ({md.width}x{md.height}):")
    print("     " + "".join(str(x % 10) for x in range(md.width)))
    for y, row in enumerate(md.rows):
        print(f"  {y:>2} {row}")

    print(f"\nCriaturas disponibles: {sorted(runner.creatures)}")
    print("Introduce colocaciones 'Especie@x,y' (vacío para terminar):")
    placements: list[tuple[str, int, int]] = []
    while True:
        line = input("  > ").strip()
        if not line:
            break
        try:
            placements.append(parse_placement(line))
        except argparse.ArgumentTypeError as e:
            print(f"  {e}")

    if not placements:
        print("No se coloco ninguna criatura.")
        return

    try:
        ticks = int(input("\nTicks a ejecutar [50]: ").strip() or "50")
    except ValueError:
        ticks = 50
    try:
        delay = float(input("Delay entre ticks en segundos [0.3]: ").strip() or "0.3")
    except ValueError:
        delay = 0.3
    try:
        seed = int(input("Semilla [42]: ").strip() or "42")
    except ValueError:
        seed = 42

    try:
        world = runner.prepare(map_name, placements)
    except ValueError as e:
        print(f"Error: {e}")
        return
    runner.run(world, ticks, seed, delay, render=True)

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ejecuta una simulacion completa desde terminal."
    )
    parser.add_argument(
        "--data", type=Path,
        default=Path(__file__).resolve().parent / "data",
    )
    parser.add_argument("--map", type=str, default=None)
    parser.add_argument(
        "--creature", type=parse_placement, action="append", default=[],
        metavar="ESPECIE@X,Y",
    )
    parser.add_argument("--ticks", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--delay", type=float, default=0.0)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    runner = SimulationRunner(args.data)
    errors = runner.load_all()

    if errors:
        print(f"Errores de carga ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")
        print()

    if not runner.map_data:
        print("No hay mapas cargados; no se puede simular.")
        return
    if not runner.creatures:
        print("No hay criaturas cargadas; no se puede simular.")
        return

    if args.map is None:
        interactive_mode(runner)
    else:
        cli_mode(runner, args)


if __name__ == "__main__":
    main()
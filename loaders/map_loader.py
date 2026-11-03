from pathlib import Path
from core.world import Terrain, World, WorldObject
from .errors import LoadError


class MapData:
    """resultado de cargar un .map: nombre, filas de chars y origen."""

    def __init__(self, name: str, rows: list[str], path: Path, line_numbers) -> None:
        self.name = name
        self.rows = rows
        self.path = path
        self.line_numbers = line_numbers

    @property
    def width(self) -> int:
        return len(self.rows[0]) if self.rows else 0

    @property
    def height(self) -> int:
        return len(self.rows)


def parse_map_file(path: Path) -> MapData:
    """lee un .map y devuelve sus datos, o tira LoadError."""
    path = Path(path)

    lines: list[tuple[int, str]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_number, raw_line in enumerate(f, start=1):
            line = raw_line.rstrip("\n").rstrip("\r")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            lines.append((line_number, line))

    if not lines:
        raise LoadError(str(path), None, "el mapa está vacoo")

    name_line_number, name = lines[0]
    name = name.strip()
    if not name:
        raise LoadError(str(path), name_line_number, "el nombre del mapa no puede estar vacio")

    rows: list[str] = []
    for line_number, row in lines[1:]:
        rows.append((line_number, row))

    line_numbers = [ln for ln, _ in rows]
    rows = [row for _, row in rows]

    if not rows:
        raise LoadError(str(path), None, "el mapa no tiene filas")

    expected_width = len(rows[0])
    for idx, row in enumerate(rows):
        if len(row) != expected_width:
            # +1 porque lines[0] es el nombre
            original_line = lines[idx + 1][0]
            raise LoadError(
                str(path), original_line,
                f"la fila mide {len(row)}, se esperaba {expected_width}",
            )

    return MapData(name=name, rows=rows, path=path, line_numbers=line_numbers)

def build_world(
    map_data: MapData,
    terrains: dict[str, Terrain],
    objects: dict[str, WorldObject],
) -> World:
    """convierte MapData en un World usando los terrenos y objetos cargados."""
    if not terrains:
        raise LoadError(
            str(map_data.path), None,
            "no hay terrenos cargados; no se puede construir el mundo",
        )

    # el "primer terreno declarado" segun la especificacion.
    # usamos el orden de insercion del dict.
    default_terrain_template = next(iter(terrains.values()))

    # indices por char para busquedas
    terrain_by_char: dict[str, Terrain] = {t.char: t for t in terrains.values()}
    object_by_char: dict[str, WorldObject] = {o.char: o for o in objects.values()}

    height = map_data.height
    width = map_data.width

    # construimos la matriz de terrenos, y de paso objetos pendientes por casilla.
    terrain_grid: list[list[Terrain]] = []
    object_placements: list[tuple[int, int, WorldObject]] = []

    for y, row in enumerate(map_data.rows):
        terrain_row: list[Terrain] = []
        for x, char in enumerate(row):
            if char in object_by_char:
                # Objeto sobre el primer terreno declarado
                terrain_row.append(_clone_terrain(default_terrain_template))
                object_placements.append((x, y, _clone_object(object_by_char[char])))
            elif char in terrain_by_char:
                terrain_row.append(_clone_terrain(terrain_by_char[char]))
            else:
                # encontramos el char pero hay que saber su linea
                original_line = _line_for_row(map_data, y)
                raise LoadError(
                    str(map_data.path), original_line,
                    f"char desconocido {char!r} en la columna {x}",
                )
        terrain_grid.append(terrain_row)

    world = World(terrain_grid)

    for x, y, obj in object_placements:
        world.get_cell(x, y).occupant = obj

    return world

def _clone_terrain(t: Terrain) -> Terrain:
    """cada casilla debe tener su propio Terrain, no compartir referencia."""
    return Terrain(name=t.name, char=t.char, resource_max=t.resource_max, regen=t.regen)

def _clone_object(o: WorldObject) -> WorldObject:
    """cada objeto colocado en el mapa es una instancia independiente."""
    return WorldObject(name=o.name, char=o.char, resource_max=o.resource_max)

def _line_for_row(map_data: MapData, y: int) -> int:
    """linea original del archivo donde esta la fila y del mapa.
    Las filas empiezan en la línea 2 del archivo (la 1 es el nombre),
    pero puede haber lineas vacias o comentarios (se saltan).
    No guardo las lineas originales en MapData, asi que:
    la fila y esta en la linea y + 2 del archivo, asumiendo sin comentarios."""

    return y + 2

def load_map_from_file(
    path: Path,
    terrains: dict[str, Terrain],
    objects: dict[str, WorldObject],
) -> World:
    """carga un .map y devuelve un World listo para simular."""
    map_data = parse_map_file(path)
    return build_world(map_data, terrains, objects)

def load_maps_from_dir(
    directory: Path,
    terrains: dict[str, Terrain],
    objects: dict[str, WorldObject],
) -> tuple[dict[str, World], list[LoadError]]:
    """carga todos los .map de un directorio. Devuelve (mapas, errores).
    Las claves del dict son los nombres de los mapas."""
    
    directory = Path(directory)
    maps: dict[str, World] = {}
    errors: list[LoadError] = []

    if not directory.is_dir():
        errors.append(LoadError(str(directory), None, "el directorio de mapas no existe"))
        return maps, errors

    for path in sorted(directory.glob("*.map")):
        try:
            map_data = parse_map_file(path)
            world = build_world(map_data, terrains, objects)
        except LoadError as e:
            errors.append(e)
            continue

        if map_data.name in maps:
            errors.append(LoadError(
                str(path), None,
                f"ya existe un mapa con el nombre {map_data.name!r}",
            ))
            continue

        maps[map_data.name] = world

    return maps, errors
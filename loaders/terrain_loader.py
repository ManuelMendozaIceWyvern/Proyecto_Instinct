from pathlib import Path
from core.world import Terrain
from .errors import LoadError

REQUIRED_KEYS = {"terrain", "char", "resource_max", "regen"}
VALID_KEYS = REQUIRED_KEYS

def parse_terrain_file(path: Path) -> Terrain:
    """Lee un .te y devuelve un Terrain, o lanza LoadError."""
    path = Path(path)
    fields: dict[str, tuple[str, int]] = {}  # clave -> (valor, línea)

    with path.open("r", encoding="utf-8") as f:
        for line_number, raw_line in enumerate(f, start=1):
            line = raw_line.split("#", 1)[0].strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split()
            if len(parts) != 2:
                raise LoadError(
                    str(path), line_number,
                    f"linea invalida, se esperaba 'clave valor': {line!r}",
                )

            key, value = parts

            if key not in VALID_KEYS:
                raise LoadError(
                    str(path), line_number,
                    f"clave desconocida: {key!r}",
                )

            if key in fields:
                raise LoadError(
                    str(path), line_number,
                    f"clave duplicada: {key!r}",
                )

            fields[key] = (value, line_number)

    missing = REQUIRED_KEYS - fields.keys()
    if missing:
        raise LoadError(
            str(path), None,
            f"faltan claves obligatorias: {sorted(missing)}",
        )

    name, name_line = fields["terrain"]
    if not name:
        raise LoadError(str(path), name_line, "el nombre del terreno no puede estar vacio")

    char_value, char_line = fields["char"]
    if len(char_value) != 1:
        raise LoadError(
            str(path), char_line,
            f"'char' debe ser un unico caracter, se recibio {char_value!r}",
        )

    resource_max = _parse_int(path, fields["resource_max"], "resource_max", minimum=1)
    regen = _parse_int(path, fields["regen"], "regen", minimum=0)

    return Terrain(name=name, char=char_value, resource_max=resource_max, regen=regen)

def _parse_int(path: Path, field: tuple[str, int], key: str, minimum: int) -> int:
    raw, line_number = field
    try:
        value = int(raw)
    except ValueError:
        raise LoadError(
            str(path), line_number,
            f"'{key}' debe ser un entero, se recibio {raw!r}",
        )
    if value < minimum:
        raise LoadError(
            str(path), line_number,
            f"'{key}' debe ser mayor o igual que {minimum}, se recibio {value}",
        )
    return value

def load_terrains_from_dir(directory: Path) -> tuple[dict[str, Terrain], list[LoadError]]:
    """carga todos los .te de un directorio. Devuelve (terrenos, errores)."""
    directory = Path(directory)
    terrains: dict[str, Terrain] = {}
    errors: list[LoadError] = []

    if not directory.is_dir():
        errors.append(LoadError(str(directory), None, "el directorio de terrenos no existe"))
        return terrains, errors

    for path in sorted(directory.glob("*.te")):
        try:
            terrain = parse_terrain_file(path)
        except LoadError as e:
            errors.append(e)
            continue

        if terrain.name in terrains:
            errors.append(LoadError(
                str(path), None,
                f"ya existe un terreno con el nombre {terrain.name!r}",
            ))
            continue

        duplicate = next(
            (t for t in terrains.values() if t.char == terrain.char),
            None,
        )
        if duplicate is not None:
            errors.append(LoadError(
                str(path), None,
                f"el char {terrain.char!r} ya lo usa el terreno {duplicate.name!r}",
            ))
            continue

        terrains[terrain.name] = terrain

    return terrains, errors
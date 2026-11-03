from pathlib import Path
from core.world import Terrain, WorldObject
from .errors import LoadError

REQUIRED_KEYS = {"object", "char", "resource_max"}
VALID_KEYS = REQUIRED_KEYS

def parse_object_file(path: Path) -> WorldObject:
    """lee un .ob y devuelve un WorldObject, o tira LoadError."""
    path = Path(path)
    fields: dict[str, tuple[str, int]] = {}

    with path.open("r", encoding="utf-8") as f:
        for line_number, raw_line in enumerate(f, start=1):
            line = raw_line.split("#", 1)[0].strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split()
            if len(parts) != 2:
                raise LoadError(
                    str(path), line_number,
                    f"linea inválida, se esperaba 'clave valor': {line!r}",
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

    name, name_line = fields["object"]
    if not name:
        raise LoadError(str(path), name_line, "el nombre del objeto no puede estar vacio")

    char_value, char_line = fields["char"]
    if len(char_value) != 1:
        raise LoadError(
            str(path), char_line,
            f"'char' debe ser un unico caracter, se recibio {char_value!r}",
        )

    resource_max = _parse_int(path, fields["resource_max"], "resource_max", minimum=1)

    return WorldObject(name=name, char=char_value, resource_max=resource_max)

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

def load_objects_from_dir(
    directory: Path,
    terrains: dict[str, Terrain],
) -> tuple[dict[str, WorldObject], list[LoadError]]:
    """carga todos los .ob de un directorio.
    Comprueba que ningun char de objeto choque con otro objeto ni con un terreno.
    Devuelve (objetos, errores)."""
    
    directory = Path(directory)
    objects: dict[str, WorldObject] = {}
    errors: list[LoadError] = []

    if not directory.is_dir():
        errors.append(LoadError(str(directory), None, "el directorio de objetos no existe"))
        return objects, errors

    # Chars ya ocupados por terrenos
    used_chars: dict[str, str] = {t.char: t.name for t in terrains.values()}

    for path in sorted(directory.glob("*.ob")):
        try:
            obj = parse_object_file(path)
        except LoadError as e:
            errors.append(e)
            continue

        if obj.name in objects:
            errors.append(LoadError(
                str(path), None,
                f"ya existe un objeto con el nombre {obj.name!r}",
            ))
            continue

        if obj.char in used_chars:
            errors.append(LoadError(
                str(path), None,
                f"el char {obj.char!r} ya lo usa {used_chars[obj.char]!r}",
            ))
            continue

        objects[obj.name] = obj
        used_chars[obj.char] = obj.name

    return objects, errors
from pathlib import Path
from core.world import Creature
from lang.ast_nodes import Program
from lang.errors import CompileError
from lang.lexer import LexerError, tokenize
from lang.parser import parse_program
from .errors import LoadError


def parse_creature_file(path: Path) -> Program:
    """lee un .ins, lo tokeniza, lo parsea y devuelve un Program.
    Cualquier error de lexer o parser se convierte en LoadError con linea."""

    path = Path(path)
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as e:
        raise LoadError(str(path), None, f"no se pudo leer: {e}")

    try:
        tokens = tokenize(source, filename=str(path))
    except LexerError as e:
        raise LoadError(str(path), e.line, e.message)

    try:
        program = parse_program(tokens, filename=str(path))
    except CompileError as e:
        raise LoadError(str(path), e.line, e.message)

    return program

def load_creatures_from_dir(
    directory: Path,
) -> tuple[dict[str, Program], list[LoadError]]:
    """Carga todos los .ins de un directorio.
    Devuelve (programas indexados por especie, errores)."""

    directory = Path(directory)
    programs: dict[str, Program] = {}
    errors: list[LoadError] = []

    if not directory.is_dir():
        errors.append(LoadError(
            str(directory), None,
            "el directorio de criaturas no existe",
        ))
        return programs, errors

    for path in sorted(directory.glob("*.ins")):
        try:
            program = parse_creature_file(path)
        except LoadError as e:
            errors.append(e)
            continue

        species = program.header.species
        if species in programs:
            errors.append(LoadError(
                str(path), None,
                f"ya existe una criatura con la especie {species!r}",
            ))
            continue

        programs[species] = program

    return programs, errors


def creature_from_program(program: Program) -> Creature:
    """Crea una instancia nueva de Creature a partir de un Program.
    Cada criatura colocada en el mapa es una instancia distinta,
    pero todas comparten el mismo Program (que es inmutable)."""
    
    h = program.header
    creature = Creature(
        species=h.species,
        faction=h.faction,
        health=h.health,
        vision=h.vision,
        lifespan=h.lifespan,
    )
    creature.program = program
    creature.program_counter = program.labels["start"]
    return creature
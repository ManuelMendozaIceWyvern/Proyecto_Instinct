class InstinctError(Exception):
    def __init__(self, line: int | None, message: str) -> None:
        self.line = line
        self.message = message
        prefix = f"línea {line}: " if line is not None else ""
        super().__init__(f"{prefix}{message}")


class CompileError(InstinctError):
    """Error de compilación: parseo o validación semántica."""


class RuntimeFault(InstinctError):
    """Error en tiempo de ejecución: la criatura muere."""
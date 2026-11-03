class LoadError(Exception):
    """error al cargar un archivo de datos, con archivo y linea."""

    def __init__(self, file: str, line: int | None, message: str) -> None:
        self.file = file
        self.line = line
        self.message = message
        super().__init__(self._format())

    def _format(self) -> str:
        if self.line is None:
            return f"{self.file}: {self.message}"
        return f"{self.file}:{self.line}: {self.message}"

    def __repr__(self) -> str:
        return f"LoadError({self._format()!r})"
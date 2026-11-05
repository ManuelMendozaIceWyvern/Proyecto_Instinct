from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    # literales e identificadores
    INT = auto()
    STRING = auto()
    IDENT = auto()

    # las palabras reservadas
    IF = auto()
    GOTO = auto()
    AND = auto()
    OR = auto()
    NOT = auto()

    # operadores aritméticos
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    PERCENT = auto()

    # comparaciones
    LT = auto()
    LE = auto()
    GT = auto()
    GE = auto()
    EQ = auto()
    NE = auto()

    # asignacion y puntuacion
    ASSIGN = auto()
    LPAREN = auto()
    RPAREN = auto()
    COMMA = auto()
    COLON = auto()

    # estructura
    NEWLINE = auto()
    EOF = auto()

KEYWORDS = {
    "if": TokenType.IF,
    "goto": TokenType.GOTO,
    "and": TokenType.AND,
    "or": TokenType.OR,
    "not": TokenType.NOT,
}

SIMPLE_OPERATORS = {
    "+": TokenType.PLUS,
    "-": TokenType.MINUS,
    "*": TokenType.STAR,
    "/": TokenType.SLASH,
    "%": TokenType.PERCENT,
    "(": TokenType.LPAREN,
    ")": TokenType.RPAREN,
    ",": TokenType.COMMA,
    ":": TokenType.COLON,
}

@dataclass
class Token:
    type: TokenType
    value: str | int | None
    line: int
    column: int

    def __repr__(self) -> str:
        return f"Token({self.type.name}, {self.value!r}, {self.line}:{self.column})"

class LexerError(Exception):
    def __init__(self, filename: str, line: int, column: int, message: str) -> None:
        self.filename = filename
        self.line = line
        self.column = column
        self.message = message
        super().__init__(f"{filename}:{line}:{column}: {message}")

class Lexer:
    def __init__(self, source: str, filename: str = "<input>") -> None:
        self.source = source
        self.filename = filename
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens: list[Token] = []

    def tokenize(self) -> list[Token]:
        while not self._at_end():
            ch = self._peek()
            if ch in " \t\r":
                self._advance()
            elif ch == "\n":
                self._emit_newline()
            elif ch == "#":
                self._skip_comment()
            elif ch.isdigit():
                self._read_number()
            elif ch == '"':
                self._read_string()
            elif ch.isalpha() or ch == "_":
                self._read_identifier()
            else:
                self._read_operator()

        # garantizar que el ultimo statement tenga NEWLINE
        if self.tokens and self.tokens[-1].type != TokenType.NEWLINE:
            self._emit(TokenType.NEWLINE, None, self.line, self.column)

        self._emit(TokenType.EOF, None, self.line, self.column)
        return self.tokens

    # ---------- utilidades de posicion ------------------------------

    def _at_end(self) -> bool:
        return self.pos >= len(self.source)

    def _peek(self) -> str:
        return self.source[self.pos] if not self._at_end() else ""

    def _advance(self) -> str:
        ch = self.source[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return ch

    def _emit(self, type_: TokenType, value, line: int, column: int) -> None:
        self.tokens.append(Token(type_, value, line, column))

    # ---------- lectores especificos --------------------------------

    def _emit_newline(self) -> None:
        line, column = self.line, self.column
        while self._peek() == "\n":
            self._advance()
        if self.tokens and self.tokens[-1].type != TokenType.NEWLINE:
            self._emit(TokenType.NEWLINE, None, line, column)

    def _skip_comment(self) -> None:
        while not self._at_end() and self._peek() != "\n":
            self._advance()

    def _read_number(self) -> None:
        line, column = self.line, self.column
        start = self.pos
        while not self._at_end() and self._peek().isdigit():
            self._advance()
        if not self._at_end() and (self._peek().isalpha() or self._peek() == "_"):
            bad = self.source[start:self.pos + 1]
            raise LexerError(
                self.filename, line, column,
                f"número seguido de letras: {bad!r}",
            )
        self._emit(TokenType.INT, int(self.source[start:self.pos]), line, column)

    def _read_string(self) -> None:
        line, column = self.line, self.column
        self._advance()  # consume la comilla de apertura
        chars: list[str] = []
        while not self._at_end() and self._peek() != '"':
            if self._peek() == "\n":
                raise LexerError(
                    self.filename, line, column,
                    "texto sin cerrar (falta \")",
                )
            if self._peek() == "\\":
                self._advance()
                if self._at_end():
                    raise LexerError(
                        self.filename, line, column, "texto sin cerrar",
                    )
                esc = self._advance()
                mapping = {"n": "\n", "t": "\t", "\\": "\\", '"': '"'}
                if esc not in mapping:
                    raise LexerError(
                        self.filename, line, column,
                        f"escape desconocido: \\{esc}",
                    )
                chars.append(mapping[esc])
            else:
                chars.append(self._advance())
        if self._at_end():
            raise LexerError(
                self.filename, line, column, "texto sin cerrar",
            )
        self._advance()  # consume la comilla de cierre
        self._emit(TokenType.STRING, "".join(chars), line, column)

    def _read_identifier(self) -> None:
        line, column = self.line, self.column
        start = self.pos
        while not self._at_end() and (self._peek().isalnum() or self._peek() == "_"):
            self._advance()
        name = self.source[start:self.pos]
        self._emit(KEYWORDS.get(name, TokenType.IDENT), name, line, column)

    def _read_operator(self) -> None:
        line, column = self.line, self.column
        ch = self._advance()

        two_char = {
            ("=", "="): TokenType.EQ,
            ("!", "="): TokenType.NE,
            ("<", "="): TokenType.LE,
            (">", "="): TokenType.GE,
        }
        pair = (ch, self._peek())
        if pair in two_char:
            self._advance()
            self._emit(two_char[pair], None, line, column)
            return

        if ch == "=":
            self._emit(TokenType.ASSIGN, None, line, column)
            return
        if ch == "<":
            self._emit(TokenType.LT, None, line, column)
            return
        if ch == ">":
            self._emit(TokenType.GT, None, line, column)
            return
        if ch == "!":
            raise LexerError(
                self.filename, line, column,
                "'!' solo es valido como parte de '!='",
            )
        if ch in SIMPLE_OPERATORS:
            self._emit(SIMPLE_OPERATORS[ch], None, line, column)
            return

        raise LexerError(
            self.filename, line, column,
            f"carácter inesperado: {ch!r}",
        )

def tokenize(source: str, filename: str = "<input>") -> list[Token]:
    return Lexer(source, filename).tokenize()
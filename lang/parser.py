from __future__ import annotations
from .actions import ACTIONS, make_action
from .ast_nodes import (
    ActionStmt,
    AssignStmt,
    BinaryOp,
    CallExpr,
    Expression,
    GotoStmt,
    Header,
    IfGotoStmt,
    LabelStmt,
    Literal,
    Program,
    Statement,
    UnaryOp,
    Variable,
)
from .errors import CompileError
from .lexer import Token, TokenType

HEADER_KEYS = {"creature", "faction", "health", "vision", "lifespan"}


class Parser:
    def __init__(
        self,
        tokens: list[Token],
        filename: str = "<input>",
        known_functions: set[str] | None = None,
    ) -> None:
        self.tokens = tokens
        self.filename = filename
        self.pos = 0
        self.known_functions = known_functions or {"see", "name"}

    # ------------- utilidades de tokens -------------

    def _peek(self) -> Token:
        return self.tokens[self.pos]

    def _at(self, *types: TokenType) -> bool:
        return self._peek().type in types

    def _advance(self) -> Token:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def _expect(self, type_: TokenType, message: str) -> Token:
        if not self._at(type_):
            tok = self._peek()
            raise CompileError(
                tok.line,
                f"{message} (se encontro {tok.type.name} {tok.value!r})",
            )
        return self._advance()

    def _skip_newlines(self) -> None:
        while self._at(TokenType.NEWLINE):
            self._advance()

    # ------------- programa: cabecera + cuerpo -------------

    def parse(self) -> Program:
        self._skip_newlines()
        header = self._parse_header()
        self._skip_newlines()

        statements: list[Statement] = []
        while not self._at(TokenType.EOF):
            stmt = self._parse_statement()
            statements.append(stmt)
            self._skip_newlines()

        return Program(header=header, statements=statements)

    # ------------- cabecera -------------

    def _parse_header(self) -> Header:
        fields: dict[str, tuple[object, int]] = {}
        first_key: str | None = None
        first_line = self._peek().line

        while not self._at(TokenType.EOF):
            if not self._at(TokenType.IDENT):
                break
            key_tok = self._peek()
            if key_tok.value not in HEADER_KEYS:
                break

            self._advance()
            key = key_tok.value
            line = key_tok.line

            if first_key is None:
                first_key = key

            if key in fields:
                raise CompileError(line, f"clave de cabecera duplicada: {key!r}")

            value = self._parse_header_value(key)
            fields[key] = (value, line)

            if not self._at(TokenType.NEWLINE, TokenType.EOF):
                tok = self._peek()
                raise CompileError(
                    tok.line,
                    f"se esperaba fin de linea tras el valor de {key!r}",
                )
            self._skip_newlines()

        missing = HEADER_KEYS - fields.keys()
        if missing:
            raise CompileError(
                first_line,
                f"faltan claves obligatorias de cabecera: {sorted(missing)}",
            )

        if first_key != "creature":
            raise CompileError(
                first_line,
                "la primera linea de la cabecera debe ser 'creature Name'",
            )

        species = fields["creature"][0]
        faction = fields["faction"][0]
        if not isinstance(species, str) or not species:
            raise CompileError(first_line, "el nombre de la criatura no puede estar vacio")
        if not isinstance(faction, str) or not faction:
            raise CompileError(first_line, "la faccion no puede estar vacia")

        health = self._require_positive_int(fields["health"], "health")
        vision = self._require_positive_int(fields["vision"], "vision")
        lifespan = self._require_positive_int(fields["lifespan"], "lifespan")

        return Header(
            species=species,
            faction=faction,
            health=health,
            vision=vision,
            lifespan=lifespan,
        )

    def _parse_header_value(self, key: str) -> object:
        if key in ("creature", "faction"):
            tok = self._expect(TokenType.IDENT, f"se esperaba un nombre para {key!r}")
            return tok.value
        tok = self._expect(TokenType.INT, f"se esperaba un entero para {key!r}")
        return tok.value

    @staticmethod
    def _require_positive_int(field: tuple[object, int], name: str) -> int:
        value, line = field
        if not isinstance(value, int):
            raise CompileError(line, f"{name!r} debe ser un entero")
        if value <= 0:
            raise CompileError(line, f"{name!r} debe ser mayor que 0")
        return value

    # ------------- instrucciones -------------

    def _parse_statement(self) -> Statement:
        if self._at(TokenType.GOTO):
            return self._parse_goto()
        if self._at(TokenType.IF):
            return self._parse_if_goto()
        if self._at(TokenType.IDENT):
            next_tok = self.tokens[self.pos + 1]
            if next_tok.type == TokenType.COLON:
                return self._parse_label()
            if next_tok.type == TokenType.ASSIGN:
                return self._parse_assign()
            if next_tok.type == TokenType.LPAREN:
                return self._parse_action_stmt()
            raise CompileError(
                self._peek().line,
                f"se esperaba ':', '=' o '(' después de {self._peek().value!r}",
            )
        raise CompileError(
            self._peek().line,
            f"instrucción invalida, comienza con {self._peek().type.name}",
        )

    def _parse_label(self) -> LabelStmt:
        name_tok = self._expect(TokenType.IDENT, "se esperaba nombre de etiqueta")
        self._expect(TokenType.COLON, "se esperaba ':' tras la etiqueta")
        self._expect_statement_end()
        return LabelStmt(name=name_tok.value, line=name_tok.line)

    def _parse_goto(self) -> GotoStmt:
        kw = self._expect(TokenType.GOTO, "se esperaba 'goto'")
        target = self._expect(TokenType.IDENT, "se esperaba nombre de etiqueta tras 'goto'")
        self._expect_statement_end()
        return GotoStmt(target=target.value, line=kw.line)

    def _parse_if_goto(self) -> IfGotoStmt:
        kw = self._expect(TokenType.IF, "se esperaba 'if'")
        condition = self._parse_expression()
        self._expect(TokenType.GOTO, "se esperaba 'goto' tras la condición del 'if'")
        target = self._expect(TokenType.IDENT, "se esperaba nombre de etiqueta tras 'goto'")
        self._expect_statement_end()
        return IfGotoStmt(condition=condition, target=target.value, line=kw.line)

    def _parse_assign(self) -> AssignStmt:
        name_tok = self._expect(TokenType.IDENT, "se esperaba nombre de variable")
        self._expect(TokenType.ASSIGN, "se esperaba '=' en la asignación")
        value = self._parse_expression()
        self._expect_statement_end()
        return AssignStmt(name=name_tok.value, value=value, line=name_tok.line)

    def _parse_action_stmt(self) -> ActionStmt:
        name_tok = self._expect(TokenType.IDENT, "se esperaba nombre de acción")
        args = self._parse_argument_list()
        self._expect_statement_end()
        action = make_action(name_tok.value, args, name_tok.line)
        return ActionStmt(action=action, line=name_tok.line)

    def _parse_argument_list(self) -> list[Expression]:
        self._expect(TokenType.LPAREN, "se esperaba '('")
        args: list[Expression] = []
        if not self._at(TokenType.RPAREN):
            args.append(self._parse_expression())
            while self._at(TokenType.COMMA):
                self._advance()
                args.append(self._parse_expression())
        self._expect(TokenType.RPAREN, "se esperaba ')' al final de los argumentos")
        return args

    def _expect_statement_end(self) -> None:
        if not self._at(TokenType.NEWLINE, TokenType.EOF):
            tok = self._peek()
            raise CompileError(
                tok.line,
                f"se esperaba fin de línea, se encontro {tok.type.name} {tok.value!r}",
            )

    # ------------------- expresiones  -------------------------

    def _parse_expression(self) -> Expression:
        return self._parse_or()

    def _parse_or(self) -> Expression:
        expr = self._parse_and()
        while self._at(TokenType.OR):
            tok = self._advance()
            right = self._parse_and()
            expr = BinaryOp(op="or", left=expr, right=right, line=tok.line)
        return expr

    def _parse_and(self) -> Expression:
        expr = self._parse_comparison()
        while self._at(TokenType.AND):
            tok = self._advance()
            right = self._parse_comparison()
            expr = BinaryOp(op="and", left=expr, right=right, line=tok.line)
        return expr

    def _parse_unary(self) -> Expression:
            if self._at(TokenType.MINUS):
                tok = self._advance()
                return UnaryOp(op="neg", operand=self._parse_unary(), line=tok.line)
            if self._at(TokenType.NOT):
                tok = self._advance()
                return UnaryOp(op="not", operand=self._parse_unary(), line=tok.line)
            return self._parse_atom()

    def _parse_multiplicative(self) -> Expression:
            expr = self._parse_unary()
            while self._at(TokenType.STAR, TokenType.SLASH, TokenType.PERCENT):
                tok = self._advance()
                right = self._parse_unary()
                op = {
                    TokenType.STAR: "*",
                    TokenType.SLASH: "/",
                    TokenType.PERCENT: "%",
                }[tok.type]
                expr = BinaryOp(op=op, left=expr, right=right, line=tok.line)
            return expr

    def _parse_additive(self) -> Expression:
            expr = self._parse_multiplicative()
            while self._at(TokenType.PLUS, TokenType.MINUS):
                tok = self._advance()
                right = self._parse_multiplicative()
                op = "+" if tok.type == TokenType.PLUS else "-"
                expr = BinaryOp(op=op, left=expr, right=right, line=tok.line)
            return expr

    def _parse_comparison(self) -> Expression:
        expr = self._parse_additive()
        while self._at(
            TokenType.LT, TokenType.LE, TokenType.GT,
            TokenType.GE, TokenType.EQ, TokenType.NE,
        ):
            tok = self._advance()
            right = self._parse_additive()
            op = {
                TokenType.LT: "<",
                TokenType.LE: "<=",
                TokenType.GT: ">",
                TokenType.GE: ">=",
                TokenType.EQ: "==",
                TokenType.NE: "!=",
            }[tok.type]
            expr = BinaryOp(op=op, left=expr, right=right, line=tok.line)
        return expr

    def _parse_atom(self) -> Expression:
        if self._at(TokenType.INT):
            tok = self._advance()
            return Literal(value=tok.value, line=tok.line)
        if self._at(TokenType.STRING):
            tok = self._advance()
            return Literal(value=tok.value, line=tok.line)
        if self._at(TokenType.LPAREN):
            self._advance()
            expr = self._parse_expression()
            self._expect(TokenType.RPAREN, "se esperaba ')'")
            return expr
        if self._at(TokenType.IDENT):
            tok = self._advance()
            if self._at(TokenType.LPAREN):
                if tok.value in ACTIONS:
                    raise CompileError(
                        tok.line,
                        f"{tok.value!r} es una accion; las acciones van solas en su linea",
                    )
                if tok.value not in self.known_functions:
                    raise CompileError(tok.line, f"funcion desconocida: {tok.value!r}")
                args = self._parse_argument_list()
                return CallExpr(name=tok.value, args=args, line=tok.line)
            return Variable(name=tok.value, line=tok.line)

        tok = self._peek()
        raise CompileError(
            tok.line,
            f"se esperaba una expresion, se encontro {tok.type.name} {tok.value!r}",
        )

def parse_program(
    tokens: list[Token],
    filename: str = "<input>",
    known_functions: set[str] | None = None,
) -> Program:
    return Parser(tokens, filename, known_functions).parse()
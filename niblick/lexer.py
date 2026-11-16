"""Small lexer for Niblick."""

from __future__ import annotations

from dataclasses import dataclass

from .errors import NiblickSyntaxError, location


KEYWORDS = {
    "fn",
    "u4",
    "i4",
    "nibble",
    "u8",
    "i8",
    "char",
    "byte",
    "uint8_t",
    "int8_t",
    "int_least8_t",
    "int_fast8_t",
    "uint_least8_t",
    "uint_fast8_t",
    "u16",
    "i16",
    "uint16_t",
    "int16_t",
    "int_least16_t",
    "int_fast16_t",
    "uint_least16_t",
    "uint_fast16_t",
    "short",
    "int",
    "u32",
    "i32",
    "uint32_t",
    "int32_t",
    "u64",
    "i64",
    "uint64_t",
    "int64_t",
    "uint_least64_t",
    "uint_fast64_t",
    "int_least64_t",
    "int_fast64_t",
    "int_least32_t",
    "int_fast32_t",
    "uint_least32_t",
    "uint_fast32_t",
    "intmax_t",
    "uintmax_t",
    "long",
    "bool",
    "half",
    "f16",
    "_Float16",
    "float",
    "f32",
    "_Float32",
    "_Float64",
    "flashptr",
    "void",
    "const",
    "if",
    "else",
    "while",
    "for",
    "return",
    "break",
    "continue",
    "true",
    "false",
    "import",
    "extern",
    "asm",
    "struct",
}

# Longest operators first.
OPERATORS = [
    "<<=",
    ">>=",
    "+=",
    "-=",
    "*=",
    "/=",
    "%=",
    "&=",
    "|=",
    "^=",
    "++",
    "--",
    "<<",
    ">>",
    "<=",
    ">=",
    "==",
    "!=",
    "&&",
    "||",
    "+",
    "-",
    "*",
    "/",
    "%",
    "&",
    "|",
    "^",
    "~",
    "!",
    "=",
    "<",
    ">",
]

PUNCTUATION = set("(){}[],;.?:")


def _is_identifier_start(ch: str) -> bool:
    return bool(ch) and ch.isascii() and (ch.isalpha() or ch == "_")


def _is_identifier_part(ch: str) -> bool:
    return bool(ch) and ch.isascii() and (ch.isalnum() or ch == "_")


@dataclass
class Token:
    kind: str
    value: object
    line: int
    column: int

    def __str__(self) -> str:
        return f"{self.kind}({self.value!r}) at {self.line}:{self.column}"


class Lexer:
    def __init__(self, source: str, filename: str = "<input>") -> None:
        self.source = source
        self.filename = filename
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens: list[Token] = []

    def error(self, message: str) -> NiblickSyntaxError:
        return NiblickSyntaxError(f"{location(self.filename, self.line, self.column)}: {message}")

    def peek(self, offset: int = 0) -> str:
        index = self.pos + offset
        return self.source[index] if index < len(self.source) else ""

    def advance(self) -> str:
        ch = self.source[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return ch

    def add(self, kind: str, value: object, line: int, column: int) -> None:
        self.tokens.append(Token(kind, value, line, column))

    def tokenize(self) -> list[Token]:
        while self.pos < len(self.source):
            ch = self.peek()

            if ch in " \t\r\n":
                self.advance()
                continue

            if ch == "/" and self.peek(1) == "/":
                while self.peek() and self.peek() != "\n":
                    self.advance()
                continue

            if ch == "/" and self.peek(1) == "*":
                self.advance()
                self.advance()
                while self.peek():
                    if self.peek() == "*" and self.peek(1) == "/":
                        self.advance()
                        self.advance()
                        break
                    self.advance()
                else:
                    raise self.error("unterminated block comment")
                continue

            line, column = self.line, self.column

            if _is_identifier_start(ch):
                start_line, start_column = self.line, self.column
                ident = self.read_identifier()
                if ident == "asm":
                    lookahead = self.pos
                    while (
                        lookahead < len(self.source)
                        and self.source[lookahead] in " \t\r\n"
                    ):
                        lookahead += 1
                    if (
                        lookahead < len(self.source)
                        and self.source[lookahead] == "{"
                    ):
                        while self.pos <= lookahead:
                            self.advance()
                        text: list[str] = []
                        while self.pos < len(self.source):
                            if self.peek() == ";":
                                while (
                                    self.pos < len(self.source)
                                    and self.peek() != "\n"
                                ):
                                    text.append(self.advance())
                                continue
                            if self.peek() == "$" and self.peek(1) == "{":
                                text.append(self.advance())
                                text.append(self.advance())
                                while self.pos < len(self.source):
                                    char = self.advance()
                                    text.append(char)
                                    if char == "}":
                                        break
                                continue
                            if self.peek() == "}":
                                self.advance()
                                break
                            text.append(self.advance())
                        else:
                            raise self.error("unterminated asm block")
                        self.add(
                            "asm_block",
                            "".join(text),
                            start_line,
                            start_column,
                        )
                        continue
                kind = "keyword" if ident in KEYWORDS else "ident"
                self.add(kind, ident, start_line, start_column)
                continue

            if ch.isdigit() or (ch == "." and self.peek(1).isdigit()):
                value = self.read_number()
                kind = "float" if isinstance(value, float) else "number"
                self.add(kind, value, line, column)
                continue

            if ch == "'":
                self.add("number", self.read_char_literal(), line, column)
                continue

            if ch == '"':
                self.add("string", self.read_string(), line, column)
                continue

            matched = False
            for op in OPERATORS:
                if self.source.startswith(op, self.pos):
                    for _ in op:
                        self.advance()
                    self.add("op", op, line, column)
                    matched = True
                    break
            if matched:
                continue

            if ch in PUNCTUATION:
                self.advance()
                self.add("punct", ch, line, column)
                continue

            raise self.error(f"unexpected character {ch!r}")

        self.add("eof", "", self.line, self.column)
        return self.tokens

    def read_identifier(self) -> str:
        start = self.pos
        while self.peek() and _is_identifier_part(self.peek()):
            self.advance()
        return self.source[start:self.pos]

    def read_digits(self, valid) -> str:
        digits: list[str] = []
        last_separator = False
        while True:
            ch = self.peek()
            if ch and valid(ch):
                digits.append(self.advance())
                last_separator = False
            elif ch == "_":
                if not digits or last_separator:
                    raise self.error("misplaced digit separator")
                self.advance()
                last_separator = True
            else:
                break
        if last_separator:
            raise self.error("misplaced digit separator")
        return "".join(digits)

    def read_number(self) -> int | float:
        start = self.pos

        if self.peek() == "0" and self.peek(1) and self.peek(1) in "xX":
            self.advance()
            self.advance()
            digits = self.read_digits(
                lambda ch: ch.isascii() and (ch.isdigit() or ch.lower() in "abcdef")
            )
            if not digits:
                raise self.error("expected hexadecimal digits")
            if self.peek() and self.peek().isalnum():
                raise self.error(f"invalid hexadecimal digit {self.peek()!r}")
            return int(digits, 16)

        if self.peek() == "0" and self.peek(1) and self.peek(1) in "bB":
            self.advance()
            self.advance()
            digits = self.read_digits(lambda ch: ch in "01")
            if not digits:
                raise self.error("expected binary digits")
            if self.peek() and self.peek().isdigit():
                raise self.error(f"invalid binary digit {self.peek()!r}")
            return int(digits, 2)

        if self.peek() == "0" and self.peek(1) and self.peek(1) in "oO":
            self.advance()
            self.advance()
            digits = self.read_digits(lambda ch: ch in "01234567")
            if not digits:
                raise self.error("expected octal digits")
            if self.peek() and self.peek().isdigit():
                raise self.error(f"invalid octal digit {self.peek()!r}")
            return int(digits, 8)

        if (
            self.peek() == "0"
            and self.peek(1)
            and (self.peek(1).isdigit() or self.peek(1) == "_")
        ):
            raise self.error(
                "leading-zero decimal literals are not supported; use 0o for octal"
            )

        is_float = False
        if self.peek() == ".":
            is_float = True
            self.advance()
            digits = self.read_digits(lambda ch: ch.isdigit())
            if not digits:
                raise self.error("expected fractional digits")
        else:
            whole = self.read_digits(lambda ch: ch.isdigit())
            if not whole:
                raise self.error("expected digits")
            if self.peek() == "." and self.peek(1) != ".":
                is_float = True
                after = self.peek(1)
                self.advance()
                if after == "_":
                    raise self.error("misplaced digit separator")
                if after.isdigit():
                    self.read_digits(lambda ch: ch.isdigit())

        if self.peek() and self.peek() in "eE":
            is_float = True
            self.advance()
            if self.peek() and self.peek() in "+-":
                self.advance()
            exponent = self.read_digits(lambda ch: ch.isdigit())
            if not exponent:
                raise self.error("expected exponent digits")

        text = self.source[start:self.pos].replace("_", "")
        if is_float:
            return float(text)
        return int(text, 10)

    def read_char_literal(self) -> int:
        self.advance()  # opening quote
        if not self.peek():
            raise self.error("unterminated character literal")
        ch = self.advance()
        if ch == "\\":
            ch = self.read_escape()
        if ord(ch) > 0xFF:
            raise self.error("character literal is not a byte")
        if self.peek() != "'":
            raise self.error("character literal must contain exactly one character")
        self.advance()
        return ord(ch)

    def read_string(self) -> str:
        self.advance()  # opening quote
        chars: list[str] = []
        while True:
            if not self.peek():
                raise self.error("unterminated string literal")
            if self.peek() == '"':
                self.advance()
                break
            if self.peek() in "\r\n":
                raise self.error("newline in string literal")
            ch = self.advance()
            if ch == "\\":
                ch = self.read_escape()
            if ord(ch) > 0xFF:
                raise self.error("string literal contains a non-byte character")
            if ch == "\0":
                raise self.error("NUL is not allowed in a string literal")
            chars.append(ch)
        return "".join(chars)

    def read_escape(self) -> str:
        if not self.peek():
            raise self.error("unterminated escape sequence")
        ch = self.advance()
        escapes = {
            "a": "\a",
            "b": "\b",
            "f": "\f",
            "n": "\n",
            "r": "\r",
            "t": "\t",
            "v": "\v",
            "\\": "\\",
            '"': '"',
            "'": "'",
            "?": "?",
        }
        if ch in escapes:
            return escapes[ch]
        if ch == "x":
            digits = ""
            for _ in range(2):
                if self.peek() and self.peek().isascii() and (
                    self.peek().isdigit() or self.peek().lower() in "abcdef"
                ):
                    digits += self.advance()
                else:
                    break
            if not digits:
                raise self.error("expected hex digits after \\x")
            return chr(int(digits, 16))
        if ch in "01234567":
            digits = ch
            for _ in range(2):
                if self.peek() and self.peek() in "01234567":
                    digits += self.advance()
                else:
                    break
            value = int(digits, 8)
            if value > 0xFF:
                raise self.error("octal escape does not fit in a byte")
            return chr(value)
        raise self.error(f"unknown escape sequence \\{ch}")


def tokenize(source: str, filename: str = "<input>") -> list[Token]:
    return Lexer(source, filename).tokenize()

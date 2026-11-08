"""Small lexer for BadgeC."""

from __future__ import annotations

from dataclasses import dataclass

from .errors import BadgeSyntaxError, location


KEYWORDS = {
    "fn",
    "nibble",
    "char",
    "word",
    "dword",
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
}

# Longest operators first.
OPERATORS = [
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

PUNCTUATION = set("(){}[],;")


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

    def error(self, message: str) -> BadgeSyntaxError:
        return BadgeSyntaxError(f"{location(self.filename, self.line, self.column)}: {message}")

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

            if ch.isalpha() or ch == "_":
                ident = self.read_identifier()
                kind = "keyword" if ident in KEYWORDS else "ident"
                self.add(kind, ident, line, column)
                continue

            if ch.isdigit():
                self.add("number", self.read_number(), line, column)
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
        while self.peek() and (self.peek().isalnum() or self.peek() == "_"):
            self.advance()
        return self.source[start:self.pos]

    def read_number(self) -> int:
        start = self.pos
        if self.peek() == "0" and self.peek(1) and self.peek(1) in "xX":
            self.advance()
            self.advance()
            digits = self.pos
            while self.peek() and (self.peek().isdigit() or self.peek().lower() in "abcdef"):
                self.advance()
            if self.pos == digits:
                raise self.error("expected hexadecimal digits")
            return int(self.source[digits:self.pos], 16)

        if self.peek() == "0" and self.peek(1) and self.peek(1) in "bB":
            self.advance()
            self.advance()
            digits = self.pos
            while self.peek() and self.peek() in "01":
                self.advance()
            if self.pos == digits:
                raise self.error("expected binary digits")
            return int(self.source[digits:self.pos], 2)

        # Allow 0x/0b style only; ordinary decimal otherwise.
        while self.peek().isdigit():
            self.advance()
        return int(self.source[start:self.pos], 10)

    def read_char_literal(self) -> int:
        self.advance()  # opening quote
        if not self.peek():
            raise self.error("unterminated character literal")
        ch = self.advance()
        if ch == "\\":
            ch = self.read_escape()
        if self.peek() != "'":
            raise self.error("character literal must contain exactly one character")
        self.advance()
        return ord(ch)

    def read_string(self) -> str:
        self.advance()  # opening quote
        chars: list[str] = []
        while self.peek() and self.peek() != '"':
            ch = self.advance()
            if ch == "\\":
                chars.append(self.read_escape())
            else:
                chars.append(ch)
        if self.peek() != '"':
            raise self.error("unterminated string literal")
        self.advance()
        return "".join(chars)

    def read_escape(self) -> str:
        if not self.peek():
            raise self.error("unterminated escape sequence")
        ch = self.advance()
        escapes = {
            "n": "\n",
            "r": "\r",
            "t": "\t",
            "0": "\0",
            "\\": "\\",
            '"': '"',
            "'": "'",
        }
        if ch in escapes:
            return escapes[ch]
        if ch == "x":
            digits = ""
            for _ in range(2):
                if self.peek() and (self.peek().isdigit() or self.peek().lower() in "abcdef"):
                    digits += self.advance()
                else:
                    break
            if not digits:
                raise self.error("expected hex digits after \\x")
            return chr(int(digits, 16))
        raise self.error(f"unknown escape sequence \\{ch}")


def tokenize(source: str, filename: str = "<input>") -> list[Token]:
    return Lexer(source, filename).tokenize()

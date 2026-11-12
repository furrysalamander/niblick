"""Symbol index for editor navigation and hover.

This is intentionally a lightweight semantic pass over the merged AST.  It
does not allocate RAM or generate code; it records declarations, references,
lexical scopes, and the correspondence between ``extern fn`` declarations and
their ``fn_*`` assembly entry points.
"""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import ast_nodes as ast
from .asm_link import scan_asm
from .asm_text import ASM_CALL_RE, Placeholder, code_part, iter_placeholders
from .compiler import BUILTINS
from .runtime_linker import ROUTINE_LABELS

_QUALIFIED_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)$")


def _normalise(path: str | Path) -> str:
    return str(Path(path).expanduser().resolve())


@dataclass
class Definition:
    name: str
    kind: str
    file: str
    line: int
    column: int
    detail: str
    type: str = ""
    is_extern: bool = False
    const_value: Optional[int] = None
    array_len: Optional[int] = None
    asm_file: Optional[str] = None
    asm_line: Optional[int] = None
    asm_column: Optional[int] = None
    params: list["Definition"] = field(default_factory=list)

    def hover_text(self) -> str:
        text = self.detail
        if self.is_extern and self.asm_file:
            text += (
                f"\n\nImplemented in `{self.asm_file}`"
                f":{self.asm_line or 1}"
            )
        return text

    def asm_location(self) -> Optional["Definition"]:
        if self.asm_file is None:
            return None
        return Definition(
            name=self.name,
            kind="asm_function",
            file=self.asm_file,
            line=self.asm_line or 1,
            column=self.asm_column or 1,
            detail=f"{self.detail} (assembly entry point)",
        )


@dataclass
class Occurrence:
    name: str
    file: str
    line: int
    column: int
    length: int
    kind: str
    definition: Optional[Definition] = None
    detail: str = ""


@dataclass
class RenameEdit:
    file: str
    line: int
    column: int
    length: int
    new_text: str


@dataclass
class InlineAsmContext:
    file: str
    start_line: int
    end_line: int
    text: str
    visible: list[Definition]


def _rename_placeholder(
    text: str,
    target_kind: str,
    old_name: str,
    new_name: str,
) -> str:
    match = re.match(
        r"^(&\s*)?([A-Za-z_][A-Za-z0-9_]*)"
        r"(?:\.([A-Za-z_][A-Za-z0-9_]*))?(.*)$",
        text,
    )
    if match is None:
        return text
    amp, first, second, rest = match.groups()
    if target_kind in ("function", "asm_function"):
        if first == old_name:
            first = new_name
        elif second == old_name:
            second = new_name
    elif target_kind == "param":
        if second == old_name:
            second = new_name
        elif first == old_name:
            first = new_name
    elif first == old_name:
        first = new_name
    qualified = f".{second}" if second else ""
    return f"${{{amp or ''}{first}{qualified}{rest}}}"


def _max_line(node) -> int:
    if isinstance(node, ast.InlineAsm):
        return node.line + max(0, len(node.text.splitlines()) - 1)
    best = getattr(node, "line", 0) or 0
    for data_field in dataclasses.fields(node):
        value = getattr(node, data_field.name)
        if isinstance(value, (ast.Expr, ast.Stmt)):
            best = max(best, _max_line(value))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, (ast.Expr, ast.Stmt)):
                    best = max(best, _max_line(item))
    return best


def _type_detail(
    typ: str, name: str, array_len: Optional[int] = None
) -> str:
    suffix = f"[{array_len}]" if array_len is not None else ""
    return f"{typ} {name}{suffix}"


def _function_detail(fn: ast.FunctionDecl) -> str:
    params = ", ".join(f"{param.type} {param.name}" for param in fn.params)
    prefix = "extern " if fn.is_extern else ""
    return f"{prefix}{fn.return_type} {fn.name}({params})"


class ProgramIndex:
    """Declarations, references and lexical scopes for one project."""

    def __init__(
        self,
        program: Optional[ast.Program],
        entry: str | Path,
        overrides: Optional[dict[str, str]] = None,
        extra_asm: Optional[dict[str, str]] = None,
    ) -> None:
        self.program = program
        self.entry = _normalise(entry)
        self.overrides = overrides or {}
        self.extra_asm = {_normalise(key): value for key, value in (extra_asm or {}).items()}
        self.functions: dict[str, Definition] = {}
        self.globals: dict[str, Definition] = {}
        self.builtins: dict[str, Definition] = {}
        self.runtime: dict[str, Definition] = {}
        self.asm_labels: dict[tuple[str, str], Definition] = {}
        self.params: dict[str, dict[str, Definition]] = {}
        self.locals: dict[str, list[Definition]] = {}
        self.occurrences: list[Occurrence] = []
        self.function_ranges: list[tuple[str, int, int, Definition]] = []
        self.inline_asm_contexts: list[InlineAsmContext] = []
        self._build()

    # ------------------------------------------------------------------
    # Public queries
    # ------------------------------------------------------------------

    def occurrence_at(
        self, file: str | Path, line: int, column: int
    ) -> Optional[Occurrence]:
        target = _normalise(file)
        candidates = []
        for occurrence in self.occurrences:
            if occurrence.file != target or occurrence.line != line:
                continue
            end = occurrence.column + max(1, occurrence.length)
            if occurrence.column <= column < end:
                candidates.append(occurrence)
        if not candidates:
            return None
        return min(candidates, key=lambda item: item.length)

    def definition_at(
        self, file: str | Path, line: int, column: int
    ) -> Optional[Definition]:
        occurrence = self.occurrence_at(file, line, column)
        if occurrence is None or occurrence.definition is None:
            return None
        definition = occurrence.definition
        if occurrence.kind in ("call", "asm_call") and definition.is_extern:
            return definition.asm_location() or definition
        if definition.kind in ("builtin", "runtime"):
            return None
        return definition

    def hover_at(self, file: str | Path, line: int, column: int) -> Optional[str]:
        occurrence = self.occurrence_at(file, line, column)
        if occurrence is None:
            return None
        if occurrence.definition is not None:
            return occurrence.definition.hover_text()
        return occurrence.detail or None

    def _reference_key(self, definition: Definition) -> tuple:
        if definition.kind == "function":
            return ("function", definition.name)
        if definition.kind == "asm_function":
            if definition.name.startswith("fn_"):
                return ("function", definition.name[3:])
            return ("asm_label", definition.file, definition.name)
        if definition.kind == "asm_label":
            return ("asm_label", definition.file, definition.name)
        if definition.kind in ("global", "constant"):
            return ("global", definition.name)
        return ("local", id(definition))

    def references_at(
        self, file: str | Path, line: int, column: int
    ) -> list[Occurrence]:
        occurrence = self.occurrence_at(file, line, column)
        if occurrence is None or occurrence.definition is None:
            return []
        if occurrence.definition.kind in ("builtin", "runtime"):
            return []
        key = self._reference_key(occurrence.definition)
        return [
            other
            for other in self.occurrences
            if other.definition is not None
            and self._reference_key(other.definition) == key
        ]

    def rename_at(
        self,
        file: str | Path,
        line: int,
        column: int,
        new_name: str,
    ) -> list[RenameEdit]:
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", new_name) is None:
            return []
        occurrence = self.occurrence_at(file, line, column)
        if occurrence is None or occurrence.definition is None:
            return []
        definition = occurrence.definition
        if definition.kind in ("builtin", "runtime"):
            return []

        key = self._reference_key(definition)
        occurrences = [
            other
            for other in self.occurrences
            if other.definition is not None
            and self._reference_key(other.definition) == key
        ]

        if definition.kind in ("function", "asm_function"):
            target_kind = definition.kind
            old_name = (
                definition.name[3:]
                if definition.kind == "asm_function"
                and definition.name.startswith("fn_")
                else definition.name
            )
            asm_name = f"fn_{new_name}"
        elif definition.kind == "asm_label":
            target_kind = "asm_label"
            old_name = definition.name
            asm_name = new_name
        else:
            target_kind = definition.kind
            old_name = definition.name
            asm_name = new_name

        edits: list[RenameEdit] = []
        seen: set[tuple[str, int, int]] = set()

        def add_edit(item: Occurrence, text: str) -> None:
            identity = (item.file, item.line, item.column)
            if identity in seen:
                return
            if item.kind == "asm_placeholder":
                if text == f"${{{item.name}}}":
                    return
            elif text == item.name:
                return
            seen.add(identity)
            edits.append(
                RenameEdit(
                    file=item.file,
                    line=item.line,
                    column=item.column,
                    length=item.length,
                    new_text=text,
                )
            )

        for item in occurrences:
            if item.kind == "asm_placeholder":
                add_edit(
                    item,
                    _rename_placeholder(
                        item.name, target_kind, old_name, new_name
                    ),
                )
            elif target_kind in ("function", "asm_function") and item.name.startswith("fn_"):
                add_edit(item, asm_name)
            else:
                add_edit(item, new_name)

        # `${function.param}` placeholders resolve to the parameter, not the
        # function, so rename the function prefix separately.
        if target_kind in ("function", "asm_function"):
            for item in self.occurrences:
                if item.kind != "asm_placeholder":
                    continue
                replacement = _rename_placeholder(
                    item.name, target_kind, old_name, new_name
                )
                add_edit(item, replacement)

        return edits

    def completions_at(
        self, file: str | Path, line: int, column: int
    ) -> list[Definition]:
        target = _normalise(file)
        items: dict[tuple[str, str], Definition] = {}
        for definition in self.globals.values():
            items[(definition.name, definition.kind)] = definition
        for definition in self.functions.values():
            items[(definition.name, definition.kind)] = definition
        for definition in self.builtins.values():
            items[(definition.name, definition.kind)] = definition
        for definition in self.runtime.values():
            items[(definition.name, definition.kind)] = definition

        function = self.function_at(target, line)
        if function is not None:
            for definition in self.params.get(function.name, {}).values():
                if definition.line <= line:
                    items[(definition.name, definition.kind)] = definition
            for definition in self.locals.get(function.name, []):
                if definition.line <= line:
                    items[(definition.name, definition.kind)] = definition
        return list(items.values())

    def asm_labels_for(self, file: str | Path) -> list[Definition]:
        target = _normalise(file)
        return [
            definition
            for (path, _), definition in self.asm_labels.items()
            if path == target
        ]

    def inline_asm_at(
        self, file: str | Path, line: int
    ) -> Optional[InlineAsmContext]:
        target = _normalise(file)
        matches = [
            context
            for context in self.inline_asm_contexts
            if context.file == target
            and context.start_line <= line <= context.end_line
        ]
        if not matches:
            return None
        return min(
            matches, key=lambda context: context.end_line - context.start_line
        )

    def function_at(
        self, file: str | Path, line: int
    ) -> Optional[Definition]:
        target = _normalise(file)
        matches = [
            (start, end, definition)
            for path, start, end, definition in self.function_ranges
            if path == target and start <= line <= end
        ]
        if not matches:
            return None
        matches.sort(key=lambda item: item[1] - item[0])
        return matches[0][2]

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _add_occurrence(
        self,
        name: str,
        file: str,
        line: int,
        column: int,
        kind: str,
        definition: Optional[Definition],
        length: Optional[int] = None,
        detail: str = "",
    ) -> None:
        if not name or line <= 0:
            return
        self.occurrences.append(
            Occurrence(
                name=name,
                file=_normalise(file),
                line=line,
                column=max(1, column),
                length=max(1, length if length is not None else len(name)),
                kind=kind,
                definition=definition,
                detail=detail,
            )
        )

    def _build(self) -> None:
        for name in ROUTINE_LABELS:
            self.runtime[name] = Definition(
                name=name,
                kind="runtime",
                file="",
                line=0,
                column=0,
                detail=f"compiler runtime routine `{name}`",
            )

        for name, typ in BUILTINS.items():
            self.builtins[name] = Definition(
                name=name,
                kind="builtin",
                file="",
                line=0,
                column=0,
                detail=f"builtin returning {typ}",
                type=str(typ),
            )

        if self.program is not None:
            self._build_program(self.program)
            asm_sources = {
                _normalise(source.path): source.text
                for source in self.program.asm_sources
            }
        else:
            asm_sources = {}
        asm_sources.update(self.extra_asm)
        for path, text in asm_sources.items():
            self._build_asm(path, text)

    def _build_program(self, program: ast.Program) -> None:
        for decl in program.globals:
            kind = "constant" if decl.is_const else "global"
            detail = _type_detail(str(decl.type), decl.name, decl.array_len)
            if decl.is_const:
                detail = f"const {detail}"
            definition = Definition(
                name=decl.name,
                kind=kind,
                file=_normalise(decl.file or self.entry),
                line=decl.line,
                column=decl.column or 1,
                detail=detail,
                type=str(decl.type),
                const_value=None,
                array_len=decl.array_len,
            )
            self.globals[decl.name] = definition
            self._add_occurrence(
                decl.name,
                definition.file,
                definition.line,
                definition.column,
                "declaration",
                definition,
            )

        for fn in program.functions:
            param_defs: dict[str, Definition] = {}
            params: list[Definition] = []
            for param in fn.params:
                definition = Definition(
                    name=param.name,
                    kind="param",
                    file=_normalise(param.file or fn.file or self.entry),
                    line=param.line,
                    column=param.column or 1,
                    detail=_type_detail(str(param.type), param.name),
                    type=str(param.type),
                )
                param_defs[param.name] = definition
                params.append(definition)
            definition = Definition(
                name=fn.name,
                kind="function",
                file=_normalise(fn.file or self.entry),
                line=fn.name_line or fn.line,
                column=fn.name_column or fn.column or 1,
                detail=_function_detail(fn),
                type=str(fn.return_type),
                is_extern=fn.is_extern,
                params=params,
            )
            self.functions[fn.name] = definition
            self.params[fn.name] = param_defs
            self.function_ranges.append(
                (
                    definition.file,
                    fn.line,
                    _max_line(fn.body) if fn.body.statements else fn.line,
                    definition,
                )
            )
            self._add_occurrence(
                fn.name,
                definition.file,
                definition.line,
                definition.column,
                "declaration",
                definition,
            )
            for param in params:
                self._add_occurrence(
                    param.name,
                    param.file,
                    param.line,
                    param.column,
                    "declaration",
                    param,
                )

        # Initializers and bodies are visited only after every global and
        # function has been registered, so forward references resolve.
        for decl in program.globals:
            if decl.init is not None:
                self._visit_expr(decl.init, [], None)
            for item in decl.init_list or []:
                self._visit_expr(item, [], None)

        for fn in program.functions:
            if not fn.is_extern:
                scopes: list[dict[str, Definition]] = [dict(self.params[fn.name])]
                self._visit_block(fn.body, scopes, fn.name)

    def _build_asm(self, path: str, text: str) -> None:
        try:
            scan = scan_asm(text, path)
        except Exception:
            return

        for label, line in scan.labels.items():
            column = scan.label_columns.get(label, 1)
            kind = "asm_function" if label.startswith("fn_") else "asm_label"
            detail = (
                f"{label} (assembly entry point)"
                if kind == "asm_function"
                else f"{label} (assembly label)"
            )
            definition = Definition(
                name=label,
                kind=kind,
                file=path,
                line=line,
                column=column,
                detail=detail,
            )
            self.asm_labels[(path, label)] = definition
            if label.startswith("fn_"):
                function = self.functions.get(label[3:])
                if function is not None and function.is_extern:
                    function.asm_file = path
                    function.asm_line = line
                    function.asm_column = column
            self._add_occurrence(
                label, path, line, column, "declaration", definition
            )

        for function_label, placeholder in scan.placeholders:
            self._add_asm_placeholder(path, function_label, placeholder)

        for call in scan.calls:
            definition = self.functions.get(call.target_label[3:])
            if definition is None:
                definition = self.asm_labels.get((path, call.target_label))
            self._add_occurrence(
                call.target_label,
                path,
                call.line,
                call.column,
                "asm_call",
                definition,
                length=len(call.target_label),
            )

        for call in scan.runtime_calls:
            definition = self.runtime.get(call.target_label)
            self._add_occurrence(
                call.target_label,
                path,
                call.line,
                call.column,
                "asm_call",
                definition,
                length=len(call.target_label),
            )

    def _add_asm_placeholder(
        self,
        path: str,
        function_label: Optional[str],
        placeholder: Placeholder,
    ) -> None:
        text = placeholder.text.strip()
        if text.startswith("&"):
            text = text[1:].strip()
        match = re.match(
            r"^([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)",
            text,
        )
        if match is None:
            return
        base = match.group(1)
        definition = self._resolve_asm_name(base, function_label)

        self._add_occurrence(
            placeholder.text,
            path,
            placeholder.line,
            placeholder.start + 1,
            "asm_placeholder",
            definition,
            length=max(1, placeholder.end - placeholder.start),
            detail=f"asm placeholder `${{{placeholder.text}}}`",
        )

    def _resolve_asm_name(
        self, name: str, function_label: Optional[str]
    ) -> Optional[Definition]:
        qualified = _QUALIFIED_RE.match(name)
        if qualified is not None:
            function_name, param_name = qualified.groups()
            return self.params.get(function_name, {}).get(param_name)
        if function_label is not None:
            function_name = function_label[3:]
            parameter = self.params.get(function_name, {}).get(name)
            if parameter is not None:
                return parameter
        return self.globals.get(name)

    # ------------------------------------------------------------------
    # AST traversal
    # ------------------------------------------------------------------

    def _visit_block(
        self,
        block: ast.Block,
        scopes: list[dict[str, Definition]],
        function_name: Optional[str],
    ) -> None:
        local_scope: dict[str, Definition] = {}
        scopes.append(local_scope)
        for statement in block.statements:
            self._visit_stmt(statement, scopes, function_name)
        scopes.pop()

    def _visit_stmt(
        self,
        statement: ast.Stmt,
        scopes: list[dict[str, Definition]],
        function_name: Optional[str],
    ) -> None:
        if isinstance(statement, ast.Block):
            self._visit_block(statement, scopes, function_name)
        elif isinstance(statement, ast.VarDecl):
            kind = "constant" if statement.is_const else "local"
            detail = _type_detail(str(statement.type), statement.name, statement.array_len)
            if statement.is_const:
                detail = f"const {detail}"
            definition = Definition(
                name=statement.name,
                kind=kind,
                file=_normalise(statement.file or self.entry),
                line=statement.line,
                column=statement.column or 1,
                detail=detail,
                type=str(statement.type),
                array_len=statement.array_len,
            )
            scopes[-1][statement.name] = definition
            if function_name is not None:
                self.locals.setdefault(function_name, []).append(definition)
            self._add_occurrence(
                statement.name,
                definition.file,
                definition.line,
                definition.column,
                "declaration",
                definition,
            )
            if statement.init is not None:
                self._visit_expr(statement.init, scopes, function_name)
        elif isinstance(statement, ast.Assign):
            self._visit_expr(statement.target, scopes, function_name)
            self._visit_expr(statement.value, scopes, function_name)
        elif isinstance(statement, ast.ExprStmt):
            self._visit_expr(statement.expr, scopes, function_name)
        elif isinstance(statement, ast.If):
            self._visit_expr(statement.condition, scopes, function_name)
            self._visit_block(statement.then_block, scopes, function_name)
            if statement.else_block is not None:
                self._visit_block(statement.else_block, scopes, function_name)
        elif isinstance(statement, ast.While):
            self._visit_expr(statement.condition, scopes, function_name)
            self._visit_block(statement.body, scopes, function_name)
        elif isinstance(statement, ast.For):
            scopes.append({})
            if statement.init is not None:
                self._visit_stmt(statement.init, scopes, function_name)
            if statement.condition is not None:
                self._visit_expr(statement.condition, scopes, function_name)
            if statement.update is not None:
                self._visit_stmt(statement.update, scopes, function_name)
            self._visit_block(statement.body, scopes, function_name)
            scopes.pop()
        elif isinstance(statement, ast.Return):
            if statement.value is not None:
                self._visit_expr(statement.value, scopes, function_name)
        elif isinstance(statement, ast.InlineAsm):
            self._visit_inline_asm(statement, scopes)
            visible: list[Definition] = []
            for scope in scopes:
                visible.extend(scope.values())
            visible.extend(self.globals.values())
            file = _normalise(statement.file or self.entry)
            self.inline_asm_contexts.append(
                InlineAsmContext(
                    file=file,
                    start_line=statement.line,
                    end_line=_max_line(statement),
                    text=statement.text,
                    visible=visible,
                )
            )

    def _visit_inline_asm(
        self,
        statement: ast.InlineAsm,
        scopes: list[dict[str, Definition]],
    ) -> None:
        file = _normalise(statement.file or self.entry)
        for placeholder in iter_placeholders(statement.text):
            text = placeholder.text.strip()
            if text.startswith("&"):
                text = text[1:].strip()
            match = re.match(
                r"^([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)",
                text,
            )
            if match is None:
                continue
            base = match.group(1)
            qualified = _QUALIFIED_RE.match(base)
            if qualified is not None:
                definition = self.params.get(qualified.group(1), {}).get(
                    qualified.group(2)
                )
            else:
                definition = self._resolve_var(base, scopes)
            self._add_occurrence(
                placeholder.text,
                file,
                statement.line + placeholder.line - 1,
                placeholder.start + 1,
                "asm_placeholder",
                definition,
                length=max(1, placeholder.end - placeholder.start),
                detail=f"asm placeholder `${{{placeholder.text}}}`",
            )

        for index, line in enumerate(statement.text.splitlines(), 1):
            for match in ASM_CALL_RE.finditer(code_part(line)):
                target = match.group(1)
                definition = self.functions.get(target[3:])
                self._add_occurrence(
                    target,
                    file,
                    statement.line + index - 1,
                    match.start(1) + 1,
                    "asm_call",
                    definition,
                    length=len(target),
                )

    def _visit_expr(
        self,
        expression: ast.Expr,
        scopes: list[dict[str, Definition]],
        function_name: Optional[str],
    ) -> None:
        if isinstance(expression, ast.Var):
            definition = self._resolve_var(expression.name, scopes)
            self._add_occurrence(
                expression.name,
                expression.file or self.entry,
                expression.line,
                expression.column or 1,
                "variable",
                definition,
            )
        elif isinstance(expression, ast.Call):
            definition = self.functions.get(expression.name)
            if definition is None:
                definition = self.builtins.get(expression.name)
            self._add_occurrence(
                expression.name,
                expression.file or self.entry,
                expression.line,
                expression.column or 1,
                "call",
                definition,
            )
            for argument in expression.args:
                self._visit_expr(argument, scopes, function_name)
        elif isinstance(expression, ast.Index):
            self._visit_expr(expression.base, scopes, function_name)
            self._visit_expr(expression.index, scopes, function_name)
        elif isinstance(expression, ast.Member):
            self._visit_expr(expression.base, scopes, function_name)
        elif isinstance(expression, ast.Unary):
            self._visit_expr(expression.operand, scopes, function_name)
        elif isinstance(expression, ast.AddressOf):
            self._visit_expr(expression.operand, scopes, function_name)
        elif isinstance(expression, ast.Binary):
            self._visit_expr(expression.left, scopes, function_name)
            self._visit_expr(expression.right, scopes, function_name)
        elif isinstance(expression, (ast.Cast, ast.ToType)):
            self._visit_expr(expression.operand, scopes, function_name)

    def _resolve_var(
        self, name: str, scopes: list[dict[str, Definition]]
    ) -> Optional[Definition]:
        for scope in reversed(scopes):
            definition = scope.get(name)
            if definition is not None:
                return definition
        return self.globals.get(name)

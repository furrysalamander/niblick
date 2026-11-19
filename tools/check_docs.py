"""Check documentation style, links, headings, and navigation."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
EXTRA = [
    ROOT / "README.md",
    ROOT / "web" / "README.md",
    ROOT / "examples" / "README.md",
    ROOT / "editors" / "vscode" / "README.md",
    ROOT / "RELEASING.md",
]

PROHIBITED = [
    (r"\bnote that\b", "note that"),
    (r"\bit is worth\b", "it is worth"),
    (r"\bworth (noting|knowing)\b", "worth noting"),
    (r"\bkeep in mind\b", "keep in mind"),
    (r"\bsimply\b", "simply"),
    (r"\bjust\b", "just"),
    (r"\bobviously\b", "obviously"),
    (r"\bof course\b", "of course"),
    (r"\brobust\b", "robust"),
    (r"\bseamless\b", "seamless"),
    (r"\bpowerful\b", "powerful"),
    (r"\bcomprehensive\b", "comprehensive"),
    (r"\balmost certainly\b", "almost certainly"),
    (r"\bprobably\b", "probably"),
    (r"\blikely\b", "likely"),
    (r"\btypically\b", "typically"),
    (r"\bin practice\b", "in practice"),
    (r"\bthis is what makes\b", "this is what makes"),
    (r"\bthe result is\b", "the result is"),
    (r"\bnot just\b", "not just"),
    (r"\ballows you to\b", "allows you to"),
    (r"\blets you\b", "lets you"),
    (r"\byou can\b", "you can"),
    (r"\b(you|your|we|our|us)\b", "first or second person"),
    (r"\blet's\b", "let's"),
    (r"\bshould\b", "should"),
    (r"\bin order to\b", "in order to"),
    (r"\butilize\b", "utilize"),
    (r"\bleverage\b", "leverage"),
    (r"\bwhich means\b", "which means"),
    (r"\bdesigned to\b", "designed to"),
    (r"\bbuilt to\b", "built to"),
    (r"—", "em dash"),
    (r"\*\*[^*\n]+\*\*", "bold emphasis"),
]

DOC_RE = re.compile(r"\{doc\}`([^`]+)`")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def doc_files() -> list[Path]:
    files = sorted(DOCS.rglob("*.md"))
    files = [path for path in files if "_build" not in path.parts]
    return files + [path for path in EXTRA if path.exists()]


def strip_fences(text: str) -> str:
    """Blank fenced code blocks, preserving line numbers and inline code."""
    out: list[str] = []
    fence = False
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            fence = not fence
            out.append("")
            continue
        out.append("" if fence else line)
    return "\n".join(out)


def strip_code(text: str) -> str:
    """Blank fenced code blocks and inline code, preserving line numbers."""
    return re.sub(r"`[^`]*`", "", strip_fences(text))


def check_prose(path: Path, errors: list[str]) -> None:
    if path.name == "docs-style.md":
        return
    text = strip_code(path.read_text(encoding="utf-8"))
    for number, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith(">"):
            continue
        for pattern, label in PROHIBITED:
            if re.search(pattern, line, flags=re.IGNORECASE):
                errors.append(f"{path.relative_to(ROOT)}:{number}: {label}: {line.strip()}")


def check_headings(path: Path, errors: list[str]) -> None:
    text = strip_fences(path.read_text(encoding="utf-8"))
    headings: list[tuple[int, str, int]] = []
    for number, line in enumerate(text.splitlines(), 1):
        match = re.match(r"^(#{1,6})\s+(.*)$", line)
        if match:
            headings.append((len(match.group(1)), match.group(2).strip(), number))
    h1 = [item for item in headings if item[0] == 1]
    if len(h1) != 1:
        errors.append(f"{path.relative_to(ROOT)}: expected one H1, found {len(h1)}")
    seen: dict[str, int] = {}
    previous = 0
    for level, title, number in headings:
        key = title.lower()
        if key in seen:
            errors.append(
                f"{path.relative_to(ROOT)}:{number}: duplicate heading {title!r} "
                f"(first at line {seen[key]})"
            )
        else:
            seen[key] = number
        if previous and level > previous + 1:
            errors.append(
                f"{path.relative_to(ROOT)}:{number}: heading jump H{previous} to H{level}"
            )
        previous = level


def check_links(path: Path, errors: list[str]) -> None:
    text = strip_code(path.read_text(encoding="utf-8"))
    for number, line in enumerate(text.splitlines(), 1):
        for match in DOC_RE.finditer(line):
            target = match.group(1).split("#", 1)[0]
            if not target:
                continue
            resolved = (path.parent / target).resolve()
            if not (
                resolved.with_suffix(".md").is_file()
                or (resolved / "index.md").is_file()
            ):
                errors.append(
                    f"{path.relative_to(ROOT)}:{number}: missing doc target {target!r}"
                )
        for match in LINK_RE.finditer(line):
            target = match.group(1).strip()
            if (
                not target
                or target.startswith(("#", "http://", "https://", "mailto:"))
                or target.startswith("<")
            ):
                continue
            target = target.split("#", 1)[0]
            if not target:
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                errors.append(
                    f"{path.relative_to(ROOT)}:{number}: missing link target {target!r}"
                )


def toctree_entries() -> set[str]:
    text = (DOCS / "index.md").read_text(encoding="utf-8")
    entries: set[str] = set()
    inside = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```{toctree}"):
            inside = True
            continue
        if inside and stripped.startswith("```"):
            inside = False
            continue
        if inside and stripped and not stripped.startswith(":"):
            entries.add(stripped)
    return entries


def check_navigation(errors: list[str]) -> None:
    entries = toctree_entries()
    for entry in entries:
        if not (DOCS / f"{entry}.md").is_file():
            errors.append(f"docs/index.md: missing toctree page {entry!r}")
    listed = {entry + ".md" for entry in entries}
    for path in sorted(DOCS.rglob("*.md")):
        if "_build" in path.parts or path.name == "index.md" and path.parent == DOCS:
            continue
        relative = path.relative_to(DOCS).as_posix()
        if relative not in listed:
            errors.append(f"docs/index.md: page not in toctree: {relative}")


def main() -> int:
    errors: list[str] = []
    for path in doc_files():
        check_prose(path, errors)
        check_headings(path, errors)
        check_links(path, errors)
    check_navigation(errors)
    for error in errors:
        print(error)
    if errors:
        print(f"{len(errors)} documentation issue(s)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

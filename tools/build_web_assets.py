"""Build the wheel and runtime assets used by the web editor."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "web" / "public"
WHEELS = PUBLIC / "wheels"
RUNTIME = PUBLIC / "runtime.zip"
EXAMPLES = PUBLIC / "examples"
ASSEMBLER_REQUIREMENT = (
    "supercon6-assembler @ "
    "git+https://github.com/furrysalamander/2022-Supercon6-Badge-Tools.git"
    "@c576ebd08d4916909c89497fba1e1158eb540685#subdirectory=assembler"
)


def build_niblick_wheel() -> None:
    WHEELS.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--outdir",
            str(WHEELS),
        ],
        cwd=ROOT,
        check=True,
    )


def build_assembler_wheel() -> None:
    if any(WHEELS.glob("supercon6_assembler-*.whl")):
        return
    WHEELS.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--wheel-dir",
            str(WHEELS),
            ASSEMBLER_REQUIREMENT,
        ],
        cwd=ROOT,
        check=True,
    )


def write_wheel_manifest() -> None:
    niblick = next(iter(sorted(WHEELS.glob("niblick-*.whl"))), None)
    assembler = next(iter(sorted(WHEELS.glob("supercon6_assembler-*.whl"))), None)
    if niblick is None or assembler is None:
        raise RuntimeError("missing compiler or assembler wheel")
    (WHEELS / "manifest.json").write_text(
        json.dumps(
            {
                "niblick": niblick.name,
                "assembler": assembler.name,
            },
            indent=2,
        )
        + "\n"
    )


def runtime_files() -> list[Path]:
    files: list[Path] = []
    files.extend(sorted((ROOT / "lib").rglob("*.nbl")))
    files.extend(sorted((ROOT / "lib").rglob("*.asm")))
    files.extend(sorted((ROOT / "examples").glob("*.nbl")))
    files.extend(sorted((ROOT / "examples" / "asm").rglob("*.asm")))
    return [
        path
        for path in files
        if "__pycache__" not in path.parts and path.is_file()
    ]


def build_runtime_zip() -> None:
    PUBLIC.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(RUNTIME, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in runtime_files():
            archive.write(path, path.relative_to(ROOT).as_posix())


def copy_examples() -> None:
    if EXAMPLES.exists():
        shutil.rmtree(EXAMPLES)
    EXAMPLES.mkdir(parents=True)
    entries = []
    for source in sorted((ROOT / "examples").glob("*.nbl")):
        target = EXAMPLES / source.name
        shutil.copy2(source, target)
        entries.append({"name": source.stem, "path": source.name})
    (EXAMPLES / "manifest.json").write_text(
        json.dumps(entries, indent=2) + "\n"
    )


def main() -> int:
    build_niblick_wheel()
    build_assembler_wheel()
    write_wheel_manifest()
    build_runtime_zip()
    copy_examples()
    print(f"wheels: {WHEELS}")
    for wheel in sorted(WHEELS.glob("*.whl")):
        print(f"  {wheel.name} {wheel.stat().st_size} bytes")
    print(f"runtime: {RUNTIME} {RUNTIME.stat().st_size} bytes")
    print(f"examples: {EXAMPLES} ({len(list(EXAMPLES.glob('*.nbl')))} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

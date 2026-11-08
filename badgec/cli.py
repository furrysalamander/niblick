"""Command line interface for BadgeC."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .assembler import assemble_file, code_words
from .compiler import Compiler
from .disasm import decode
from .emulator import Emulator
from .errors import BadgeError
from .loader import load_program


def compile_source(
    source_path: str | Path,
    output_dir: str | Path | None = None,
    assemble: bool = True,
    run: bool = False,
    max_steps: int = 100000,
    show_map: bool = False,
    strip_runtime: bool = True,
    asm_optimize: bool = True,
    map_json: str | Path | None = None,
    show_symbols: bool = False,
    show_callgraph: bool = False,
    show_stack: bool = False,
    trace: bool = False,
    trace_io: bool = False,
    trace_limit: int = 200,
    io_trace_limit: int | None = 2000,
    dump_ram: bool = False,
    dump_uart: bool = False,
    dump_sfr: bool = False,
) -> tuple[Path, Path | None]:
    source_path = Path(source_path)
    program = load_program(source_path)
    compiler = Compiler(
        program,
        str(source_path),
        strip_runtime=strip_runtime,
        asm_optimize=asm_optimize,
    )
    asm = compiler.compile()

    out_dir = Path(output_dir) if output_dir is not None else source_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    asm_path = out_dir / (source_path.stem + ".asm")
    asm_path.write_text(asm)

    hex_path: Path | None = None
    words: int | None = None
    if assemble:
        hex_path = out_dir / (source_path.stem + ".hex")
        assemble_file(asm_path, hex_path)
        words = code_words(hex_path)

    print(f"compiled {source_path} -> {asm_path}")
    if hex_path is not None and words is not None:
        if words > 4096:
            raise BadgeError(
                f"program is {words} words, but the badge has only 4096 words of code space"
            )
        print(f"  code+data: {words} / 4096 words")
        print(f"  data RAM:  {compiler.mem.used()} / 208 nibbles")
        print(f"  max non-tail call depth: {compiler.max_call_depth}")

    for warning in compiler.stack_warnings:
        print(f"warning: {warning}", file=sys.stderr)

    if show_map:
        print_map(compiler)
    if show_symbols:
        print_symbols(compiler, words)
    if show_callgraph:
        print_callgraph(compiler)
    if show_stack:
        print_stack(compiler)

    if map_json is not None:
        data = compiler.map_data(total_words=words)
        if words is not None:
            data["code_words"] = words
        Path(map_json).write_text(json.dumps(data, indent=2) + "\n")
        print(f"  map written to {map_json}")

    if run:
        if hex_path is None:
            raise BadgeError("running requires assembly; remove --no-assemble")
        emu = Emulator()
        emu.load_hex(hex_path)
        if trace_io:
            emu.trace_io(limit=io_trace_limit)
        if trace:
            steps = run_traced(emu, max_steps=max_steps, limit=trace_limit)
        else:
            steps = emu.run(max_steps=max_steps)
        print(f"  ran {steps} instructions; {emu.cycle_count} cycles; ~{emu.elapsed_seconds:.4f}s at {emu.clock_hz:g} Hz")
        print_state(emu)
        if dump_ram:
            print_ram(emu)
        if dump_uart:
            print_uart(emu)
        if dump_sfr:
            print_sfrs(emu)
        if trace_io:
            print_io_trace(emu)

    return asm_path, hex_path


def print_map(compiler: Compiler) -> None:
    print("  globals:")
    if not compiler.globals:
        print("    (none)")
    for name, symbol in compiler.globals.items():
        if symbol.flash_label is not None:
            print(f"    {name}: flash {symbol.flash_label} ({symbol.array_len} elements)")
        elif symbol.const_value is not None:
            print(f"    {name}: const 0x{symbol.const_value:X} ({symbol.type})")
        elif symbol.array_len is not None:
            print(f"    {name}: RAM 0x{symbol.address:02X} ({symbol.array_len} elements)")
        else:
            print(f"    {name}: RAM 0x{symbol.address:02X}")


def print_symbols(compiler: Compiler, total_words: int | None = None) -> None:
    sizes = compiler.code_sizes(total_words)
    print("  functions:")
    for name, fn in compiler.functions.items():
        params = ", ".join(f"{p.name}:{p.type}@0x{p.address:02X}" for p in fn.params)
        words = sizes["functions"].get(name, 0)
        print(f"    {name} -> {fn.decl.return_type} [{fn.label}] {words} words {params}")
    if compiler.flash:
        print("  flash data:")
        for item in compiler.flash:
            words = len(item.values) * max(item.type.flash_size, 1)
            print(f"    {item.label}: {item.type}[{len(item.values)}] {words} words")
    print("  runtime:")
    if not sizes["runtime"]:
        print("    (none)")
    for label, words in sorted(sizes["runtime"].items(), key=lambda item: (-item[1], item[0])):
        print(f"    {label}: {words} words")
    print(f"  startup/other: {sizes['startup']} words")
    print(f"  total: {sizes['total']} words")


def print_stack(compiler: Compiler) -> None:
    print("  stack report:")
    print(f"    user depth: {compiler.max_call_depth} / 4 (hardware has 5 entries)")
    if compiler.deepest_path:
        print(f"    deepest path: {' -> '.join(compiler.deepest_path)}")
    print("    function entry depths:")
    if not compiler.function_depths:
        print("      (none)")
    for name, depth in sorted(
        compiler.function_depths.items(), key=lambda item: (-item[1], item[0])
    ):
        print(f"      {name}: {depth}")
    print("    runtime calls:")
    if not compiler.stack_call_sites:
        print("      (none)")
    for site in compiler.stack_call_sites:
        source = f"{site.get('file', '')}:{site['line']}"
        print(
            f"      {site['caller']} ({source}) -> {site['entry']} "
            f"(cost {site['cost']}) total {site['total']}/5"
        )
    print("    linked runtime costs:")
    if not compiler.linked_runtime:
        print("      (none)")
    for label in sorted(compiler.linked_runtime):
        print(f"      {label}: {compiler.runtime_costs.get(label, 1)}")
    if compiler.stack_warnings:
        print("    warnings:")
        for warning in compiler.stack_warnings:
            print(f"      {warning}")


def print_io_trace(emu: Emulator) -> None:
    events = emu.io_trace or []
    suffix = ""
    if len(events) < emu.io_trace_total:
        suffix = f" (showing first {len(events)})"
    print(f"  I/O trace: {emu.io_trace_total} events{suffix}")
    for event in events:
        bit = f" bit={event.bit}" if event.bit is not None else ""
        print(
            f"    {event.step:06d} pc=0x{event.pc:03X} {event.kind:<5} "
            f"0x{event.address:02X}{bit} 0x{event.before:X} -> 0x{event.after:X}"
        )


def print_callgraph(compiler: Compiler) -> None:
    print("  call graph:")
    if not compiler.calls:
        print("    (none)")
    for caller, callee, tail, line, filename in compiler.calls:
        kind = "tail" if tail else "call"
        print(f"    {caller} -> {callee} ({kind}, {filename}:{line})")


def print_state(emu: Emulator) -> None:
    regs = " ".join(f"R{i}=0x{emu.ram[i]:X}" for i in range(10))
    print(f"  pc=0x{emu.pc:03X} sp={emu.sp} C={emu.C} Z={emu.Z} V={emu.V}")
    print(f"  {regs}")
    print(
        "  OUT=0x{:X} IN=0x{:X} Received=0x{:X}".format(
            emu.ram[0x0A], emu.ram[0x0B], emu.ram[0xF8]
        )
    )


def print_ram(emu: Emulator) -> None:
    print("  RAM:")
    for row in range(16):
        values = " ".join(f"{emu.ram[row * 16 + col]:X}" for col in range(16))
        print(f"    {row:X}0: {values}")


def print_uart(emu: Emulator) -> None:
    print(f"  UART TX: {bytes(emu.uart_tx)!r}")
    print(f"  UART RX: {bytes(emu.uart_rx)!r}")
    print(f"  UART error: {emu.uart_error}")


def print_sfrs(emu: Emulator) -> None:
    names = {
        0xF0: "Page",
        0xF1: "Clock",
        0xF2: "Sync",
        0xF3: "WrFlags",
        0xF4: "RdFlags",
        0xF5: "SerCtrl",
        0xF6: "SerLow",
        0xF7: "SerHigh",
        0xF8: "Received",
        0xF9: "AutoOff",
        0xFA: "OutB",
        0xFB: "InB",
        0xFC: "KeyStatus",
        0xFD: "KeyReg",
        0xFE: "Dimmer",
        0xFF: "Random",
    }
    print("  SFRs:")
    for address, name in names.items():
        print(f"    {address:02X} {name:<10} 0x{emu.ram[address]:X}")


def run_traced(emu: Emulator, max_steps: int, limit: int = 200) -> int:
    steps = 0
    while steps < max_steps and not emu.halted:
        pc = emu.pc
        word = emu.program[pc]
        emu.step()
        if steps < limit:
            print(
                f"  {steps:06d} pc={pc:03X} word={word:03X} {decode(word):<20} "
                f"R0={emu.ram[0]:X} R1={emu.ram[1]:X} R2={emu.ram[2]:X} "
                f"sp={emu.sp} C={emu.C} Z={emu.Z}"
            )
        steps += 1
    if steps >= limit:
        print(f"  ... trace truncated after {limit} instructions")
    return steps


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="badgec", description="BadgeC compiler for the Supercon.6 badge")
    parser.add_argument("source", help="BadgeC source file")
    parser.add_argument("-o", "--output-dir", help="directory for generated .asm/.hex files")
    parser.add_argument("--no-assemble", action="store_true", help="emit assembly only")
    parser.add_argument("--run", action="store_true", help="run the generated program in the emulator")
    parser.add_argument("--max-steps", type=int, default=100000, help="emulator step limit for --run")
    parser.add_argument("--map", action="store_true", help="print the global memory map")
    parser.add_argument("--map-json", help="write a JSON symbol map")
    parser.add_argument("--symbols", action="store_true", help="print functions, sizes, and flash labels")
    parser.add_argument("--callgraph", action="store_true", help="print the user call graph")
    parser.add_argument("--stack", action="store_true", help="print call-depth and runtime stack costs")
    parser.add_argument("--trace", action="store_true", help="trace emulator execution")
    parser.add_argument("--trace-limit", type=int, default=200, help="maximum traced instructions")
    parser.add_argument("--trace-io", action="store_true", help="trace OUT/OUTB/IN/INB accesses")
    parser.add_argument(
        "--io-trace-limit",
        type=int,
        default=2000,
        help="maximum stored I/O trace events (0 = unlimited)",
    )
    parser.add_argument("--dump-ram", action="store_true", help="dump RAM after running")
    parser.add_argument("--dump-uart", action="store_true", help="dump UART TX/RX after running")
    parser.add_argument("--dump-sfr", action="store_true", help="dump SFRs after running")
    parser.add_argument(
        "--keep-runtime",
        action="store_true",
        help="link the entire runtime instead of only the routines used",
    )
    parser.add_argument(
        "--no-optimize",
        action="store_true",
        help="disable peephole and branch-relaxation optimizations",
    )
    args = parser.parse_args(argv)

    run = (
        args.run
        or args.trace
        or args.trace_io
        or args.dump_ram
        or args.dump_uart
        or args.dump_sfr
    )

    try:
        compile_source(
            args.source,
            output_dir=args.output_dir,
            assemble=not args.no_assemble,
            run=run,
            max_steps=args.max_steps,
            show_map=args.map,
            strip_runtime=not args.keep_runtime,
            asm_optimize=not args.no_optimize,
            map_json=args.map_json,
            show_symbols=args.symbols,
            show_callgraph=args.callgraph,
            show_stack=args.stack,
            trace=args.trace,
            trace_io=args.trace_io,
            trace_limit=args.trace_limit,
            io_trace_limit=None if args.io_trace_limit == 0 else args.io_trace_limit,
            dump_ram=args.dump_ram,
            dump_uart=args.dump_uart,
            dump_sfr=args.dump_sfr,
        )
    except BadgeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

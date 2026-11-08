# Debugging BadgeC programs

The VS Code extension includes a BadgeC emulator debugger. It compiles the
active `.badge` file, loads the resulting `.hex` into the existing headless
emulator, and exposes breakpoints, stepping, registers, flags, globals, and
UART output.

## Launch configuration

Add this to `.vscode/launch.json`:

```json
{
  "type": "badgec",
  "request": "launch",
  "name": "BadgeC: Run Program",
  "program": "${file}",
  "cwd": "${workspaceFolder}",
  "stopOnEntry": true
}
```

Then open a `.badge` file and press F5.

The extension also contributes a **BadgeC: Launch Program** configuration
snippet in the debug configuration picker.

## What works

- stop on entry;
- line breakpoints;
- continue and pause;
- step over, step into, and step out;
- registers `R0`–`R9`;
- flags `C`, `Z`, `V`;
- globals with their types and addresses;
- evaluate simple expressions (`x`, `R1`, `arr[2]`, `peek(0x40)`);
- UART output in the Debug Console;
- a basic source-level stack trace using the hardware return addresses.

## How the source map works

The compiler emits source markers into the generated assembly:

```asm
; @badgec-src /path/main.badge:12
```

After optimization, the debug map scans the final assembly and records the
word address of each marker. The map contains:

- file/line to PC addresses;
- PC to file/line;
- function start/end addresses;
- global addresses and types;
- assembler labels.

Generate one manually with:

```bash
python3 -m badgec examples/hello.badge --debug-map hello.map.json
```

## Debugging an existing `.hex`

Use the `hex` launch field instead of `program`:

```json
{
  "type": "badgec",
  "request": "launch",
  "name": "BadgeC: Run Hex",
  "hex": "${workspaceFolder}/examples/hello.hex",
  "debugMap": "${workspaceFolder}/examples/hello.map.json",
  "cwd": "${workspaceFolder}"
}
```

If the map is omitted, breakpoints and source-level stepping are unavailable,
but registers and execution still work.

## Python requirements

The debug service uses the repository's emulator:

```bash
python3 -m badgec.debug
```

No extra package is needed beyond the compiler itself. The extension
auto-detects `.venv/bin/python`, `venv/bin/python`, or falls back to
`python3`. Set `pythonPath` in the launch configuration to override it.

## Limitations

- Stepping is source-line based, not instruction based.
- Pause is implemented by stopping between emulator step chunks; it is not an
  immediate interrupt.
- UART output is shown when execution stops, not as a live stream.
- The stack trace is reconstructed from the five-entry hardware stack.
- The emulator does not model real-time clock speed or electrical behavior.

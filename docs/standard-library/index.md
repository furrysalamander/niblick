# Standard library

The standard library has three layers:

| Layer | Location | Import |
|---|---|---|
| Intrinsics | Compiler and `niblick/runtime/runtime.asm` | Built in |
| Standard modules | `lib/*.nbl` | `import "lib/<name>.nbl";` |
| Drivers | `lib/drivers/*.nbl` | Explicit import |

Each module is an ordinary Niblick source file. The compiler removes functions
and globals that are not reachable, so an unused module contributes no code or
RAM.

## Module index

| Module | Purpose |
|---|---|
| {doc}`intrinsics` | Compiler builtins and runtime-backed operations |
| {doc}`formatting` | Compile-time `print()` expansion |
| {doc}`uart` | UART setup, byte I/O, formatting, hex input |
| {doc}`gpio` | GPIO port reads and writes |
| {doc}`board` | Voja4 pin and default SPI constants |
| {doc}`display` | Display pages, framebuffer, pixels, lines, rectangles |
| {doc}`keys` | Front-panel key state and key codes |
| {doc}`time` | Clock, Sync, and delays |
| {doc}`power` | Auto-off and sleep |
| {doc}`system` | Raw status and control SFR access |
| {doc}`random` | Hardware PRNG helpers |
| {doc}`memory` | Nibble and byte memory operations |
| {doc}`strings` | RAM and flash string operations, number formatting |
| {doc}`math` | Integer helpers, square roots, mapping |
| {doc}`fixed-point` | Q4.4 fixed-point helpers |
| {doc}`trig` | Q4.4 sine and cosine table |
| {doc}`audio` | Square-wave output |
| {doc}`pdm` | PDM sample playback |
| {doc}`spi` | Bit-banged SPI mode-0 master |
| {doc}`font` | 5x8 font glyphs |
| {doc}`textscroll` | Horizontal text scroller |
| {doc}`drivers/w5500` | W5500 Ethernet register and socket access |

## Public and internal modules

The pages above document the public library. `lib/wide.nbl`,
`lib/float16.nbl`, and `lib/float32.nbl` are compiler implementation modules.
They are loaded automatically when a program uses 64-bit arithmetic or a float
type. Their interfaces are documented in {doc}`../internals/wide-arithmetic`
and {doc}`../internals/soft-float`.

## Import resolution

Imports resolve relative to the importing file, then the repository root,
installed data directory, and `NIBLICK_PATH` entries. See {doc}`../language/imports`.

## Calling conventions

All module functions use the normal Niblick calling convention. Argument and
return types follow {doc}`../language/types`. Stack costs for intrinsics and
runtime helpers are listed in {doc}`../internals/runtime-abi`.

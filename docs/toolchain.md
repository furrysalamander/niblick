# Toolchain

The Supercon.6 toolchain lives in the upstream
[Hack-a-Day/2022-Supercon6-Badge-Tools](https://github.com/Hack-a-Day/2022-Supercon6-Badge-Tools)
repository, which contains the Python assembler, a disassembler, a Tk emulator,
example programs, and Windows serial helpers. BadgeC uses the assembler through
the `supercon6-assembler` package; that package is installed automatically as a
BadgeC dependency. This page documents how to use the upstream tools for BadgeC
development and where they stop being faithful to hardware.

## Assembler

### Basic use

The package installs a `supercon6-assemble` console script and an importable
`assemble` module:

```sh
supercon6-assemble program.asm          # writes program.hex
supercon6-assemble program.asm -q       # quiet; file output only
supercon6-assemble program.asm -n       # show word addresses
supercon6-assemble program.asm -s       # 12-bit words with spaces
```

The output path is the input path with the extension replaced by `.hex`, in the
same directory as the input. The assembler requires Python 3.10+ and has no
dependencies beyond the standard library.

To run tools from an upstream checkout instead, clone
<https://github.com/Hack-a-Day/2022-Supercon6-Badge-Tools> and use
`python3 assembler/assemble.py ...`.

### Options

| Option | Effect |
|---|---|
| `-q` | Suppress human-readable listing; still writes `.hex` |
| `-c` | Show comments only in the listing |
| `-m` | Show original assembly (with comments) |
| `-n` | Show line/word numbers |
| `-s` | Show 12-bit words with spaces (`1001 0010 0111`) |
| `-w` | Show 12-bit words without spaces |

`-c`, `-m`, `-n`, `-s`, and `-w` mainly change the listing, not the binary.

### Source syntax

* One instruction per line; `;` starts a comment.
* Labels end with `:`; a leading `.` makes a label local to the last global label
  (the README does not mention this, but the implementation supports it).
* `EQU` defines a constant expression; `+`, `-`, `HIGH`, `MID`, `LOW` are
  supported. `HIGH`/`MID`/`LOW` extract nibbles 11..8 / 7..4 / 3..0.
* Numeric literals may be decimal, `0x` hex, or `0b` binary.
* Operands are comma-separated. Register names are limited to
  `R0`-`R9`, `OUT`, `IN`, `JSR`, `PCL`, `PCM`, `PCH`. R10-R15 cannot be named
  directly; use their data addresses via `MOV R0,[NN]` / `MOV [NN],R0`.
* `MOV PC,[NN]` requires brackets. The 8-bit value goes to `PCM`/`PCH`; it does
  not jump by itself.
* Pseudo-ops and generated sequences are listed in [isa.md](isa.md).

Assembler quirks worth knowing:

* It uppercases tokens, except the payload of `ASCII`.
* It will not move `ORG` backwards.
* `SKIP label` requires the resolved skip count to be 1-4; a label pointing at
  the very next word resolves to 0 (which means "skip 4") and is rejected.
* `JR label` is resolved relative to the next word, matching hardware. The range
  check is off by one at the top end: `+127` is rejected even though the hardware
  accepts `0x7F`.
* `R3` and `RS` in `BIT`/`BSET`/`BCLR`/`BTG` both encode `G=3`, which hardware
  maps to the I/O port (`IN` for `BIT`, `OUT` for the bit-write forms), not R3.
* `NOP`, `CPL`, `NEG`, `LSR`, `SL`, `RLC` are assembler pseudo-ops, not opcodes.

### `.hex` format

Despite the name, this is a custom binary container, not Intel HEX:

| Offset | Bytes | Content |
|---:|---:|---|
| 0 | 6 | `00 FF 00 FF A5 C3` |
| 6 | 2 | word count `N`, little-endian |
| 8 | `2N` | program words, little-endian, upper nibble 0 |
| `8+2N` | 2 | checksum, little-endian |

The checksum is the 16-bit sum (mod 65536) of the length field and all program
words. There is no address field and no EOF record; loading always starts at code
word 0. `ORG` creates `0x000` fill words inside the image.

Minimal validator:

```sh
python3 - <<'PY'
from pathlib import Path
b = Path("program.hex").read_bytes()
assert b[:6] == bytes([0,0xFF,0,0xFF,0xA5,0xC3])
n = b[6] | (b[7] << 8)
assert len(b) == 8 + 2*n + 2
s = sum(b[i] | (b[i+1] << 8) for i in range(6, 8 + 2*n, 2)) & 0xFFFF
assert b[-2] | (b[-1] << 8) == s
print(f"OK: {n} words")
PY
```

### Disassembler

The disassembler is not part of the installed `supercon6-assembler` package. Run
it from an upstream checkout:

```sh
cd 2022-Supercon6-Badge-Tools/assembler
python3 disassemble.py program.hex        # writes program.s
python3 disassemble.py program.hex -q
python3 disassemble.py program.hex -f     # continue if checksum is bad
```

The disassembler validates the header and checksum. `-c` shows source comments,
`-n` line numbers, `-s`/`-w` control spacing. It does not reconstruct `GOTO`,
`GOSUB`, `BYTE`, `NIBBLE`, or `ASCII`; those appear as the underlying `MOV`/`RET`
sequences. A round trip is therefore semantically equivalent, not textually
identical.

## Building and running upstream examples

Clone the upstream repository before using its examples:

```sh
git clone https://github.com/Hack-a-Day/2022-Supercon6-Badge-Tools
cd 2022-Supercon6-Badge-Tools
```

Most examples have a small makefile that calls the assembler and, optionally,
flashes the badge:

```sh
cd examples/Hackaday-bouncy_ball
make bouncy_ball.hex          # assemble only
make flash PORT=/dev/ttyUSB0  # assemble + send via cat
```

The makefiles differ slightly:

| Example | Target behavior |
|---|---|
| `Hackaday-bouncy_ball`, `octav-snake` | `all` builds; `flash` sends over `PORT` |
| `achasen-symbolscroll`, `Hackaday-hamlet` | `all` assembles and programs |
| `Hackaday-heart` | no makefile; run `assemble.py` directly |

There is no repository-wide build or test target. The Hamlet examples include
ad-hoc comparison scripts under `test/`; they assume a reference disassembly and
are not wired into `make`.

## Emulator (BVM)

### Running

The upstream GUI is run from a checkout:

```sh
cd 2022-Supercon6-Badge-Tools/emulator
python3 -m pip install pillow
python3 bvm.py ../examples/Hackaday-heart/heart.hex
```

Run from the `emulator/` directory: the GUI loads `gui_assets/badgeface.jpg`,
`gui_assets/pnp.csv`, and LED images by relative path. Tkinter must be available
(`python3-tk` on Debian/Ubuntu). A GUI display is required; there is no headless
mode in the upstream GUI.

The headless CPU core (`badge`, `bvmCPU`, and `bvmParser`) is available as the
optional `supercon6-emulator` package:

```sh
python3 -m pip install "git+https://github.com/Hack-a-Day/2022-Supercon6-Badge-Tools.git#subdirectory=emulator"
```

BadgeC's own emulator lives in `badgec/emulator.py` and is the primary test
model. The `fidelity` extra installs the upstream core for cross-checks.

The README calls the input a `.bin`; in practice `badge.py` expects the
assembler's 8-byte header + length + words + checksum container, so pass the
`.hex` file. The extension is irrelevant, the content is not.

### What it models

* The 4-bit CPU, flags, ALU, `EXR`, `SKIP`, `JR`, `RET`, and the 5-level stack.
* The 256-nibble data memory and 4096-word program memory.
* The LED matrix for two selected pages, PC, flags, stack pointer, and some ALU
  indicators.
* `Page` (`0xF0`) and `Clock` (`0xF1`) for display and speed selection.
* `Random` (`0xFF`) with a new random nibble on clock updates.
* `Dimmer`/other SFRs only as ordinary RAM values.

### Limitations

| Area | Limitation |
|---|---|
| Input | `Button` is an empty class; no key/button events. `KeyStatus`/`KeyReg` (`0xFC`/`0xFD`) are not simulated. |
| UART | `SerCtrl`/`SerLow`/`SerHigh`/`Received` (`0xF5`-`0xF8`) are plain RAM. No serial input/output, no FIFO, no baud timing. |
| SFR side effects | Reads/writes generally do not trigger hardware effects (JSR/PCL jumps are handled in the CPU; `UserSync`, `Vflag`, error flags, auto-off, PWM, and display blanking are not). |
| Timing | Wall-clock tick (`frameDelay` 10 ms, `0.5/speed` gate); not cycle-accurate. `Clock` indexes a speed table rather than modeling instruction costs. |
| Input file | Header is skipped, length is ignored, and checksum is not verified. Truncated/extra bytes can be silently accepted. |
| Instruction aliases | `BIT`/`BSET`/`BCLR`/`BTG` with `G=3` operate on `R3`, matching the assembler's `R3`/`RS` alias rather than the hardware I/O port (`IN` for `BIT`, `OUT` for the write forms). |
| Errors | Stack overflow/underflow raises a Python exception; it does not reproduce the badge's halted-error display. |
| Output | Prints every decoded instruction and stack event to stdout; very noisy for large programs. |

The source header says Python 3.10+; the README says 3.6+. Use 3.10+ to be safe.

## Flashing hardware

### Program memory (normal use)

1. Assemble to `.hex`.
2. Put the badge in **DIR** mode.
3. Start the sender, then press **LOAD** on the badge.
4. Send at **9600 8N1**, raw:

```sh
stty -F /dev/ttyUSB0 raw 9600
cat program.hex > /dev/ttyUSB0
```

The badge uses the main I/O connector, not the SAO header, for load/save. See
[serial.md](serial.md) for the protocol and wiring.

To save from the badge:

```sh
stty -F /dev/ttyUSB0 raw 9600
cat /dev/ttyUSB0 > out.hex       # start this first
# then press SAVE
```

Windows helpers are in the upstream repository's `software/Windows Tools/`
directory:

* `win_flash.py` — sends a file with pyserial. Set `PORT` at the top, then
  `python win_flash.py program.hex`. It writes 1024 trailing NUL bytes to work
  around flush behavior.
* `save_from_serial.py` — captures SAVE output. Set `PORT`, run it, then press
  SAVE within 5 seconds. Default output is `out.hex`.

Both require `pip install pyserial`.

### Flashing checklist (especially for agents)

These are the details that most often waste a flashing attempt:

1. **Use exactly one serial port.** A Tigard exposes two interfaces
   (`/dev/ttyUSB0` and `/dev/ttyUSB1`); only one is wired to the badge. Identify
   the correct channel with `udevadm info -q property -n /dev/ttyUSBn` or the
   adapter labels, then use that port consistently. Do **not** broadcast the
   same `.hex` to both channels. The second channel may be wired to another
   target or inject noise into the badge's UART.
2. **Use plain LOAD, not ALT+LOAD.** ALT+LOAD enters the firmware bootloader,
   whose LOAD LED blinks slowly and which expects a raw firmware image, not a
   program `.hex`. A slow blink means stop and exit/reset the bootloader.
3. **Timing matters.** The loader ignores bytes until it sees a valid header.
   Start the sender and press LOAD close together; if the sender finishes before
   LOAD, nothing is loaded. A sender that retries the whole file is more robust
   than a single one-shot write.
4. **The badge stays in DIR mode after loading.** The matrix is blank in DIR
   mode. Select **RUN** and press **RUN** to execute the new program.
5. **Pad the transfer.** Some FTDI/Tigard adapters buffer the tail. Appending
   about 1 KiB of NUL bytes after the `.hex` is harmless and helps flush the
   final bytes. The badge ignores the padding.
6. **Validate the container first.** The file starts with
   `00 FF 00 FF A5 C3`, followed by a 16-bit word count, the words, and a
   16-bit checksum. `examples/*.hex` from the BadgeC toolchain already satisfy
   this.
7. **Wiring:** 3.3 V logic, common ground, adapter TX to badge RX and adapter RX
   to badge TX. Use the main I/O connector (pins 2/3), not the SAO header. Do
   not parallel adapter VCC with the badge batteries.

A retrying sender that targets one channel is enough:

```python
import time
from pathlib import Path
import serial

port_name = "/dev/ttyUSB0"          # the one wired to the badge
data = Path("examples/wave.hex").read_bytes() + b"\0" * 1024
for _ in range(3):
    with serial.Serial(port_name, 9600, bytesize=8, parity="N", stopbits=1) as port:
        time.sleep(0.3)
        port.write(data)
        port.flush()
        time.sleep(len(data) / (9600 / 10.0))
    time.sleep(2)
```

### Firmware bootloader

This is separate from program LOAD and takes a raw firmware image, not a program
`.hex`:

1. Hold **ALT + LOAD** and ground the **RES** pin on the main header.
2. Release; LOAD blinks slowly.
3. Send the firmware image at 9600 8N1 raw (the upstream vendor image is
   `firmware/Badge_v99r3.bin`).
4. LOAD blinks fast; after roughly 20-30 s SAVE and LOAD are both solid.
5. Press **MODE** to view version/checksum; MODE again to exit.

Only the main connector's RX pin is active during bootload; TX is ignored. The
bootloader is write-protected and independent of the user program.

### Hardware caveats

* The badge is 3 V CMOS. Use a 3.3 V USB-UART; a 5 V adapter can damage it.
* Do not parallel the adapter's VCC with the badge batteries.
* Cross TX/RX and connect ground.
* `SerCtrl` baud settings do not affect program load/save or the bootloader; both
  are fixed at 9600.
* `RxTxPos` does not affect program load/save or the bootloader; both use the
  main I/O connector.

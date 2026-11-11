# Voja4 Instruction Set Reference

The Supercon.6 (2022) "Voja4" badge executes a 12-bit, 4-bit-word CPU implemented in
PIC24 firmware. This page is a compact reference for compiler and assembler work.
Primary source: the upstream
[Instruction Set](https://github.com/Hack-a-Day/2022-Supercon6-Badge-Tools/blob/main/manuals/2.Instruction_Set_v4.pdf)
(rev. 4, 2022-11-02); cross-checked against the
[User Manual](https://github.com/Hack-a-Day/2022-Supercon6-Badge-Tools/blob/main/manuals/1.User_Manual_v4.pdf)
and the assembler.

## Machine model

| Item | Value |
|---|---|
| Instruction word | 12 bits |
| Code space | 4096 words (`0x000`-`0xFFF`), PC is 12 bits |
| Data space | 256 nibbles (`0x00`-`0xFF`), see [memory-map.md](memory-map.md) |
| Registers | R0-R9 general purpose; R10-R15 are SFRs (R10/R11 recoverable) |
| Flags | `V` signed overflow, `Z` zero, `C` carry / inverse borrow |
| Stack | 5 subroutine levels, 3 nibbles per return address, in `0x10`-`0x1E` |
| Reset entry | PC = `0x000` on RUN; no interrupt/exception vectors |
| Multiply/divide | None; software only |

All instruction fields are nibbles:

```
 bits 11..8   bits 7..4   bits 3..0
+-----------+-----------+-----------+
|  OPCODE   | OPERAND X | OPERAND Y |
+-----------+-----------+-----------+
```

Most instructions use a 4-bit opcode in bits 11..8. Opcode `0x0` is an extended
opcode: bits 7..4 select the operation, bits 3..0 are a 4-bit operand.

### Operand notation

| Form | Meaning |
|---|---|
| `RX`, `RY`, `RG` | Direct register 0-15 (SFR names are valid destinations/sources) |
| `#N`, `N` | 4-bit immediate, `0..15` |
| `[NN]` | Direct data-memory address, 8-bit, `0x00..0xFF` |
| `[XY]` | Indirect data-memory address: `RX` supplies bits 7..4, `RY` bits 3..0 |
| `PC` | 12-bit code address (assembler pseudo-op expands to 2 words) |
| `F` | Skip condition: `C`, `NC`, `Z`, `NZ` (aliases `GTE`, `LT`, `EQ`, `NE`) |
| `M` | Bit number `0..3`, or skip count `0..4` |
| `RS` | Manual name for the I/O port selected by `G=3`; see the `BIT` note |

## Instruction summary

### 4-bit opcodes (`bits 11..8`)

| Op | Binary | Mnemonic | Operation | Flags |
|---|---|---|---|---|
| 1 | `0001` | `ADD RX,RY` | RX <- RX + RY | V Z C |
| 2 | `0010` | `ADC RX,RY` | RX <- RX + RY + C | V Z C |
| 3 | `0011` | `SUB RX,RY` | RX <- RX - RY | V Z C |
| 4 | `0100` | `SBB RX,RY` | RX <- RX - RY - C | V Z C |
| 5 | `0101` | `OR RX,RY` | RX <- RX OR RY | Z |
| 6 | `0110` | `AND RX,RY` | RX <- RX AND RY | Z |
| 7 | `0111` | `XOR RX,RY` | RX <- RX XOR RY | Z |
| 8 | `1000` | `MOV RX,RY` | RX <- RY | none |
| 9 | `1001` | `MOV RX,#N` | RX <- N | none |
| A | `1010` | `MOV [XY],R0` | data[RX:RY] <- R0 | none |
| B | `1011` | `MOV R0,[XY]` | R0 <- data[RX:RY] | none |
| C | `1100` | `MOV [NN],R0` | data[NN] <- R0 | none |
| D | `1101` | `MOV R0,[NN]` | R0 <- data[NN] | none |
| E | `1110` | `MOV PC,#NN` | PCM <- NN[3:0], PCH <- NN[7:4]; does **not** jump | none |
| F | `1111` | `JR NN` | PC <- PC + sign-extend(NN) | none |

`MOV PC,#NN` loads only the middle and high PC nibbles. A jump also needs a write
to PCL (`0x0D`). The assembler spells this `MOV PC,[NN]`; the `GOTO`/`GOSUB`
pseudo-ops generate the full two-word sequence.

### Extended opcodes (opcode nibble `0x0`)

| X | Binary | Mnemonic | Operation | Flags |
|---|---|---|---|---|
| 0 | `0000 0000` | `CP R0,#N` | flags from R0 - N; result discarded | C Z |
| 1 | `0000 0001` | `ADD R0,#N` | R0 <- R0 + N | V Z C |
| 2 | `0000 0010` | `INC RY` | RY <- RY + 1 | Z C |
| 3 | `0000 0011` | `DEC RY` | RY <- RY - 1 | Z C |
| 4 | `0000 0100` | `DSZ RY` | RY <- RY - 1; if RY=0 skip next word | none |
| 5 | `0000 0101` | `OR R0,#N` | R0 <- R0 OR N; C <- 1 | Z C |
| 6 | `0000 0110` | `AND R0,#N` | R0 <- R0 AND N; C <- 0 | Z C |
| 7 | `0000 0111` | `XOR R0,#N` | R0 <- R0 XOR N; C <- ~C | Z C |
| 8 | `0000 1000` | `EXR #N` | swap R0..R(N-1) with `0xE0..`; N=0 means 16 | none |
| 9 | `0000 1001` | `BIT RG,M` | Z <- NOT(bit M of RG) | Z |
| A | `0000 1010` | `BSET RG,M` | set bit M | none |
| B | `0000 1011` | `BCLR RG,M` | clear bit M | none |
| C | `0000 1100` | `BTG RG,M` | toggle bit M | none |
| D | `0000 1101` | `RRC RY` | rotate right through C | Z C |
| E | `0000 1110` | `RET R0,#N` | R0 <- N; pop PC from stack | none |
| F | `0000 1111` | `SKIP F,M` | if F true, skip M words | none |

`RG` is encoded as two bits `G` in bits 3..2 of the operand nibble:

| G | Hardware register | Notes |
|---|---|---|
| 0 | R0 | |
| 1 | R1 | |
| 2 | R2 | |
| 3 | I/O port | `IN`/`INB` for `BIT` (source); `OUT`/`OUTB` for `BSET`/`BCLR`/`BTG` (destination) |

The assembler maps `RS` **and** `R3` to G=3. On hardware G=3 selects an
I/O port, not R3: `BIT R3,n` reads an input bit, while `BSET R3,n`,
`BCLR R3,n`, and `BTG R3,n` modify an output bit. This matches the vendor examples
(`BIT R3` = "in" register; `BTG R3` = GPIO output). Do not use these forms to
touch R3; use another register or an explicit `MOV`/`AND`/`OR` sequence. The
manual's prose sometimes calls the G=3 register `IN` even for the write forms;
the examples and addresses `0x0A`/`0xFA` show that the write forms target `OUT`.
(See [upstream-errata.md](upstream-errata.md).)

`BIT` sets `Z=1` when the tested bit is **zero**, and `Z=0` when it is one.

## Flags

| Instruction(s) | C | Z | V |
|---|---|---|---|
| `ADD`, `ADC` | 1 on unsigned carry out | 1 if result = 0 | 1 on signed overflow |
| `SUB`, `SBB` | 1 = no borrow; 0 = borrow | 1 if result = 0 | 1 on signed overflow |
| `OR`/`AND`/`XOR RX,RY` | unchanged | 1 if result = 0 | unchanged |
| `OR R0,#N` | forced to 1 | 1 if result = 0 | unchanged |
| `AND R0,#N` | forced to 0 | 1 if result = 0 | unchanged |
| `XOR R0,#N` | toggled | 1 if result = 0 | unchanged |
| `CP R0,#N` | 1 if R0 >= N | 1 if R0 = N | unchanged (body text; summary table lists V) |
| `INC` | 1 only when 15 -> 0 | 1 if result = 0 | unchanged |
| `DEC` | 0 only when 0 -> 15; else 1 | 1 if result = 0 | unchanged |
| `DSZ` | unchanged | unchanged | unchanged |
| `BIT` | unchanged | 1 if bit = 0 | unchanged |
| `RRC` | old bit 0 | 1 if result = 0 | unchanged |
| `MOV`, `EXR`, `BSET`, `BCLR`, `BTG`, `RET`, `SKIP` | unchanged | unchanged | unchanged |

Notes:

* After `CP R0,N`: `C=1` means `R0 >= N`, `Z=1` means `R0 == N`.
  To branch on "less than", test `NC`.
* `SUB` borrow is inverse carry, so `C=0` means borrow. The manual names this
  "Borrow" but keeps the bit as inverse carry.
* `SBB RX,RY` performs `RX - RY - C` exactly as documented. Because `C` is
  inverse borrow after `SUB`, chaining `SUB` then `SBB` is not a normal
  multi-nibble borrow chain without adjustment.
* `INC`/`DEC` use `C` as a wrap indicator, not as a general carry.

## Pseudo-ops and assembler-generated sequences

| Directive / pseudo-op | Words | Generated code / meaning |
|---|---|---|
| `label:` | 0 | Symbol = current word address. Leading `.` makes a local label. |
| `name EQU expr` | 0 | Constant expression; supports `+`, `-`, `HIGH`, `MID`, `LOW`. |
| `ORG addr` | variable | Pad with `0x000` (`CP R0,0`) until word `addr`; cannot move backwards. |
| `GOTO addr` | 2 | `MOV PC,[HIGH:MID]`; `MOV PCL,LOW` |
| `GOSUB addr` | 2 | `MOV PC,[HIGH:MID]`; `MOV JSR,LOW` (push return address) |
| `BYTE expr` | 2 | `RET R0,expr&0xF`; `RET R0,expr>>4` (low nibble first) |
| `NIBBLE expr` | 1 | `RET R0,expr` (one table nibble) |
| `ASCII "text"` | 2/char | `RET R0,char&0xF`; `RET R0,char>>4` (low nibble first) |
| `NOP` | 1 | `MOV R0,R0` |
| `CPL R0` | 1 | `XOR R0,#15` |
| `CPL RX,RY` | 2 | `MOV RX,#15`; `SUB RX,RY` |
| `NEG RX,RY` | 2 | `MOV RX,#0`; `SUB RX,RY` |
| `LSR RY` | 2 | `ADD R0,#0` (clear C); `RRC RY` |
| `SL RX,RY` | 2 | `MOV RX,RY`; `ADD RX,RY` |
| `RLC RX,RY` | 2 | `MOV RX,RY`; `ADC RX,RY` |

`ASCII` accepts only the printable set documented in the assembler README. A
semicolon cannot appear in the string because it starts a comment. `BYTE` takes
`0..255`; `NIBBLE` and 4-bit immediates take `0..15`.

> **Assembler label bug:** the upstream assembler's first pass counts a
> `BYTE` or `ASCII` directive as **one** word when resolving a later label,
> even though the second pass emits **two** words. A label placed after
> `BYTE`/`ASCII` data therefore resolves one word too low per directive.
> BadgeC avoids the bug by emitting flash bytes as pairs of `NIBBLE`
> directives. If you hand-write tables and use labels after `BYTE`, either
> switch to `NIBBLE` or calculate the address explicitly.

Do not execute into `ORG` padding: the fill word `0x000` is `CP R0,0`, not a
harmless NOP. It updates `C` and `Z`.

## Code-generation notes

### Relative jumps

`JR NN` adds the signed 8-bit `NN` to the **already-incremented** PC. The range is
`-128..+127`, and the target is:

```
target = address_of_JR + 1 + NN
```

`JR -1` (`0xFFF`) is an infinite self-loop. `JR 0` falls through to the next
instruction. Page crossing wraps modulo 4096, so the code space is a ring.

The assembler resolves `JR label` as `label - current_word - 1`, which matches the
hardware. Its range check has an off-by-one: it accepts `-128..126`, not `+127`.

### `SKIP`

`SKIP F,M` only skips **forward**, 1 to 4 words. `M=0` encodes a skip of 4:

| M field | Words skipped |
|---|---|
| `00` | 4 |
| `01` | 1 |
| `10` | 2 |
| `11` | 3 |

The condition is evaluated against the flags at the time of the `SKIP`; `SKIP`
does not modify flags. `SKIP` cannot be used as a backward branch. The assembler
accepts label operands only when the resolved count is `1..4`; a label for the
immediately following instruction resolves to 0 and is rejected because 0 means 4.

`SKIP` counts **words**, not source lines or pseudo-ops. `GOTO` and `GOSUB` are
two words, so `SKIP cond,1` before a `GOTO` skips only its first word and executes
the second (the `MOV PCL`/`MOV JSR`). Use a single-word `JR` for conditional
branches, or branch around the whole two-word sequence with an explicit
`SKIP cond,2`. `DSZ` also skips one word, so it has the same hazard; do not place
a two-word pseudo-op immediately after `DSZ` if you expect it to be skipped as a
unit.

Aliases: `GTE` = `C`, `LT` = `NC`, `EQ` = `Z`, `NE` = `NZ`.

### Calls, jumps and the hardware stack

* `GOTO` and `GOSUB` are two-word sequences. They can reach any of the 4096 code
  words, but both clobber `PCM` and `PCH` (`0x0E`, `0x0F`).
* `GOSUB` writes the low target nibble to `JSR` (`0x0C`). That write pushes the
  12-bit return address onto the hardware stack and jumps.
* `RET R0,#N` loads R0 with `N` and pops the return address. There is no
  `RET` without an immediate and no `PUSH`/`POP`.
* The stack has 5 levels. Return addresses live at `0x10 + 3*SP`, low nibble
  first. A sixth nested call is a fatal stack overflow (SP indicator blinks
  `110`); an extra `RET` is a fatal underflow (`111`). Both halt the program.
* Only `MOV RX,RY`, `MOV RX,#N`, `INC RY` and `DEC RY` trigger a call/jump when
  their destination is `JSR`/`PCL`. Other writes, such as `MOV [0x0C],R0` or
  `MOV [0x0D],R0` (absolute stores to JSR/PCL), are plain memory writes and do
  not branch.
* `MOV PC,#NN` only loads `PCM`/`PCH`; it does not jump.

### R0-only memory access

All data-memory accesses go through R0:

```
MOV [NN],R0      ; store R0 to absolute data address NN
MOV R0,[NN]      ; load R0 from absolute data address NN
MOV [XY],R0      ; store R0 to address (RX << 4) | RY
MOV R0,[XY]      ; load R0 from address (RX << 4) | RY
```

There is no `MOV [NN],RY` or `MOV RY,[NN]`. A compiler must move the value into
R0 first, or move a loaded value out of R0. For a pointer held low/high in
`R6:R7`, the indirect address is written `[R7:R6]` because X is the high nibble
and Y is the low nibble.

### Arithmetic and shifts

* No multiply or divide instruction. Use repeated add/subtract or shift-add
  routines. `ADD RX,RX` is a left shift; `ADC RX,RX` is a left rotate through
  carry.
* `RRC` is the only single-instruction shift. There is no `RLC`; use
  `ADC RX,RX` (or the assembler `RLC` pseudo-op).
* All arithmetic is 4-bit. Multi-nibble values must be handled as nibble arrays
  with explicit carry/borrow logic.
* `EXR N` swaps `R0..R(N-1)` with `0xE0..0xE(N-1)`; `N=0` means all 16. This is
  the only block move and it is a swap, not a copy. With `N>10` it also swaps the
  fixed registers (`OUT`/`IN` or R10/R11, and `JSR`/`PCL`/`PCM`/`PCH`). `EXR` is
  not one of the instructions that triggers a call/jump, so it changes those
  stored target registers without branching; use `N<=10` unless that is intended.

### Program memory is not writable

`MOV [NN],R0` addresses data memory only. There is no instruction that stores to
code memory at runtime, so self-modifying code and run-time patching are not
possible. Constants and lookup tables must be built at assembly/link time.

### Timing

One instruction is executed per clock. Clock speed is selected by SFR `Clock`
(`0xF1`), from about 0.5 Hz to about 250 kHz. At the fastest setting the badge is
roughly 0.25 MIPS, and the exact rate depends on the instruction mix. There are
no interrupts or cycle-count guarantees beyond "one instruction per clock".

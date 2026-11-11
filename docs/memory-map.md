# Voja4 Memory Map

The Voja4 has two separate address spaces: a 256-nibble data space and a
4096-word code space. Neither is byte-addressed from the CPU's point of view.
Sources: the upstream
[User Manual](https://github.com/Hack-a-Day/2022-Supercon6-Badge-Tools/blob/main/manuals/1.User_Manual_v4.pdf)
(programmer's model, pp. 18-20),
[SFR manual](https://github.com/Hack-a-Day/2022-Supercon6-Badge-Tools/blob/main/manuals/3.Special_Function_Registers_v4a.pdf),
and
[Instruction Set](https://github.com/Hack-a-Day/2022-Supercon6-Badge-Tools/blob/main/manuals/2.Instruction_Set_v4.pdf).

## Data memory (`0x00`-`0xFF`)

Data memory is 256 x 4 bits, organized as 16 pages of 16 nibbles. It cannot be
expanded.

| Range | Size | Use |
|---|---:|---|
| `0x00`-`0x0F` | 16 | Page 0: R0-R9 and the fixed registers/SFRs |
| `0x10`-`0x1E` | 15 | Hardware subroutine stack, 5 return addresses x 3 nibbles |
| `0x1F` | 1 | Free; always available as RAM (not part of the stack) |
| `0x20`-`0xEF` | 208 | General-purpose data RAM (`0xE0`-`0xEF` also the EXR alternate bank) |
| `0xF0`-`0xFF` | 16 | Page 15: control/status SFRs |

`0x20`-`0xEF` is the general RAM area: **208 nibbles**. Note that
`0xE0`-`0xEF` is the alternate register set used by `EXR N`; those 16 nibbles are
still addressable, but `EXR` will overwrite them.

### Page 0: registers and fixed SFRs

| Addr | Name | Meaning |
|---:|---|---|
| `0x00` | `R0` | Accumulator; the only register usable for data-memory loads/stores |
| `0x01` | `R1` | General purpose |
| `0x02` | `R2` | General purpose |
| `0x03` | `R3` | General purpose |
| `0x04` | `R4` | General purpose |
| `0x05` | `R5` | General purpose |
| `0x06` | `R6` | General purpose |
| `0x07` | `R7` | General purpose |
| `0x08` | `R8` | General purpose |
| `0x09` | `R9` | General purpose |
| `0x0A` | `OUT` / `R10` | Output latch when `IOPos=0`; R10 when `IOPos=1` |
| `0x0B` | `IN` / `R11` | Input port when `IOPos=0`; R11 when `IOPos=1` |
| `0x0C` | `JSR` | Low nibble of a subroutine target; a write triggers the call |
| `0x0D` | `PCL` | Low nibble of a jump target; a write triggers the jump |
| `0x0E` | `PCM` | Middle PC nibble/bits 7..4 |
| `0x0F` | `PCH` | High PC nibble/bits 11..8 |

`IOPos` is `WrFlags` bit 1. Setting it moves the output/input latches to
`0xFA`/`0xFB` and frees R10/R11 as general registers; the `OUT`/`IN` names at
`0x0A`/`0x0B` then refer to R10/R11, not the connector.

Only `MOV RX,RY`, `MOV RX,#N`, `INC RY` and `DEC RY` with `JSR`/`PCL` as the
destination trigger a call/jump. An absolute store such as `MOV [0x0D],R0` writes
the PCL latch without branching.

### Hardware stack (`0x10`-`0x1E`)

| Item | Value |
|---|---|
| Stack pointer | 3-bit, not readable by the program |
| Depth | 5 levels, at SP 0-4; SP reads 5 when the stack is full |
| Frame size | 3 nibbles |
| Address | `0x10 + 3*SP`, `+1`, `+2` |
| Push order | PC bits 3..0 at base, bits 7..4 at base+1, bits 11..8 at base+2 |
| Overflow | 6th nested call: fatal, SP indicator blinks `110` (`6`) |
| Underflow | `RET` with no frame: fatal, SP indicator blinks `111` (`-1`) |

The stack is cleared to SP=0 on RUN/BREAK. There are no `PUSH`/`POP`
instructions; the only way to push is a write to `JSR`, and the only way to pop
is `RET R0,#N`. `0x1F` is not part of the five frames and is free for data.

One manual sentence says each return address takes "4 nibbles" (User Manual p. 20),
but every diagram and the `RET`/`JSR` descriptions use 3 nibbles, and 5 x 3 = 15,
matching `0x10`-`0x1E`. The 3-nibble model is correct.

### Page 15: special function registers

All are data-memory locations and are accessed with `MOV [NN],R0` /
`MOV R0,[NN]`. Reset values are the documented defaults; RUN clears most state.

| Addr | Name | Bits (3..0) | Reset | Function |
|---:|---|---|---:|---|
| `0xF0` | `Page` | `PAGE[3:0]` | `0000` | Selects the data-memory page shown on the right half of the LED matrix |
| `0xF1` | `Clock` | `CLOCK[3:0]` | `0000` | CPU clock divider index; 0 = fastest (~250 kHz), 15 = 0.5 Hz |
| `0xF2` | `Sync` | `SYNC[3:0]` | `0000` | User-sync divider index; sets the `UserSync` flag rate |
| `0xF3` | `WrFlags` | `LedsOff`, `MatrixOff`, `IOPos`, `RxTxPos` | `0000` | Display and I/O routing control |
| `0xF4` | `RdFlags` | reserved, reserved, `Vflag`, `UserSync` | `0000` | Status flags; reading clears `UserSync` |
| `0xF5` | `SerCtrl` | `Error`, `Baud[2:0]` | `0011` | UART error flag and baud rate; reset 9600 |
| `0xF6` | `SerLow` | `SER LOW[3:0]` | `0000` | UART low nibble; read/write have different meanings |
| `0xF7` | `SerHigh` | `SER HIGH[3:0]` | `0000` | UART high nibble; read/write have different meanings |
| `0xF8` | `Received` | `RECEIVED[3:0]` | `0000` | Number of unread bytes, 0-14, 15 = "15 or more" |
| `0xF9` | `AutoOff` | `AUTO OFF[3:0]` | `0010` | 10-minute down-counter; 0 enters SLEEP |
| `0xFA` | `OutB` | `OUT B[3:0]` | `0000` | Output latch when `IOPos=1`; otherwise general RAM |
| `0xFB` | `InB` | `IN B[3:0]` | `0000` | Input port when `IOPos=1`; otherwise general RAM |
| `0xFC` | `KeyStatus` | `AltPress`, `AnyPress`, `LastPress`, `JustPress` | `0011` | Debounced key status; reading clears `JustPress` |
| `0xFD` | `KeyReg` | `KEY REG[3:0]` | `0000` | Number of the last pressed key (0-13) |
| `0xFE` | `Dimmer` | `DIMMER[3:0]` | `1111` | LED PWM duty; `1111` = 100%, `0000` = lowest |
| `0xFF` | `Random` | `RANDOM[3:0]` | random | 4-bit PRNG output; each read advances the LCG; writing reseeds (`1111` = true random) |

### SFR access from BadgeC

Every page-15 SFR has a typed helper in `lib/`, and `peek`/`poke` can reach
any data address directly when a raw access is needed.

| SFR | Address | Public BadgeC API |
|---|---:|---|
| `Page` | `0xF0` | `display_page`, `display_page_get`, `system_page` |
| `Clock` | `0xF1` | `time_clock_set`, `time_clock_get` |
| `Sync` | `0xF2` | `time_sync_set`, `time_sync_get`, `time_sync_seen`, `time_sync_wait` |
| `WrFlags` | `0xF3` | `system_wr_flags`, `system_wr_flags_set`, `gpio_alt`, `uart_route`, `leds_enable`, `matrix_enable` |
| `RdFlags` | `0xF4` | `system_rd_flags`, `system_vflag`, `system_user_sync` |
| `SerCtrl` | `0xF5` | `uart_init`, `uart_error`, `uart_baud`, `system_ser_ctrl`, `system_uart_error`, `system_uart_baud` |
| `SerLow` / `SerHigh` | `0xF6` / `0xF7` | `uart_putc`, `uart_getc` (use these: the two nibbles have side effects) |
| `Received` | `0xF8` | `uart_available` |
| `AutoOff` | `0xF9` | `power_keep_awake`, `power_auto_off`, `power_auto_off_minutes`, `power_sleep`, `power_remaining` |
| `OutB` / `InB` | `0xFA` / `0xFB` | `gpio_read`, `gpio_write`, `gpio_alt` |
| `KeyStatus` | `0xFC` | `key_status`, `key_any`, `key_alt`, `key_just`, `key_last` and the `*_of` forms |
| `KeyReg` | `0xFD` | `key_code`, `key_down`, `key_wait`, `key_wait_any`, `key_wait_release`, `key_name` |
| `Dimmer` | `0xFE` | `dimmer`, `dimmer_get`, `system_dimmer` |
| `Random` | `0xFF` | `random`, `seed`, `rand_seed`, `rand_byte`, `rand_word`, `rand_below`, `rand_range`, `rand_true` |

Page 0's fixed registers are different: `OUT`/`IN` at `0x0A`/`0x0B` are
reached through `out()`, `in()`, `gpio_read`, and `gpio_write`; `JSR`, `PCL`,
`PCM`, and `PCH` are driven by calls, jumps, and returns rather than by a
typed API. Inline assembly can access them when needed.

#### `WrFlags` (`0xF3`)

| Bit | Name | 0 | 1 |
|---:|---|---|---|
| 3 | `LedsOff` | ALU panel LEDs enabled | ALU panel LEDs off (CLK/nCLK stay on) |
| 2 | `MatrixOff` | LED matrix enabled | LED matrix off |
| 1 | `IOPos` | `OUT`/`IN` at `0x0A`/`0x0B` | `OutB`/`InB` at `0xFA`/`0xFB`; R10/R11 free |
| 0 | `RxTxPos` | UART on SAO connector | UART on main I/O connector; SAO Rx inactive |

`WrFlags` is reset to 0 on every RUN and BREAK. Program load/save and the
firmware bootloader ignore `RxTxPos` and always use the main I/O connector.

#### `RdFlags` (`0xF4`)

| Bit | Name | Meaning |
|---:|---|---|
| 3-2 | reserved | Read as 0 |
| 1 | `Vflag` | Copy of the signed-overflow flag from the adder |
| 0 | `UserSync` | Set by the `Sync` divider; cleared automatically when `RdFlags` is read |

#### `KeyStatus` (`0xFC`)

| Bit | Name | Meaning |
|---:|---|---|
| 3 | `AltPress` | ALT is pressed (debounced, 5 ms) |
| 2 | `AnyPress` | Any key except ALT/ON-OFF is pressed |
| 1 | `LastPress` | The key named in `KeyReg` is currently pressed |
| 0 | `JustPress` | A key was pressed since the last read; read clears it |

The matrix is 16 rows x 8 columns, arranged as two 16x4 pages side by side, so two pages (32 nibbles) are visible at once:

```
             Page+1 (left half)              Page (right half)
        bit 3 2 1 0 (one nibble per row)   bit 3 2 1 0
addr (Page+1)*16 + 0  -> top row           addr Page*16 + 0  -> top row
addr (Page+1)*16 + 15 -> bottom row        addr Page*16 + 15 -> bottom row
```

The selected page is on the right, `Page+1` on the left. If `Page=15`, the left
half wraps to page 0, which lets you watch page 0 and the SFR page together. Bit 3
is the left column of a nibble, bit 0 the right column. `Page` resets to 0 on RUN.
In SS mode, ALT forces pages 0 and 1 to be displayed.

### Reset/default state at RUN

RUN/BREAK clears the whole data memory and resets most control state:

| Item | Value at RUN |
|---|---|
| Data memory | all zeros |
| Stack pointer | 0 |
| `Page` | 0 |
| `Clock` | 0 (fastest) |
| `Sync` | 0 |
| `WrFlags` | 0 |
| `Dimmer` | `1111` (maximum) |
| `SerCtrl` | `0011` (9600 baud) |
| `AutoOff` | `0010` |
| PC | `0x000` |

This means `.bss` is zero-initialized for free on the first RUN, and `Clock`,
`Page`, etc. do not retain values from a previous run.

## Code memory (`0x000`-`0xFFF`)

| Item | Value |
|---|---|
| Size | 4096 words x 12 bits |
| Address range | `0x000`-`0xFFF` |
| PC width | 12 bits |
| Reset/run entry | `0x000` |
| Interrupt vectors | none |
| Writable at run time | no |
| Addressing | absolute 12-bit via `PCL`/`PCM`/`PCH`; no banking |

The program loader loads a `.hex` image sequentially starting at word 0; the file
format has no per-record address. `ORG` only inserts padding so a later word lands
at a chosen address. The assembler's fill value is `0x000` (`CP R0,0`), not a NOP.

Because code and data are separate, a 12-bit value is not a data pointer and an
8-bit data address is not a code address. See [runtime-abi.md](runtime-abi.md) for
the compiler's pointer conventions.

## SFR aliases and documentation errata

* The "Special Function Registers on Page 0" table on page 3 of the SFR manual
  lists `0xF0`-`0xFF` as `R0`-`R9`, `Out/In`, `JSR`, `PCL`, `PCM`, `PCH`. That is
  not the implemented page-15 map and conflicts with the User Manual programmer's
  model. The implemented map is the one above.
* The SFR manual's `SerCtrl` section says the error bit is cleared by reading
  `RdFlags`; it should say reading `SerCtrl` clears its own error bit.
* `Received` has reset `0000` in the SFR summary table but `0011` in its detailed
  page. Treat it as zero at RUN; test it before reading a byte regardless.
* The User Manual also uses `0x12`/`0x13`/`0x14`/`0x15` for `JSR`/`PCL`/`PCM`/`PCH`
  in one paragraph (p. 20). The correct page-0 addresses are `0x0C`-`0x0F`;
  `0x10`-`0x1F` is the stack.

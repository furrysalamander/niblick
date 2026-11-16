# Serial / UART

The badge has one UART, built into the PIC firmware and exposed through four
memory-mapped nibbles plus a control/status register. The same UART is used for
application I/O and for program save/load. The firmware bootloader is a separate
path with different rules.

Sources: the upstream
[SFR manual](https://github.com/Hack-a-Day/2022-Supercon6-Badge-Tools/blob/main/manuals/3.Special_Function_Registers_v4a.pdf)
(SFR F5-F8), the
[User Manual](https://github.com/Hack-a-Day/2022-Supercon6-Badge-Tools/blob/main/manuals/1.User_Manual_v4.pdf)
(DIR mode, pp. 22-24), the upstream
[assembler README](https://github.com/Hack-a-Day/2022-Supercon6-Badge-Tools/blob/main/assembler/README.md),
and the upstream
[firmware README](https://github.com/Hack-a-Day/2022-Supercon6-Badge-Tools/blob/main/firmware/README.md).

## Register summary

| Addr | Name | Access | Purpose |
|---:|---|---|---|
| `0xF5` | `SerCtrl` | R/W | bit 3 = error; bits 2..0 = baud index |
| `0xF6` | `SerLow` | R/W (split) | low nibble of the byte; **writing starts TX**; reading pops RX |
| `0xF7` | `SerHigh` | R/W (split) | high nibble of the byte |
| `0xF8` | `Received` | R | unread-byte count, 0-14, 15 = "15 or more" |
| `0xF3` | `WrFlags` | R/W | bit 0 `RxTxPos` selects SAO vs main I/O header |

`SerLow` and `SerHigh` are each a pair of registers at the same address: one
read-only (RX) and one write-only (TX). A read returns the RX side; a write loads
the TX side.

## Byte format: two nibbles

Every 8-bit byte is transferred as two 4-bit halves. The low nibble is bits 3..0
and the high nibble is bits 7..4:

```
byte = (high_nibble << 4) | low_nibble
```

Example: ASCII `'A'` = `0x41` => high = `4`, low = `1`.

### Transmit

Write the **high** nibble first, then the low nibble last:

```
MOV R0, high
MOV [0xF7], R0      ; SerHigh, no transmission yet
MOV R0, low
MOV [0xF6], R0      ; SerLow, byte is transmitted now
```

Writing `SerLow` is the transmit trigger. Writing `SerHigh` alone leaves the byte
pending. The manual says the processor waits if the transmitter is not ready, so a
`SerLow` write can stall the CPU for up to one character time. No public
"TxReady" bit is documented; treat the low-nibble write as potentially blocking.

### Receive

Wait until `Received` is nonzero, then read the **high** nibble first and the
**low** nibble last:

```
wait:
    MOV R0, [0xF8]      ; Received
    CP R0, 0
    SKIP nz, 1          ; Received != 0: skip the one-word JR
    JR wait             ; still empty: loop (JR is a single word)
    MOV R0, [0xF7]      ; SerHigh (does not advance FIFO)
    MOV R1, R0          ; save high
    MOV R0, [0xF6]      ; SerLow: pops next byte, decrements Received
    MOV R2, R0          ; low
```

Reading `SerLow` is the handshake: it advances the FIFO and decrements `Received`.
Reading `SerHigh` does not advance. If you read the low nibble first, the high
nibble of that byte is lost.

### FIFO and errors

| Item | Value |
|---|---|
| FIFO | 256 bytes |
| Holding pair | 1 byte (`SerHigh`/`SerLow`) |
| Total unread capacity | 257 bytes |
| `Received` encoding | 0-14 exact, 15 means 15 or more |
| Overflow | new bytes dropped; `SerCtrl` bit 3 set |

`Received` is read-only in practice. The program must never write it. It is
incremented when a byte is moved from the UART into the FIFO, and decremented when
`SerLow` is read.

`SerCtrl` bit 3 is a sticky error flag (overrun/framing/FIFO). Reading `SerCtrl`
clears it; the SFR manual's remark that `RdFlags` clears it is a typo.

## Baud rate

`SerCtrl` bits 2..0 select the application UART baud rate:

| Index | Baud | Notes |
|---:|---:|---|
| 0 | 1200 | |
| 1 | 2400 | |
| 2 | 4800 | |
| 3 | 9600 | reset default (`SerCtrl = 0011`) |
| 4 | 19200 | |
| 5 | 38600 | manual prints 38600; almost certainly 38400 |
| 6 | 57600 | |
| 7 | 115200 | |

The baud rate is **ignored** for DIR-mode program SAVE/LOAD and for the firmware
bootloader: those always use **9600, N, 8, 1**.

## Pin routing and wiring

`WrFlags` bit 0 (`RxTxPos`) selects where the application UART appears:

| `RxTxPos` | TX / RX location |
|---:|---|
| 0 (reset) | SAO connector (`Rx` and `Tx`; +3V and GND also present) |
| 1 | Main I/O connector, pins 2 and 3 from the left; SAO `Rx` inactive, SAO `Tx` still driven |

`RxTxPos` is cleared on every RUN/BREAK. Program SAVE/LOAD and the firmware
bootloader use the **main I/O connector regardless of `RxTxPos`**; the SAO UART
cannot be used to load or save programs.

Electrical notes:

* 3 V CMOS logic, not RS-232 and not 5 V tolerant.
* Common ground is required.
* Cross the data lines: adapter TX -> badge RX, adapter RX -> badge TX.
* Do **not** connect the adapter's +/VCC to the badge's +3V while the badge is
  battery-powered. The manual explicitly warns against paralleling two supplies.
* There is no hardware flow control (no RTS/CTS), and the badge does not report
  whether a listener is present.

### Tigard / USB-UART notes

A Tigard (or any 3.3 V USB-UART) works for both application serial and program
load/save if wired correctly:

1. Set the Tigard I/O supply to **3.3 V**, not 5 V.
2. Connect Tigard GND to badge GND.
3. Connect Tigard TX to badge RX and Tigard RX to badge TX.
4. Leave Tigard VCC/+ disconnected unless you have removed the
   badge batteries and are powering the badge from a known-good 3.3 V source.
5. For program load/save and firmware bootload, use the **main I/O connector**
   (pins 2/3 from the left), not the SAO header.
6. Use 9600 8N1 for load/save/bootload. For application UART, set `SerCtrl` to
   the desired rate and use 8N1.

Caveats:

* A 5 V FTDI cable will drive the badge out of spec. Use a 3.3 V setting or a
  level shifter.
* The badge's TX idles high through a pull-up; some adapters need a pull-up or
  will show a floating line before the program configures the pin.
* On Linux, put the port in raw mode before `cat`, for example:
  `stty -F /dev/ttyUSB0 raw 9600`.
* macOS `cat` has been reported not to work reliably for this; use a terminal
  program such as CoolTerm.
* A Tigard has two UART channels and therefore two `/dev/ttyUSB*` devices.
  Only one channel is connected to the badge. Use that channel consistently;
  do not send the same program to both, and do not assume `ttyUSB1` is spare.
* Program load waits for a valid header, so sender/LOAD timing matters. A
  one-shot send that finishes before LOAD is pressed does nothing; retrying the
  file is the simplest robust fix. Appending about 1 KiB of NUL bytes helps
  flush adapters that buffer the tail.
* After a successful LOAD the badge remains in DIR mode and the matrix stays
  blank. Switch to RUN and press RUN to execute the program.
* The badge cannot tell whether the host is ready. SAVE starts transmitting
  immediately; start the capture first, then press SAVE.
* The Nov. 2022 tutorial reports a firmware bug in the application UART on the
  main expansion header (SAO worked). That note concerns application I/O;
  program load/save follows the separate loader path. Update the badge firmware
  if `RxTxPos=1` application UART misbehaves.

## DIR-mode program SAVE/LOAD protocol

The program container is the assembler's `.hex` format. It is **not** Intel HEX.
The loader always starts at code word 0; there is no address field.

| Field | Size | Meaning |
|---|---:|---|
| Header | 6 bytes | `00 FF 00 FF A5 C3` |
| Length | 2 bytes | number of 12-bit words, little-endian |
| Program | 2 x length bytes | each word little-endian, upper nibble zero |
| Checksum | 2 bytes | 16-bit sum of length field + program words, little-endian |

Checksum is modulo 65536. The 16-bit word for a 12-bit instruction has bits 15..12
= 0. Example: `MOV R9,7` = `0x907` is stored as bytes `07 09`.

### Load a program (host -> badge)

1. Put the badge in DIR mode.
2. Prepare the host to send the `.hex` file at 9600 8N1 raw.
3. Press **LOAD** on the badge.
4. Send the file, e.g. `cat program.hex > /dev/ttyUSB0`.
5. The LOAD bargraph runs; the badge ignores data until it sees a valid header.
   If no valid header arrives, existing program memory is not destroyed.

### Save a program (badge -> host)

1. Put the badge in DIR mode.
2. Start the capture first: `cat /dev/ttyUSB0 > out.hex`.
3. Press **SAVE** on the badge.
4. Stop the capture after the transfer (Ctrl-C). The file is the same container.

The badge sends immediately even with no listener. The SAVE indicator blinks and
nothing is sent if program memory is empty.

### Internal flash slots

ALT+SAVE / ALT+LOAD use the badge's internal flash instead of serial. There are 15
usable program slots; slot 15 is reserved as the automatic backup used before an
ALT+LOAD. Selecting slot 15 for ALT+SAVE is ignored. An ALT+LOAD first copies the
current program memory to slot 15, so two unintentional ALT+LOADs can destroy the
backup. See the User Manual pp. 23-24.

### Firmware bootloader (different from program LOAD)

Firmware updates use the bootloader, not the DIR-mode program loader:

1. Hold **ALT + LOAD** while grounding the **RES** pin (far right of the main
   header), then release.
2. The LOAD LED blinks slowly; start sending the firmware image at 9600 8N1 raw.
3. It blinks fast while receiving; after roughly 20-30 s both SAVE and LOAD turn
   on solid.
4. Press **MODE** to see the version/checksum; MODE again to exit.

The upstream firmware image `firmware/Badge_v99r3.bin` is a raw firmware binary, not
a program `.hex`; do not send a program `.hex` to the firmware bootloader. Only the
main I/O connector's RX pin is active in bootload mode; TX has no effect.

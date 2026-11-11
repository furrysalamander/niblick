# Upstream documentation errata

These contradictions were found while writing `isa.md`, `memory-map.md`,
`serial.md`, `toolchain.md`, and `runtime-abi.md`. The implementation and the
more detailed sections usually agree with each other; the errors are in summary
tables, prose, or the assembler.

The source documents are in the
[Hack-a-Day Supercon.6 badge tools](https://github.com/Hack-a-Day/2022-Supercon6-Badge-Tools)
repository under `manuals/` and `tutorial/`.

| # | Source | Problem | Resolution used in these docs |
|---:|---|---|---|
| 1 | User Manual p. 20 | Says each return address takes 12 bits "(4 nibbles)". | 12 bits = **3 nibbles**; p. 15/18 and the RET/JSR diagrams use 3. Five frames occupy `0x10`-`0x1E`. |
| 2 | User Manual p. 20 | Gives `JSR`/`PCL`/`PCM`/`PCH` as `0x12`-`0x15`. | Correct page-0 addresses are **`0x0C`-`0x0F`** (p. 18 map and SFR manual). |
| 3 | SFR manual p. 3 | "Special Function Registers on Page 0" lists `0xF0`-`0xFF` as `R0`-`R9`, `Out/In`, `JSR`, `PCL`, `PCM`, `PCH`. | Actual page 15 is `Page`, `Clock`, `Sync`, `WrFlags`, `RdFlags`, `SerCtrl`, `SerLow`, `SerHigh`, `Received`, `AutoOff`, `OutB`, `InB`, `KeyStatus`, `KeyReg`, `Dimmer`, `Random`. |
| 4 | Instruction Set pp. 2, 18-19 | Text calls the `JR` opcode `1010` and the `SKIP` example opcode `0000 1101`; the encoding diagrams show `1111`. | `JR` = `1111 NNNN NNNN`; `SKIP` = `0000 1111 FFMM`. |
| 5 | Instruction Set pp. 29-36; assembler | `BIT/BSET/BCLR/BTG` operands say `RG ∈ R0,R1,R2,RS`; the assembler accepts `R3` and `RS` and encodes both as `G=3`. The prose calls G=3 `IN`, but the write examples modify `0xFA` (`OUTB`). | `G=3` is an I/O port, not R3: `BIT` reads `IN`/`INB`, while `BSET`/`BCLR`/`BTG` write `OUT`/`OUTB`. Vendor examples confirm (`BIT R3` = input, `BTG R3` = GPIO output). |
| 6 | Instruction Set p. 2 vs pp. 20/31 | Summary table lists `V` as affected by `CP`; body says only `C`/`Z` are updated. | `CP` updates C and Z; V is unchanged. |
| 7 | SFR manual p. 16 | Says the `SerCtrl` error bit is reset by reading `RdFlags`. | Reading **`SerCtrl`** clears its error bit. |
| 8 | SFR manual p. 10 vs p. 19 | `Received` reset is `0000` in the summary table and `0011` in the detailed page. | Treat as 0 at RUN; always test `Received > 0` before reading. |
| 9 | SFR manual p. 16 | Baud index 5 is printed as **38600**. | Almost certainly **38400**; the rest of the table is standard. |
| 10 | SFR manual pp. 17-18 | Prose says "read the high nibble (SerHigh-w) first" and "read the high nibble ... first"; one parenthetical uses the write-side name. | RX order is `SerHigh`-read first, `SerLow`-read last. |
| 11 | User Manual pp. 22, 34 | Bootload section refers to "SFR 0xF3 (SerCtrl)". | `0xF3` is `WrFlags`; `SerCtrl` is **`0xF5`**. Bootload ignores both and is fixed at 9600. |
| 12 | Tutorial `2.Flow.md` | Comment says `skip c,1` skips "if R0 < 5"; after `CP R0,5`, `C=1` means `R0 >= 5`. | `SKIP c` means carry set (`R0 >= N`); use `SKIP nc` for less-than. The narrative and result match `>=`. |
| 13 | Emulator README vs source | README says Python 3.6+, `bvm.py` says 3.10+; README says input `.bin`, but `badge.py` parses the assembler `.hex` container. | Use Python 3.10+ and pass the `.hex` container. |
| 14 | Assembler source | `JR` range check rejects `+127` although hardware allows `-128..+127`. | Treat `+127` as unsupported by this assembler revision; use a nearby branch or `GOTO` if needed. |
| 15 | Instruction Set pp. 4, 7 | `ADC` and `SBB` flag prose is copied from `SUB` and says "underflow ... reset C". The ADC example correctly shows `C=1` on carry-out. | `ADC` uses C as carry-in/carry-out; `SBB` uses C as the subtract-with-borrow input. Ignore the copied "underflow" sentence. |
| 16 | User Manual p. 17 | Says the default `R10`/`R11` are at `0xFA`/`0xFB` on page 0. | `0x0A`/`0x0B` are `OUT`/`IN` when `IOPos=0`, and become `R10`/`R11` when `IOPos=1`; `0xFA`/`0xFB` are `OutB`/`InB` only when `IOPos=1`. |

Errata 1-2 are internally contradicted by the same manual's diagrams and
programmer's model. Errata 3 is the most consequential: following the page-3
table would make all page-15 SFR access wrong. The map in
[memory-map.md](memory-map.md) follows the detailed SFR pages and the User
Manual programmer's model.

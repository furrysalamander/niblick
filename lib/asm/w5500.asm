; W5500 socket 0 TX write pointer.
;
; This is a library routine rather than part of the compiler runtime.  The
; BadgeC declaration is:
;
;     extern fn word w5500_tx_pointer();
;
; Result: R1..R4 = 16-bit Sn_TX_WR, low nibble first.
; Clobbers R0..R9 and flags, per the BadgeC calling convention.

fn_w5500_tx_pointer:
    BCLR R3, 1
    MOV R1, 0
    MOV R2, 0
    GOSUB __bc_spi_xfer_fast
    MOV R1, 4
    MOV R2, 2
    GOSUB __bc_spi_xfer_fast
    MOV R1, 8
    MOV R2, 0
    GOSUB __bc_spi_xfer_fast
    MOV R1, 0
    MOV R2, 0
    GOSUB __bc_spi_xfer_fast
    MOV R8, R1
    MOV R9, R2
    BSET R3, 1
    BCLR R3, 1
    MOV R1, 0
    MOV R2, 0
    GOSUB __bc_spi_xfer_fast
    MOV R1, 5
    MOV R2, 2
    GOSUB __bc_spi_xfer_fast
    MOV R1, 8
    MOV R2, 0
    GOSUB __bc_spi_xfer_fast
    MOV R1, 0
    MOV R2, 0
    GOSUB __bc_spi_xfer_fast
    BSET R3, 1
    MOV R3, R8
    MOV R4, R9
    RET R0, 0

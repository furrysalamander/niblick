; W5500 socket 0 TX write pointer.
;
; This is a library routine rather than part of the compiler runtime.  The
; Niblick declaration is:
;
;     extern fn word w5500_tx_pointer();
;
; Result: R1..R4 = 16-bit Sn_TX_WR, low nibble first.
; Clobbers R0..R9 and flags, per the Niblick calling convention.

fn_w5500_tx_pointer:
    BCLR R3, 1
    MOV R1, 0
    MOV R2, 0
    GOSUB __nib_w5500_spi_xfer_fast
    MOV R1, 4
    MOV R2, 2
    GOSUB __nib_w5500_spi_xfer_fast
    MOV R1, 8
    MOV R2, 0
    GOSUB __nib_w5500_spi_xfer_fast
    MOV R1, 0
    MOV R2, 0
    GOSUB __nib_w5500_spi_xfer_fast
    MOV R8, R1
    MOV R9, R2
    BSET R3, 1
    BCLR R3, 1
    MOV R1, 0
    MOV R2, 0
    GOSUB __nib_w5500_spi_xfer_fast
    MOV R1, 5
    MOV R2, 2
    GOSUB __nib_w5500_spi_xfer_fast
    MOV R1, 8
    MOV R2, 0
    GOSUB __nib_w5500_spi_xfer_fast
    MOV R1, 0
    MOV R2, 0
    GOSUB __nib_w5500_spi_xfer_fast
    BSET R3, 1
    MOV R3, R8
    MOV R4, R9
    RET R0, 0

; char w5500_rx_peek(word offset)
;
; Reads Sn_RX_RD, adds offset, then reads one byte from the socket-0 RX
; buffer.  Reuses the C register helpers so the SPI sequence stays in one
; place.
fn_w5500_rx_peek:
    ; Read Sn_RX_RD high byte (0x28).
    MOV R0, 1
    MOV [${w5500_read.bsb}], R0
    MOV R0, 0
    MOV [${w5500_read.addr_hi}], R0
    MOV [${w5500_read.addr_hi+1}], R0
    MOV R0, 8
    MOV [${w5500_read.addr_lo}], R0
    MOV R0, 2
    MOV [${w5500_read.addr_lo+1}], R0
    GOSUB fn_w5500_read
    MOV R0, R1
    MOV [${w5500_scratch+2}], R0
    MOV R0, R2
    MOV [${w5500_scratch+3}], R0

    ; Read Sn_RX_RD low byte (0x29).
    MOV R0, 9
    MOV [${w5500_read.addr_lo}], R0
    GOSUB fn_w5500_read

    ; Combine RX_RD and add offset.
    MOV R0, [${w5500_scratch+2}]
    MOV R3, R0
    MOV R0, [${w5500_scratch+3}]
    MOV R4, R0
    MOV R0, [${offset}]
    ADD R1, R0
    MOV R0, [${offset+1}]
    ADC R2, R0
    MOV R0, [${offset+2}]
    ADC R3, R0
    MOV R0, [${offset+3}]
    ADC R4, R0

    ; Wrap the pointer inside the 2 KB socket-0 RX buffer.
    MOV R0, R3
    MOV R5, 7
    AND R0, R5
    MOV R3, R0
    MOV R4, 0

    ; Read the byte from the RX buffer (BSB 3).
    MOV R0, 3
    MOV [${w5500_read.bsb}], R0
    MOV R0, R3
    MOV [${w5500_read.addr_hi}], R0
    MOV R0, R4
    MOV [${w5500_read.addr_hi+1}], R0
    MOV R0, R1
    MOV [${w5500_read.addr_lo}], R0
    MOV R0, R2
    MOV [${w5500_read.addr_lo+1}], R0
    GOSUB fn_w5500_read
    RET R0, 0

; void w5500_rx_consume(word count)
;
; Advances Sn_RX_RD by count, issues RECV, and gives the W5500 a settling
; delay.  The intermediate pointer is kept in w5500_scratch because the C
; helpers clobber R0..R9.
fn_w5500_rx_consume:
    ; Read Sn_RX_RD high byte (0x28).
    MOV R0, 1
    MOV [${w5500_read.bsb}], R0
    MOV R0, 0
    MOV [${w5500_read.addr_hi}], R0
    MOV [${w5500_read.addr_hi+1}], R0
    MOV R0, 8
    MOV [${w5500_read.addr_lo}], R0
    MOV R0, 2
    MOV [${w5500_read.addr_lo+1}], R0
    GOSUB fn_w5500_read
    MOV R0, R1
    MOV [${w5500_scratch+2}], R0
    MOV R0, R2
    MOV [${w5500_scratch+3}], R0

    ; Read Sn_RX_RD low byte (0x29).
    MOV R0, 9
    MOV [${w5500_read.addr_lo}], R0
    GOSUB fn_w5500_read

    ; Combine RX_RD and add count.
    MOV R0, [${w5500_scratch+2}]
    MOV R3, R0
    MOV R0, [${w5500_scratch+3}]
    MOV R4, R0
    MOV R0, [${count}]
    ADD R1, R0
    MOV R0, [${count+1}]
    ADC R2, R0
    MOV R0, [${count+2}]
    ADC R3, R0
    MOV R0, [${count+3}]
    ADC R4, R0

    ; Wrap the pointer inside the 2 KB socket-0 RX buffer.
    MOV R0, R3
    MOV R5, 7
    AND R0, R5
    MOV R3, R0
    MOV R4, 0

    ; Keep the new pointer in scratch while the C helper clobbers registers.
    MOV R0, R1
    MOV [${w5500_scratch}], R0
    MOV R0, R2
    MOV [${w5500_scratch+1}], R0
    MOV R0, R3
    MOV [${w5500_scratch+2}], R0
    MOV R0, R4
    MOV [${w5500_scratch+3}], R0

    ; Write Sn_RX_RD high byte (0x28).
    MOV R0, 1
    MOV [${w5500_write.bsb}], R0
    MOV R0, 0
    MOV [${w5500_write.addr_hi}], R0
    MOV [${w5500_write.addr_hi+1}], R0
    MOV R0, 8
    MOV [${w5500_write.addr_lo}], R0
    MOV R0, 2
    MOV [${w5500_write.addr_lo+1}], R0
    MOV R0, [${w5500_scratch+2}]
    MOV [${w5500_write.value}], R0
    MOV R0, [${w5500_scratch+3}]
    MOV [${w5500_write.value+1}], R0
    GOSUB fn_w5500_write

    ; Write Sn_RX_RD low byte (0x29).
    MOV R0, 9
    MOV [${w5500_write.addr_lo}], R0
    MOV R0, [${w5500_scratch}]
    MOV [${w5500_write.value}], R0
    MOV R0, [${w5500_scratch+1}]
    MOV [${w5500_write.value+1}], R0
    GOSUB fn_w5500_write

    ; Sn_CR = RECV (0x40) at 0x0001.
    MOV R0, 0
    MOV [${w5500_write.addr_lo}], R0
    MOV R0, 1
    MOV [${w5500_write.addr_lo+1}], R0
    MOV R0, 0
    MOV [${w5500_write.value}], R0
    MOV R0, 4
    MOV [${w5500_write.value+1}], R0
    GOSUB fn_w5500_write

    GOSUB fn_w5500_delay
    RET R0, 0

fn_w5500_delay:
    MOV R2, 15
.delay_outer:
    MOV R3, 15
.delay_inner:
    DSZ R3
    JR .delay_inner
    DSZ R2
    JR .delay_outer
    RET R0, 0

; BadgeC runtime (hand-written assembly)
;
; ABI
;   nibble    R1
;   char      R1 = low nibble, R2 = high nibble
;   flashptr  R1 = low, R2 = middle, R3 = high
;
; These routines are intentionally kept small and are allowed to clobber
; R0..R9.  The compiler spills live expression values to RAM before calls.

; ---------------------------------------------------------------------------
; UART
; ---------------------------------------------------------------------------

__bc_uart_putc:
    MOV R0, R2
    MOV [0xF7], R0              ; SerHigh first
    MOV R0, R1
    MOV [0xF6], R0              ; writing SerLow starts TX
    RET R0, 0

__bc_uart_getc:
__bc_uart_getc_wait:
    MOV R0, [0xF8]              ; Received
    CP R0, 0
    SKIP NZ, 2
    GOTO __bc_uart_getc_wait
    MOV R0, [0xF7]              ; SerHigh
    MOV R2, R0
    MOV R0, [0xF6]              ; SerLow (pops one byte)
    MOV R1, R0
    RET R0, 0

__bc_flash_read_nibble_ptr:
    MOV PCH, R8
    MOV PCM, R7
    MOV JSR, R6                 ; call table entry; RET R0,n returns here
    MOV R1, R0
    RET R0, 0

; Read a char from a flash table and advance the pointer by two words.
;   in:  R6/R7/R8 = address of low nibble
;   out: R1/R2 = low/high nibble, R6/R7/R8 advanced by 2
__bc_flash_read_char_ptr:
    MOV PCH, R8
    MOV PCM, R7
    MOV JSR, R6
    MOV R5, R0                  ; low nibble

    INC R6
    SKIP NC, 3
    INC R7
    SKIP NC, 1
    INC R8

    MOV PCH, R8
    MOV PCM, R7
    MOV JSR, R6
    MOV R2, R0                  ; high nibble
    MOV R1, R5

    INC R6
    SKIP NC, 3
    INC R7
    SKIP NC, 1
    INC R8
    RET R0, 0

; Public entry points used by the compiler.
__bc_flash_read_char:
    MOV R6, R1
    MOV R7, R2
    MOV R8, R3
    GOSUB __bc_flash_read_char_ptr
    RET R0, 0

__bc_flash_read_nibble:
    MOV R6, R1
    MOV R7, R2
    MOV R8, R3
    GOSUB __bc_flash_read_nibble_ptr
    RET R0, 0

; Write a flash string to the UART.  Stops at 0xFF.
;   in: R1/R2/R3 = flash pointer
__bc_w5500_spi_tx_fast:
    MOV R4, 8
__bc_w5500_spi_tx_fast_loop:
    BIT R2, 3
    SKIP Z, 1
    BSET R3, 3
    BIT R2, 3
    SKIP NZ, 1
    BCLR R3, 3
    BSET R3, 2
    ADD R1, R1
    ADC R2, R2
    BCLR R3, 2
    DSZ R4
    JR __bc_w5500_spi_tx_fast_loop
    RET R0, 0

; Exchange the char in R1:R2, returning MISO in R1:R2.
__bc_w5500_spi_xfer_fast:
    MOV R4, 8
    MOV R6, 0
    MOV R7, 0
__bc_w5500_spi_xfer_fast_loop:
    BIT R2, 3
    SKIP Z, 1
    BSET R3, 3
    BIT R2, 3
    SKIP NZ, 1
    BCLR R3, 3
    BSET R3, 2
    ADD R6, R6
    ADC R7, R7
    BIT R3, 0
    SKIP Z, 1
    INC R6
    ADD R1, R1
    ADC R2, R2
    BCLR R3, 2
    DSZ R4
    JR __bc_w5500_spi_xfer_fast_loop
    MOV R1, R6
    MOV R2, R7
    RET R0, 0

; ---------------------------------------------------------------------------
; GPIO / I/O port
; ---------------------------------------------------------------------------

; Read the 4-bit connector input, honoring WrFlags.IOPos.
__bc_gpio_set:
    MOV R9, R1
    GOSUB __bc_gpio_read_out
    OR R1, R9
    GOSUB __bc_gpio_write
    RET R0, 0

__bc_gpio_clear:
    MOV R9, R1
    GOSUB __bc_gpio_read_out
    MOV R0, R9
    CPL R0
    AND R1, R0
    GOSUB __bc_gpio_write
    RET R0, 0

__bc_gpio_toggle:
    MOV R9, R1
    GOSUB __bc_gpio_read_out
    XOR R1, R9
    GOSUB __bc_gpio_write
    RET R0, 0

__bc_gpio_test:
    MOV R9, R1
    GOSUB __bc_gpio_read
    AND R1, R9
    MOV R0, R1
    CP R0, 0
    MOV R1, 0
    SKIP Z, 1
    INC R1
    RET R0, 0

; ---------------------------------------------------------------------------
; Buttons, random, dimmer
; ---------------------------------------------------------------------------

__bc_mul4:
    MOV R3, 0
    MOV R4, 0
    MOV R5, R1
    MOV R6, 0
    MOV R7, 4
__bc_mul4_loop:
    MOV R0, R2
    AND R0, 1
    CP R0, 0
    SKIP NZ, 2
    GOTO __bc_mul4_noadd
    MOV R0, R3
    ADD R0, R5
    MOV R3, R0
    MOV R0, R4
    ADC R0, R6
    MOV R4, R0
__bc_mul4_noadd:
    ADD R5, R5
    ADC R6, R6
    ADD R0, 0
    RRC R2
    DSZ R7
    JR __bc_mul4_loop
    MOV R1, R3
    MOV R2, R4
    RET R0, 0

; char x char -> word.  in: R1:R2=a, R3:R4=b.  out: R1..R4.
__bc_mul8:
    MOV R0, 0
    MOV [0x38], R0
    MOV [0x39], R0
    MOV R5, 0
    MOV R6, 0
    MOV R7, 0
    MOV R8, 0
    MOV R9, 8
__bc_mul8_loop:
    MOV R0, R3
    AND R0, 1
    CP R0, 0
    SKIP NZ, 2
    GOTO __bc_mul8_noadd
    MOV R0, R5
    ADD R0, R1
    MOV R5, R0
    MOV R0, R6
    ADC R0, R2
    MOV R6, R0
    MOV R0, [0x38]
    ADC R7, R0
    MOV R0, [0x39]
    ADC R8, R0
__bc_mul8_noadd:
    ADD R1, R1
    ADC R2, R2
    MOV R0, [0x38]
    ADC R0, R0
    MOV [0x38], R0
    MOV R0, [0x39]
    ADC R0, R0
    MOV [0x39], R0
    ADD R0, 0
    RRC R4
    RRC R3
    DSZ R9
    JR __bc_mul8_loop
    MOV R1, R5
    MOV R2, R6
    MOV R3, R7
    MOV R4, R8
    RET R0, 0

; word x word -> low word.  in: R1..R4=a, R5..R8=b.  out: R1..R4.
__bc_mul16:
    MOV R0, 0
    MOV [0x38], R0
    MOV [0x39], R0
    MOV [0x3A], R0
    MOV [0x3B], R0
    MOV R9, 0
__bc_mul16_loop:
    MOV R0, R5
    AND R0, 1
    CP R0, 0
    SKIP NZ, 2
    GOTO __bc_mul16_noadd
    MOV R0, [0x38]
    ADD R0, R1
    MOV [0x38], R0
    MOV R0, [0x39]
    ADC R0, R2
    MOV [0x39], R0
    MOV R0, [0x3A]
    ADC R0, R3
    MOV [0x3A], R0
    MOV R0, [0x3B]
    ADC R0, R4
    MOV [0x3B], R0
__bc_mul16_noadd:
    ADD R1, R1
    ADC R2, R2
    ADC R3, R3
    ADC R4, R4
    ADD R0, 0
    RRC R8
    RRC R7
    RRC R6
    RRC R5
    DSZ R9
    JR __bc_mul16_loop
    MOV R0, [0x38]
    MOV R1, R0
    MOV R0, [0x39]
    MOV R2, R0
    MOV R0, [0x3A]
    MOV R3, R0
    MOV R0, [0x3B]
    MOV R4, R0
    RET R0, 0

; char / char.  in: R1:R2=dividend, R3:R4=divisor.
; out: R1:R2=quotient, R3:R4=remainder.  Zero divisor returns zero.
__bc_divmod8:
    MOV R0, R3
    OR R0, R4
    CP R0, 0
    SKIP NZ, 2
    GOTO __bc_divmod8_zero
    GOTO __bc_divmod8_start
__bc_divmod8_zero:
    MOV R1, 0
    MOV R2, 0
    MOV R3, 0
    MOV R4, 0
    RET R0, 0
__bc_divmod8_start:
    MOV R5, 0
    MOV R6, 0
    MOV R7, 0
    MOV R8, 0
    MOV R9, 8
__bc_divmod8_loop:
    ADD R7, R7
    ADC R8, R8
    MOV R0, R2
    AND R0, 8
    CP R0, 0
    SKIP Z, 1
    INC R7
    ADD R1, R1
    ADC R2, R2
    ADD R5, R5
    ADC R6, R6
    SUB R7, R3
    SBB R8, R4
    SKIP C, 2
    GOTO __bc_divmod8_restore
    INC R5
    GOTO __bc_divmod8_next
__bc_divmod8_restore:
    ADD R7, R3
    ADC R8, R4
__bc_divmod8_next:
    DSZ R9
    JR __bc_divmod8_loop
    MOV R1, R5
    MOV R2, R6
    MOV R3, R7
    MOV R4, R8
    RET R0, 0

; word / word.  in: R1..R4=dividend, R5..R8=divisor.
; out: R1..R4=quotient, R5..R8=remainder.  Zero divisor returns zero.
__bc_divmod16:
    MOV R0, 0
    MOV [0x38], R0
    MOV [0x39], R0
    MOV [0x3A], R0
    MOV [0x3B], R0
    MOV [0x3C], R0
    MOV [0x3D], R0
    MOV [0x3E], R0
    MOV [0x3F], R0
    MOV R0, R5
    OR R0, R6
    OR R0, R7
    OR R0, R8
    CP R0, 0
    SKIP NZ, 2
    GOTO __bc_divmod16_zero
    MOV R9, 0
__bc_divmod16_loop:
    ADD R1, R1
    ADC R2, R2
    ADC R3, R3
    ADC R4, R4
    MOV R0, [0x3C]
    ADC R0, R0
    MOV [0x3C], R0
    MOV R0, [0x3D]
    ADC R0, R0
    MOV [0x3D], R0
    MOV R0, [0x3E]
    ADC R0, R0
    MOV [0x3E], R0
    MOV R0, [0x3F]
    ADC R0, R0
    MOV [0x3F], R0
    MOV R0, [0x38]
    ADD R0, R0
    MOV [0x38], R0
    MOV R0, [0x39]
    ADC R0, R0
    MOV [0x39], R0
    MOV R0, [0x3A]
    ADC R0, R0
    MOV [0x3A], R0
    MOV R0, [0x3B]
    ADC R0, R0
    MOV [0x3B], R0
    MOV R0, [0x3C]
    SUB R0, R5
    MOV [0x3C], R0
    MOV R0, [0x3D]
    SBB R0, R6
    MOV [0x3D], R0
    MOV R0, [0x3E]
    SBB R0, R7
    MOV [0x3E], R0
    MOV R0, [0x3F]
    SBB R0, R8
    MOV [0x3F], R0
    SKIP C, 2
    GOTO __bc_divmod16_restore
    MOV R0, [0x38]
    OR R0, 1
    MOV [0x38], R0
    GOTO __bc_divmod16_next
__bc_divmod16_restore:
    MOV R0, [0x3C]
    ADD R0, R5
    MOV [0x3C], R0
    MOV R0, [0x3D]
    ADC R0, R6
    MOV [0x3D], R0
    MOV R0, [0x3E]
    ADC R0, R7
    MOV [0x3E], R0
    MOV R0, [0x3F]
    ADC R0, R8
    MOV [0x3F], R0
__bc_divmod16_next:
    DSZ R9
    JR __bc_divmod16_loop
    MOV R0, [0x38]
    MOV R1, R0
    MOV R0, [0x39]
    MOV R2, R0
    MOV R0, [0x3A]
    MOV R3, R0
    MOV R0, [0x3B]
    MOV R4, R0
    MOV R0, [0x3C]
    MOV R5, R0
    MOV R0, [0x3D]
    MOV R6, R0
    MOV R0, [0x3E]
    MOV R7, R0
    MOV R0, [0x3F]
    MOV R8, R0
    RET R0, 0
__bc_divmod16_zero:
    MOV R0, 0
    MOV R1, R0
    MOV R2, R0
    MOV R3, R0
    MOV R4, R0
    MOV R5, R0
    MOV R6, R0
    MOV R7, R0
    MOV R8, R0
    RET R0, 0

; Signed char / char.  in: R1:R2=a, R3:R4=b.
; out: R1:R2=quotient, R3:R4=remainder.  Zero divisor returns zero.
; Signs are stashed in the shared runtime scratch area (0x35..0x37); these
; bytes are not used by __bc_divmod8 and are free during a runtime call.
__bc_sdivmod8:
    MOV R0, R2
    AND R0, 8
    CP R0, 0
    SKIP Z, 2
    GOTO __bc_sdivmod8_a_neg
    MOV R0, 0
    MOV [0x36], R0
    GOTO __bc_sdivmod8_a_done
__bc_sdivmod8_a_neg:
    MOV R0, 1
    MOV [0x36], R0
    MOV R0, R1
    CPL R1, R0
    MOV R0, R2
    CPL R2, R0
    MOV R0, 1
    ADD R1, R0
    MOV R0, 0
    ADC R2, R0
__bc_sdivmod8_a_done:
    MOV R0, R4
    AND R0, 8
    CP R0, 0
    SKIP Z, 2
    GOTO __bc_sdivmod8_b_neg
    MOV R0, 0
    MOV [0x35], R0
    GOTO __bc_sdivmod8_b_done
__bc_sdivmod8_b_neg:
    MOV R0, 1
    MOV [0x35], R0
    MOV R0, R3
    CPL R3, R0
    MOV R0, R4
    CPL R4, R0
    MOV R0, 1
    ADD R3, R0
    MOV R0, 0
    ADC R4, R0
__bc_sdivmod8_b_done:
    MOV R0, [0x36]
    MOV R9, R0
    MOV R0, [0x35]
    XOR R0, R9
    MOV [0x37], R0
    GOSUB __bc_divmod8
    MOV R0, [0x37]
    CP R0, 0
    SKIP Z, 2
    GOTO __bc_sdivmod8_q_neg
    GOTO __bc_sdivmod8_q_done
__bc_sdivmod8_q_neg:
    MOV R0, R1
    CPL R1, R0
    MOV R0, R2
    CPL R2, R0
    MOV R0, 1
    ADD R1, R0
    MOV R0, 0
    ADC R2, R0
__bc_sdivmod8_q_done:
    MOV R0, [0x36]
    CP R0, 0
    SKIP Z, 2
    GOTO __bc_sdivmod8_r_neg
    GOTO __bc_sdivmod8_r_done
__bc_sdivmod8_r_neg:
    MOV R0, R3
    CPL R3, R0
    MOV R0, R4
    CPL R4, R0
    MOV R0, 1
    ADD R3, R0
    MOV R0, 0
    ADC R4, R0
__bc_sdivmod8_r_done:
    RET R0, 0

; Signed word / word.  in: R1..R4=a, R5..R8=b.
; out: R1..R4=quotient, R5..R8=remainder.  Zero divisor returns zero.
__bc_sdivmod16:
    MOV R0, R4
    AND R0, 8
    CP R0, 0
    SKIP Z, 2
    GOTO __bc_sdivmod16_a_neg
    MOV R0, 0
    MOV [0x36], R0
    GOTO __bc_sdivmod16_a_done
__bc_sdivmod16_a_neg:
    MOV R0, 1
    MOV [0x36], R0
    MOV R0, R1
    CPL R1, R0
    MOV R0, R2
    CPL R2, R0
    MOV R0, R3
    CPL R3, R0
    MOV R0, R4
    CPL R4, R0
    MOV R0, 1
    ADD R1, R0
    MOV R0, 0
    ADC R2, R0
    ADC R3, R0
    ADC R4, R0
__bc_sdivmod16_a_done:
    MOV R0, R8
    AND R0, 8
    CP R0, 0
    SKIP Z, 2
    GOTO __bc_sdivmod16_b_neg
    MOV R0, 0
    MOV [0x35], R0
    GOTO __bc_sdivmod16_b_done
__bc_sdivmod16_b_neg:
    MOV R0, 1
    MOV [0x35], R0
    MOV R0, R5
    CPL R5, R0
    MOV R0, R6
    CPL R6, R0
    MOV R0, R7
    CPL R7, R0
    MOV R0, R8
    CPL R8, R0
    MOV R0, 1
    ADD R5, R0
    MOV R0, 0
    ADC R6, R0
    ADC R7, R0
    ADC R8, R0
__bc_sdivmod16_b_done:
    MOV R0, [0x36]
    MOV R9, R0
    MOV R0, [0x35]
    XOR R0, R9
    MOV [0x37], R0
    GOSUB __bc_divmod16
    MOV R0, [0x37]
    CP R0, 0
    SKIP Z, 2
    GOTO __bc_sdivmod16_q_neg
    GOTO __bc_sdivmod16_q_done
__bc_sdivmod16_q_neg:
    MOV R0, R1
    CPL R1, R0
    MOV R0, R2
    CPL R2, R0
    MOV R0, R3
    CPL R3, R0
    MOV R0, R4
    CPL R4, R0
    MOV R0, 1
    ADD R1, R0
    MOV R0, 0
    ADC R2, R0
    ADC R3, R0
    ADC R4, R0
__bc_sdivmod16_q_done:
    MOV R0, [0x36]
    CP R0, 0
    SKIP Z, 2
    GOTO __bc_sdivmod16_r_neg
    GOTO __bc_sdivmod16_r_done
__bc_sdivmod16_r_neg:
    MOV R0, R5
    CPL R5, R0
    MOV R0, R6
    CPL R6, R0
    MOV R0, R7
    CPL R7, R0
    MOV R0, R8
    CPL R8, R0
    MOV R0, 1
    ADD R5, R0
    MOV R0, 0
    ADC R6, R0
    ADC R7, R0
    ADC R8, R0
__bc_sdivmod16_r_done:
    RET R0, 0

; Flash word read.  in: R1/R2/R3 = pointer.  out: R1..R4.
__bc_flash_read_word:
    MOV R6, R1
    MOV R7, R2
    MOV R8, R3
    MOV PCH, R8
    MOV PCM, R7
    MOV JSR, R6
    MOV R1, R0
    INC R6
    SKIP NC, 3
    INC R7
    SKIP NC, 1
    INC R8
    MOV PCH, R8
    MOV PCM, R7
    MOV JSR, R6
    MOV R2, R0
    INC R6
    SKIP NC, 3
    INC R7
    SKIP NC, 1
    INC R8
    MOV PCH, R8
    MOV PCM, R7
    MOV JSR, R6
    MOV R3, R0
    INC R6
    SKIP NC, 3
    INC R7
    SKIP NC, 1
    INC R8
    MOV PCH, R8
    MOV PCM, R7
    MOV JSR, R6
    MOV R4, R0
    RET R0, 0

; ---------------------------------------------------------------------------
; 32-bit multiply / divide
;
; Scratch layout (24 nibbles, allocated on demand):
;   00..07  A (multiply) / dividend and quotient (divide)
;   08..15  B (multiply) / divisor and remainder (divide)
;   16..23  result (multiply) / working remainder (divide)
; ---------------------------------------------------------------------------

; word pointers: R4:R5 = A, R6:R7 = B.  Result in R1..R8.
__bc_mul32:
    MOV R0, [R4:R5]
    MOV [__D32_00], R0
    INC R5
    SKIP NC, 1
    INC R4
    MOV R0, [R4:R5]
    MOV [__D32_01], R0
    INC R5
    SKIP NC, 1
    INC R4
    MOV R0, [R4:R5]
    MOV [__D32_02], R0
    INC R5
    SKIP NC, 1
    INC R4
    MOV R0, [R4:R5]
    MOV [__D32_03], R0
    INC R5
    SKIP NC, 1
    INC R4
    MOV R0, [R4:R5]
    MOV [__D32_04], R0
    INC R5
    SKIP NC, 1
    INC R4
    MOV R0, [R4:R5]
    MOV [__D32_05], R0
    INC R5
    SKIP NC, 1
    INC R4
    MOV R0, [R4:R5]
    MOV [__D32_06], R0
    INC R5
    SKIP NC, 1
    INC R4
    MOV R0, [R4:R5]
    MOV [__D32_07], R0
    MOV R0, [R6:R7]
    MOV [__D32_08], R0
    INC R7
    SKIP NC, 1
    INC R6
    MOV R0, [R6:R7]
    MOV [__D32_09], R0
    INC R7
    SKIP NC, 1
    INC R6
    MOV R0, [R6:R7]
    MOV [__D32_10], R0
    INC R7
    SKIP NC, 1
    INC R6
    MOV R0, [R6:R7]
    MOV [__D32_11], R0
    INC R7
    SKIP NC, 1
    INC R6
    MOV R0, [R6:R7]
    MOV [__D32_12], R0
    INC R7
    SKIP NC, 1
    INC R6
    MOV R0, [R6:R7]
    MOV [__D32_13], R0
    INC R7
    SKIP NC, 1
    INC R6
    MOV R0, [R6:R7]
    MOV [__D32_14], R0
    INC R7
    SKIP NC, 1
    INC R6
    MOV R0, [R6:R7]
    MOV [__D32_15], R0
    MOV R0, 0
    MOV [__D32_16], R0
    MOV R0, 0
    MOV [__D32_17], R0
    MOV R0, 0
    MOV [__D32_18], R0
    MOV R0, 0
    MOV [__D32_19], R0
    MOV R0, 0
    MOV [__D32_20], R0
    MOV R0, 0
    MOV [__D32_21], R0
    MOV R0, 0
    MOV [__D32_22], R0
    MOV R0, 0
    MOV [__D32_23], R0
    MOV R9, 0
    MOV R3, 2
__bc_mul32_loop:
    MOV R0, [__D32_08]
    AND R0, 1
    CP R0, 0
    SKIP NZ, 2
    GOTO __bc_mul32_noadd
    MOV R0, [__D32_00]
    MOV R8, R0
    MOV R0, [__D32_16]
    ADD R0, R8
    MOV [__D32_16], R0
    MOV R0, [__D32_01]
    MOV R8, R0
    MOV R0, [__D32_17]
    ADC R0, R8
    MOV [__D32_17], R0
    MOV R0, [__D32_02]
    MOV R8, R0
    MOV R0, [__D32_18]
    ADC R0, R8
    MOV [__D32_18], R0
    MOV R0, [__D32_03]
    MOV R8, R0
    MOV R0, [__D32_19]
    ADC R0, R8
    MOV [__D32_19], R0
    MOV R0, [__D32_04]
    MOV R8, R0
    MOV R0, [__D32_20]
    ADC R0, R8
    MOV [__D32_20], R0
    MOV R0, [__D32_05]
    MOV R8, R0
    MOV R0, [__D32_21]
    ADC R0, R8
    MOV [__D32_21], R0
    MOV R0, [__D32_06]
    MOV R8, R0
    MOV R0, [__D32_22]
    ADC R0, R8
    MOV [__D32_22], R0
    MOV R0, [__D32_07]
    MOV R8, R0
    MOV R0, [__D32_23]
    ADC R0, R8
    MOV [__D32_23], R0
__bc_mul32_noadd:
    ADD R0, 0
    MOV R0, [__D32_00]
    ADC R0, R0
    MOV [__D32_00], R0
    MOV R0, [__D32_01]
    ADC R0, R0
    MOV [__D32_01], R0
    MOV R0, [__D32_02]
    ADC R0, R0
    MOV [__D32_02], R0
    MOV R0, [__D32_03]
    ADC R0, R0
    MOV [__D32_03], R0
    MOV R0, [__D32_04]
    ADC R0, R0
    MOV [__D32_04], R0
    MOV R0, [__D32_05]
    ADC R0, R0
    MOV [__D32_05], R0
    MOV R0, [__D32_06]
    ADC R0, R0
    MOV [__D32_06], R0
    MOV R0, [__D32_07]
    ADC R0, R0
    MOV [__D32_07], R0
    ADD R0, 0
    MOV R0, [__D32_15]
    RRC R0
    MOV [__D32_15], R0
    MOV R0, [__D32_14]
    RRC R0
    MOV [__D32_14], R0
    MOV R0, [__D32_13]
    RRC R0
    MOV [__D32_13], R0
    MOV R0, [__D32_12]
    RRC R0
    MOV [__D32_12], R0
    MOV R0, [__D32_11]
    RRC R0
    MOV [__D32_11], R0
    MOV R0, [__D32_10]
    RRC R0
    MOV [__D32_10], R0
    MOV R0, [__D32_09]
    RRC R0
    MOV [__D32_09], R0
    MOV R0, [__D32_08]
    RRC R0
    MOV [__D32_08], R0
    DSZ R9
    JR __bc_mul32_continue
    DSZ R3
    JR __bc_mul32_continue
    GOTO __bc_mul32_done
__bc_mul32_continue:
    GOTO __bc_mul32_loop
__bc_mul32_done:
    MOV R0, [__D32_16]
    MOV R1, R0
    MOV R0, [__D32_17]
    MOV R2, R0
    MOV R0, [__D32_18]
    MOV R3, R0
    MOV R0, [__D32_19]
    MOV R4, R0
    MOV R0, [__D32_20]
    MOV R5, R0
    MOV R0, [__D32_21]
    MOV R6, R0
    MOV R0, [__D32_22]
    MOV R7, R0
    MOV R0, [__D32_23]
    MOV R8, R0
    RET R0, 0

; D pointer R4:R5 becomes quotient; V pointer R6:R7 becomes remainder.
__bc_divmod32:
    MOV R1, R4
    MOV R2, R5
    MOV R3, R6
    MOV R8, R7
    MOV R0, [R4:R5]
    MOV [__D32_00], R0
    INC R5
    SKIP NC, 1
    INC R4
    MOV R0, [R4:R5]
    MOV [__D32_01], R0
    INC R5
    SKIP NC, 1
    INC R4
    MOV R0, [R4:R5]
    MOV [__D32_02], R0
    INC R5
    SKIP NC, 1
    INC R4
    MOV R0, [R4:R5]
    MOV [__D32_03], R0
    INC R5
    SKIP NC, 1
    INC R4
    MOV R0, [R4:R5]
    MOV [__D32_04], R0
    INC R5
    SKIP NC, 1
    INC R4
    MOV R0, [R4:R5]
    MOV [__D32_05], R0
    INC R5
    SKIP NC, 1
    INC R4
    MOV R0, [R4:R5]
    MOV [__D32_06], R0
    INC R5
    SKIP NC, 1
    INC R4
    MOV R0, [R4:R5]
    MOV [__D32_07], R0
    MOV R0, [R6:R7]
    MOV [__D32_08], R0
    INC R7
    SKIP NC, 1
    INC R6
    MOV R0, [R6:R7]
    MOV [__D32_09], R0
    INC R7
    SKIP NC, 1
    INC R6
    MOV R0, [R6:R7]
    MOV [__D32_10], R0
    INC R7
    SKIP NC, 1
    INC R6
    MOV R0, [R6:R7]
    MOV [__D32_11], R0
    INC R7
    SKIP NC, 1
    INC R6
    MOV R0, [R6:R7]
    MOV [__D32_12], R0
    INC R7
    SKIP NC, 1
    INC R6
    MOV R0, [R6:R7]
    MOV [__D32_13], R0
    INC R7
    SKIP NC, 1
    INC R6
    MOV R0, [R6:R7]
    MOV [__D32_14], R0
    INC R7
    SKIP NC, 1
    INC R6
    MOV R0, [R6:R7]
    MOV [__D32_15], R0
    MOV R4, R1
    MOV R5, R2
    MOV R6, R3
    MOV R7, R8
    MOV R0, 0
    MOV [__D32_16], R0
    MOV R0, 0
    MOV [__D32_17], R0
    MOV R0, 0
    MOV [__D32_18], R0
    MOV R0, 0
    MOV [__D32_19], R0
    MOV R0, 0
    MOV [__D32_20], R0
    MOV R0, 0
    MOV [__D32_21], R0
    MOV R0, 0
    MOV [__D32_22], R0
    MOV R0, 0
    MOV [__D32_23], R0
    MOV R0, [__D32_08]
    MOV R8, R0
    MOV R0, [__D32_09]
    OR R8, R0
    MOV R0, [__D32_10]
    OR R8, R0
    MOV R0, [__D32_11]
    OR R8, R0
    MOV R0, [__D32_12]
    OR R8, R0
    MOV R0, [__D32_13]
    OR R8, R0
    MOV R0, [__D32_14]
    OR R8, R0
    MOV R0, [__D32_15]
    OR R8, R0
    MOV R0, R8
    CP R0, 0
    SKIP NZ, 2
    GOTO __bc_divmod32_zero
    MOV R9, 0
    MOV R3, 2
__bc_divmod32_loop:
    ADD R0, 0
    MOV R0, [__D32_00]
    ADC R0, R0
    MOV [__D32_00], R0
    MOV R0, [__D32_01]
    ADC R0, R0
    MOV [__D32_01], R0
    MOV R0, [__D32_02]
    ADC R0, R0
    MOV [__D32_02], R0
    MOV R0, [__D32_03]
    ADC R0, R0
    MOV [__D32_03], R0
    MOV R0, [__D32_04]
    ADC R0, R0
    MOV [__D32_04], R0
    MOV R0, [__D32_05]
    ADC R0, R0
    MOV [__D32_05], R0
    MOV R0, [__D32_06]
    ADC R0, R0
    MOV [__D32_06], R0
    MOV R0, [__D32_07]
    ADC R0, R0
    MOV [__D32_07], R0
    MOV R0, [__D32_16]
    ADC R0, R0
    MOV [__D32_16], R0
    MOV R0, [__D32_17]
    ADC R0, R0
    MOV [__D32_17], R0
    MOV R0, [__D32_18]
    ADC R0, R0
    MOV [__D32_18], R0
    MOV R0, [__D32_19]
    ADC R0, R0
    MOV [__D32_19], R0
    MOV R0, [__D32_20]
    ADC R0, R0
    MOV [__D32_20], R0
    MOV R0, [__D32_21]
    ADC R0, R0
    MOV [__D32_21], R0
    MOV R0, [__D32_22]
    ADC R0, R0
    MOV [__D32_22], R0
    MOV R0, [__D32_23]
    ADC R0, R0
    MOV [__D32_23], R0
    MOV R0, [__D32_08]
    MOV R8, R0
    MOV R0, [__D32_16]
    SUB R0, R8
    MOV [__D32_16], R0
    MOV R0, [__D32_09]
    MOV R8, R0
    MOV R0, [__D32_17]
    SBB R0, R8
    MOV [__D32_17], R0
    MOV R0, [__D32_10]
    MOV R8, R0
    MOV R0, [__D32_18]
    SBB R0, R8
    MOV [__D32_18], R0
    MOV R0, [__D32_11]
    MOV R8, R0
    MOV R0, [__D32_19]
    SBB R0, R8
    MOV [__D32_19], R0
    MOV R0, [__D32_12]
    MOV R8, R0
    MOV R0, [__D32_20]
    SBB R0, R8
    MOV [__D32_20], R0
    MOV R0, [__D32_13]
    MOV R8, R0
    MOV R0, [__D32_21]
    SBB R0, R8
    MOV [__D32_21], R0
    MOV R0, [__D32_14]
    MOV R8, R0
    MOV R0, [__D32_22]
    SBB R0, R8
    MOV [__D32_22], R0
    MOV R0, [__D32_15]
    MOV R8, R0
    MOV R0, [__D32_23]
    SBB R0, R8
    MOV [__D32_23], R0
    SKIP C, 2
    GOTO __bc_divmod32_restore
    MOV R0, [__D32_00]
    OR R0, 1
    MOV [__D32_00], R0
    GOTO __bc_divmod32_next
__bc_divmod32_restore:
    MOV R0, [__D32_08]
    MOV R8, R0
    MOV R0, [__D32_16]
    ADD R0, R8
    MOV [__D32_16], R0
    MOV R0, [__D32_09]
    MOV R8, R0
    MOV R0, [__D32_17]
    ADC R0, R8
    MOV [__D32_17], R0
    MOV R0, [__D32_10]
    MOV R8, R0
    MOV R0, [__D32_18]
    ADC R0, R8
    MOV [__D32_18], R0
    MOV R0, [__D32_11]
    MOV R8, R0
    MOV R0, [__D32_19]
    ADC R0, R8
    MOV [__D32_19], R0
    MOV R0, [__D32_12]
    MOV R8, R0
    MOV R0, [__D32_20]
    ADC R0, R8
    MOV [__D32_20], R0
    MOV R0, [__D32_13]
    MOV R8, R0
    MOV R0, [__D32_21]
    ADC R0, R8
    MOV [__D32_21], R0
    MOV R0, [__D32_14]
    MOV R8, R0
    MOV R0, [__D32_22]
    ADC R0, R8
    MOV [__D32_22], R0
    MOV R0, [__D32_15]
    MOV R8, R0
    MOV R0, [__D32_23]
    ADC R0, R8
    MOV [__D32_23], R0
__bc_divmod32_next:
    DSZ R9
    JR __bc_divmod32_continue
    DSZ R3
    JR __bc_divmod32_continue
    GOTO __bc_divmod32_output
__bc_divmod32_continue:
    GOTO __bc_divmod32_loop
__bc_divmod32_zero:
    MOV R0, 0
    MOV [__D32_00], R0
    MOV [__D32_01], R0
    MOV [__D32_02], R0
    MOV [__D32_03], R0
    MOV [__D32_04], R0
    MOV [__D32_05], R0
    MOV [__D32_06], R0
    MOV [__D32_07], R0
    MOV [__D32_08], R0
    MOV [__D32_09], R0
    MOV [__D32_10], R0
    MOV [__D32_11], R0
    MOV [__D32_12], R0
    MOV [__D32_13], R0
    MOV [__D32_14], R0
    MOV [__D32_15], R0
__bc_divmod32_output:
    MOV R0, [__D32_00]
    MOV [R4:R5], R0
    INC R5
    SKIP NC, 1
    INC R4
    MOV R0, [__D32_01]
    MOV [R4:R5], R0
    INC R5
    SKIP NC, 1
    INC R4
    MOV R0, [__D32_02]
    MOV [R4:R5], R0
    INC R5
    SKIP NC, 1
    INC R4
    MOV R0, [__D32_03]
    MOV [R4:R5], R0
    INC R5
    SKIP NC, 1
    INC R4
    MOV R0, [__D32_04]
    MOV [R4:R5], R0
    INC R5
    SKIP NC, 1
    INC R4
    MOV R0, [__D32_05]
    MOV [R4:R5], R0
    INC R5
    SKIP NC, 1
    INC R4
    MOV R0, [__D32_06]
    MOV [R4:R5], R0
    INC R5
    SKIP NC, 1
    INC R4
    MOV R0, [__D32_07]
    MOV [R4:R5], R0
    MOV R0, [__D32_16]
    MOV [R6:R7], R0
    INC R7
    SKIP NC, 1
    INC R6
    MOV R0, [__D32_17]
    MOV [R6:R7], R0
    INC R7
    SKIP NC, 1
    INC R6
    MOV R0, [__D32_18]
    MOV [R6:R7], R0
    INC R7
    SKIP NC, 1
    INC R6
    MOV R0, [__D32_19]
    MOV [R6:R7], R0
    INC R7
    SKIP NC, 1
    INC R6
    MOV R0, [__D32_20]
    MOV [R6:R7], R0
    INC R7
    SKIP NC, 1
    INC R6
    MOV R0, [__D32_21]
    MOV [R6:R7], R0
    INC R7
    SKIP NC, 1
    INC R6
    MOV R0, [__D32_22]
    MOV [R6:R7], R0
    INC R7
    SKIP NC, 1
    INC R6
    MOV R0, [__D32_23]
    MOV [R6:R7], R0
    RET R0, 0

; Flash dword read.  in: R1/R2/R3 = pointer.  out: R1..R8.
__bc_flash_read_dword:
    MOV R6, R1
    MOV R7, R2
    MOV R8, R3
    MOV PCH, R8
    MOV PCM, R7
    MOV JSR, R6
    MOV [__D32_00], R0
    INC R6
    SKIP NC, 3
    INC R7
    SKIP NC, 1
    INC R8
    MOV PCH, R8
    MOV PCM, R7
    MOV JSR, R6
    MOV [__D32_01], R0
    INC R6
    SKIP NC, 3
    INC R7
    SKIP NC, 1
    INC R8
    MOV PCH, R8
    MOV PCM, R7
    MOV JSR, R6
    MOV [__D32_02], R0
    INC R6
    SKIP NC, 3
    INC R7
    SKIP NC, 1
    INC R8
    MOV PCH, R8
    MOV PCM, R7
    MOV JSR, R6
    MOV [__D32_03], R0
    INC R6
    SKIP NC, 3
    INC R7
    SKIP NC, 1
    INC R8
    MOV PCH, R8
    MOV PCM, R7
    MOV JSR, R6
    MOV [__D32_04], R0
    INC R6
    SKIP NC, 3
    INC R7
    SKIP NC, 1
    INC R8
    MOV PCH, R8
    MOV PCM, R7
    MOV JSR, R6
    MOV [__D32_05], R0
    INC R6
    SKIP NC, 3
    INC R7
    SKIP NC, 1
    INC R8
    MOV PCH, R8
    MOV PCM, R7
    MOV JSR, R6
    MOV [__D32_06], R0
    INC R6
    SKIP NC, 3
    INC R7
    SKIP NC, 1
    INC R8
    MOV PCH, R8
    MOV PCM, R7
    MOV JSR, R6
    MOV [__D32_07], R0
    MOV R0, [__D32_00]
    MOV R1, R0
    MOV R0, [__D32_01]
    MOV R2, R0
    MOV R0, [__D32_02]
    MOV R3, R0
    MOV R0, [__D32_03]
    MOV R4, R0
    MOV R0, [__D32_04]
    MOV R5, R0
    MOV R0, [__D32_05]
    MOV R6, R0
    MOV R0, [__D32_06]
    MOV R7, R0
    MOV R0, [__D32_07]
    MOV R8, R0
    RET R0, 0

; ---------------------------------------------------------------------------
; WrFlags helper bits
; ---------------------------------------------------------------------------

__bc_gpio_read_out:
    MOV R0, [0xF3]
    AND R0, 2
    CP R0, 0
    SKIP NZ, 3
    MOV R0, [0x0A]              ; IOPos=0: OUT
    MOV R1, R0
    RET R0, 0
    MOV R0, [0xFA]              ; IOPos=1: OutB
    MOV R1, R0
    RET R0, 0

__bc_gpio_write:
    MOV R0, [0xF3]
    AND R0, 2
    CP R0, 0
    SKIP NZ, 3
    MOV R0, R1
    MOV [0x0A], R0              ; IOPos=0: OUT
    RET R0, 0
    MOV R0, R1
    MOV [0xFA], R0              ; IOPos=1: OutB
    RET R0, 0

__bc_gpio_read:
    MOV R0, [0xF3]
    AND R0, 2
    CP R0, 0
    SKIP NZ, 3
    MOV R0, [0x0B]              ; IOPos=0: IN
    MOV R1, R0
    RET R0, 0
    MOV R0, [0xFB]              ; IOPos=1: InB
    MOV R1, R0
    RET R0, 0

; Write the 4-bit connector output, honoring WrFlags.IOPos.
; Read the 4-bit output latch, honoring WrFlags.IOPos.

__bc_delay:
    MOV R2, R1
    MOV R0, R2
    CP R0, 0
    SKIP NZ, 1
    RET R0, 0
__bc_delay_outer:
    MOV R3, 15
__bc_delay_inner:
    DEC R3
    MOV R0, R3
    CP R0, 0
    SKIP Z, 2
    GOTO __bc_delay_inner
    DSZ R2
    JR __bc_delay_outer
    RET R0, 0

; Copy R1 nibbles from R6:R7 to R4:R5.
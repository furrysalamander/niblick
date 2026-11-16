; Accurate binary16 add/sub (round-to-nearest-even).
;
; Scratch: 0x20..0x25 A, 0x28..0x2D B, 0x30..0x35 result,
; 0x36 sticky, 0x37 subtraction, 0x38..0x3A exp A, 0x3B..0x3D exp B.

fn___nib_f16_add:
    MOV R0, [${a+0}]
    MOV [0x20], R0
    MOV R0, [${a+1}]
    MOV [0x21], R0
    MOV R0, [${a+2}]
    MOV [0x22], R0
    MOV R0, [${a+3}]
    MOV [0x23], R0
    MOV R0, [${b+0}]
    MOV [0x28], R0
    MOV R0, [${b+1}]
    MOV [0x29], R0
    MOV R0, [${b+2}]
    MOV [0x2A], R0
    MOV R0, [${b+3}]
    MOV [0x2B], R0
    MOV R0, 0
    MOV [0x3F], R0
    GOTO fn___nib_f16_core

fn___nib_f16_mul:
    MOV R0, [${a+0}]
    MOV [0x20], R0
    MOV R0, [${a+1}]
    MOV [0x21], R0
    MOV R0, [${a+2}]
    MOV [0x22], R0
    MOV R0, [${a+3}]
    MOV [0x23], R0
    MOV R0, [${b+0}]
    MOV [0x28], R0
    MOV R0, [${b+1}]
    MOV [0x29], R0
    MOV R0, [${b+2}]
    MOV [0x2A], R0
    MOV R0, [${b+3}]
    MOV [0x2B], R0
    MOV R0, 1
    MOV [0x3F], R0
    GOTO fn___nib_f16_core

fn___nib_f16_div:
    MOV R0, [${a+0}]
    MOV [0x20], R0
    MOV R0, [${a+1}]
    MOV [0x21], R0
    MOV R0, [${a+2}]
    MOV [0x22], R0
    MOV R0, [${a+3}]
    MOV [0x23], R0
    MOV R0, [${b+0}]
    MOV [0x28], R0
    MOV R0, [${b+1}]
    MOV [0x29], R0
    MOV R0, [${b+2}]
    MOV [0x2A], R0
    MOV R0, [${b+3}]
    MOV [0x2B], R0
    MOV R0, 2
    MOV [0x3F], R0
    GOTO fn___nib_f16_core

fn___nib_f16_sub:
    MOV R0, [${a+0}]
    MOV [0x20], R0
    MOV R0, [${a+1}]
    MOV [0x21], R0
    MOV R0, [${a+2}]
    MOV [0x22], R0
    MOV R0, [${a+3}]
    MOV [0x23], R0
    MOV R0, [${b+0}]
    MOV [0x28], R0
    MOV R0, [${b+1}]
    MOV [0x29], R0
    MOV R0, [${b+2}]
    MOV [0x2A], R0
    MOV R0, [${b+3}]
    MOV [0x2B], R0
    MOV R0, [0x2B]
    XOR R0, 8
    MOV [0x2B], R0
    MOV R0, 0
    MOV [0x3F], R0
    GOTO fn___nib_f16_core

fn___nib_f16_core:
    MOV R0, [0x23]
    AND R0, 8
    MOV R8, R0
    MOV R0, [0x2B]
    AND R0, 8
    MOV R9, R0
    MOV R0, [0x22]
    MOV R2, R0
    MOV R0, R2
    MOV R1, 0
    ADD R0, R1
    RRC R0
    RRC R0
    AND R0, 3
    MOV R2, R0
    MOV R0, [0x23]
    MOV R3, R0
    MOV R0, R3
    AND R0, 3
    ADD R0, R0
    ADD R0, R0
    OR R2, R0
    MOV R0, R2
    MOV [0x38], R0
    MOV R0, [0x23]
    AND R0, 4
    MOV R1, 0
    ADD R0, R1
    RRC R0
    RRC R0
    MOV [0x39], R0
    MOV R0, 0
    MOV [0x3A], R0
    MOV R0, [0x2A]
    MOV R2, R0
    MOV R0, R2
    MOV R1, 0
    ADD R0, R1
    RRC R0
    RRC R0
    AND R0, 3
    MOV R2, R0
    MOV R0, [0x2B]
    MOV R3, R0
    MOV R0, R3
    AND R0, 3
    ADD R0, R0
    ADD R0, R0
    OR R2, R0
    MOV R0, R2
    MOV [0x3B], R0
    MOV R0, [0x2B]
    AND R0, 4
    MOV R1, 0
    ADD R0, R1
    RRC R0
    RRC R0
    MOV [0x3C], R0
    MOV R0, 0
    MOV [0x3D], R0
    MOV R0, [0x3F]
    CP R0, 0
    SKIP Z, 2
    GOTO .muldiv_special
    GOTO .add_special
.add_special:
    MOV R0, [0x38]
    CP R0, 0xF
    SKIP Z, 2
    GOTO .check_b_special
    GOTO .check_a_hi
.check_a_hi:
    MOV R0, [0x39]
    CP R0, 1
    SKIP Z, 2
    GOTO .check_b_special
    GOTO .a_special
.a_special:
    MOV R0, [0x20]
    MOV R1, R0
    MOV R0, [0x21]
    OR R1, R0
    MOV R0, [0x22]
    AND R0, 3
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP Z, 2
    GOTO .nan
    GOTO .a_inf
.a_inf:
    MOV R0, [0x3B]
    CP R0, 0xF
    SKIP NZ, 2
    GOTO .check_b_inf_hi
    GOTO .return_a
.check_b_inf_hi:
    MOV R0, [0x3C]
    CP R0, 1
    SKIP Z, 2
    GOTO .return_a
    GOTO .b_inf_with_a_inf
.b_inf_with_a_inf:
    MOV R0, [0x28]
    MOV R1, R0
    MOV R0, [0x29]
    OR R1, R0
    MOV R0, [0x2A]
    AND R0, 3
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP Z, 2
    GOTO .nan
    GOTO .inf_sign_check
.inf_sign_check:
    MOV R0, R8
    MOV R1, R0
    MOV R0, R9
    SUB R1, R0
    SKIP Z, 2
    GOTO .nan
    GOTO .return_a
.check_b_special:
    MOV R0, [0x3B]
    CP R0, 0xF
    SKIP Z, 2
    GOTO .unpack
    GOTO .check_b_hi
.check_b_hi:
    MOV R0, [0x3C]
    CP R0, 1
    SKIP Z, 2
    GOTO .unpack
    GOTO .b_special
.b_special:
    MOV R0, [0x28]
    MOV R1, R0
    MOV R0, [0x29]
    OR R1, R0
    MOV R0, [0x2A]
    AND R0, 3
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP Z, 2
    GOTO .nan
    GOTO .return_b
.unpack:
    MOV R0, [0x38]
    MOV R1, R0
    MOV R0, [0x39]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP Z, 2
    GOTO .check_b_zero
    GOTO .zfrac_1
.zfrac_1:
    MOV R0, [0x20]
    MOV R1, R0
    MOV R0, [0x21]
    OR R1, R0
    MOV R0, [0x22]
    AND R0, 3
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .a_zero
    GOTO .check_b_zero
.a_zero:
    MOV R0, [0x3B]
    MOV R1, R0
    MOV R0, [0x3C]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP Z, 2
    GOTO .return_b
    GOTO .zfrac_2
.zfrac_2:
    MOV R0, [0x28]
    MOV R1, R0
    MOV R0, [0x29]
    OR R1, R0
    MOV R0, [0x2A]
    AND R0, 3
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .both_zero
    GOTO .return_b
.check_b_zero:
    MOV R0, [0x3B]
    MOV R1, R0
    MOV R0, [0x3C]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP Z, 2
    GOTO .unpack_a
    GOTO .zfrac_3
.zfrac_3:
    MOV R0, [0x28]
    MOV R1, R0
    MOV R0, [0x29]
    OR R1, R0
    MOV R0, [0x2A]
    AND R0, 3
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .return_a
    GOTO .unpack_a
.both_zero:
    MOV R0, R8
    AND R0, R9
    MOV R8, R0
    MOV R1, 0
    MOV R2, 0
    MOV R3, 0
    RET R0, 0
.unpack_a:
    MOV R0, 0
    MOV [0x36], R0
    MOV R0, [0x20]
    MOV R1, R0
    MOV R0, [0x21]
    MOV R2, R0
    MOV R0, [0x22]
    MOV R3, R0
    AND R0, 3
    MOV R3, R0
    MOV R0, 0
    MOV [0x20], R0
    MOV [0x21], R0
    MOV [0x22], R0
    MOV R0, R1
    AND R0, 7
    ADD R0, R0
    MOV [0x23], R0
    MOV R0, R2
    AND R0, 7
    ADD R0, R0
    MOV R4, R0
    MOV R0, R1
    AND R0, 8
    RRC R0
    RRC R0
    RRC R0
    OR R0, R4
    MOV [0x24], R0
    MOV R0, R3
    ADD R0, R0
    MOV R4, R0
    MOV R0, R2
    AND R0, 8
    RRC R0
    RRC R0
    RRC R0
    OR R0, R4
    MOV [0x25], R0
    MOV R0, [0x38]
    MOV R1, R0
    MOV R0, [0x39]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .subnormal_a
    MOV R0, [0x25]
    OR R0, 8
    MOV [0x25], R0
    MOV R0, [0x38]
    MOV R1, 1
    ADD R0, R1
    MOV [0x38], R0
    MOV R1, 0xF
    MOV R0, [0x39]
    ADC R0, R1
    MOV [0x39], R0
    MOV R1, 0
    MOV R0, [0x3A]
    ADC R0, R1
    MOV [0x3A], R0
    GOTO .unpack_b
.subnormal_a:
    MOV R0, 2
    MOV [0x38], R0
    MOV R0, 0xF
    MOV [0x39], R0
    MOV R0, 0
    MOV [0x3A], R0
.subnorm_4:
    MOV R0, [0x25]
    AND R0, 8
    CP R0, 0
    SKIP Z, 2
    GOTO .unpack_b
    MOV R0, [0x20]
    ADD R0, R0
    MOV [0x20], R0
    MOV R0, [0x21]
    ADC R0, R0
    MOV [0x21], R0
    MOV R0, [0x22]
    ADC R0, R0
    MOV [0x22], R0
    MOV R0, [0x23]
    ADC R0, R0
    MOV [0x23], R0
    MOV R0, [0x24]
    ADC R0, R0
    MOV [0x24], R0
    MOV R0, [0x25]
    ADC R0, R0
    MOV [0x25], R0
    MOV R1, 1
    MOV R0, [0x38]
    SUB R0, R1
    MOV [0x38], R0
    MOV R1, 0
    MOV R0, [0x39]
    SBB R0, R1
    MOV [0x39], R0
    MOV R1, 0
    MOV R0, [0x3A]
    SBB R0, R1
    MOV [0x3A], R0
    GOTO .subnorm_4
.unpack_b:
    MOV R0, [0x28]
    MOV R1, R0
    MOV R0, [0x29]
    MOV R2, R0
    MOV R0, [0x2A]
    MOV R3, R0
    AND R0, 3
    MOV R3, R0
    MOV R0, 0
    MOV [0x28], R0
    MOV [0x29], R0
    MOV [0x2A], R0
    MOV R0, R1
    AND R0, 7
    ADD R0, R0
    MOV [0x2B], R0
    MOV R0, R2
    AND R0, 7
    ADD R0, R0
    MOV R4, R0
    MOV R0, R1
    AND R0, 8
    RRC R0
    RRC R0
    RRC R0
    OR R0, R4
    MOV [0x2C], R0
    MOV R0, R3
    ADD R0, R0
    MOV R4, R0
    MOV R0, R2
    AND R0, 8
    RRC R0
    RRC R0
    RRC R0
    OR R0, R4
    MOV [0x2D], R0
    MOV R0, [0x3B]
    MOV R1, R0
    MOV R0, [0x3C]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .subnormal_b
    MOV R0, [0x2D]
    OR R0, 8
    MOV [0x2D], R0
    MOV R0, [0x3B]
    MOV R1, 1
    ADD R0, R1
    MOV [0x3B], R0
    MOV R1, 0xF
    MOV R0, [0x3C]
    ADC R0, R1
    MOV [0x3C], R0
    MOV R1, 0
    MOV R0, [0x3D]
    ADC R0, R1
    MOV [0x3D], R0
    GOTO .unpack_done
.subnormal_b:
    MOV R0, 2
    MOV [0x3B], R0
    MOV R0, 0xF
    MOV [0x3C], R0
    MOV R0, 0
    MOV [0x3D], R0
.subnorm_5:
    MOV R0, [0x2D]
    AND R0, 8
    CP R0, 0
    SKIP Z, 2
    GOTO .unpack_done
    MOV R0, [0x28]
    ADD R0, R0
    MOV [0x28], R0
    MOV R0, [0x29]
    ADC R0, R0
    MOV [0x29], R0
    MOV R0, [0x2A]
    ADC R0, R0
    MOV [0x2A], R0
    MOV R0, [0x2B]
    ADC R0, R0
    MOV [0x2B], R0
    MOV R0, [0x2C]
    ADC R0, R0
    MOV [0x2C], R0
    MOV R0, [0x2D]
    ADC R0, R0
    MOV [0x2D], R0
    MOV R1, 1
    MOV R0, [0x3B]
    SUB R0, R1
    MOV [0x3B], R0
    MOV R1, 0
    MOV R0, [0x3C]
    SBB R0, R1
    MOV [0x3C], R0
    MOV R1, 0
    MOV R0, [0x3D]
    SBB R0, R1
    MOV [0x3D], R0
    GOTO .subnorm_5
.unpack_done:
    MOV R0, [0x3F]
    CP R0, 0
    SKIP Z, 2
    GOTO .muldiv_calc
    GOTO .align
.muldiv_calc:
    MOV R0, [0x23]
    ADD R0, 0
    RRC R0
    MOV R2, R0
    MOV R0, [0x24]
    AND R0, 1
    ADD R0, R0
    ADD R0, R0
    ADD R0, R0
    OR R0, R2
    MOV [0x20], R0
    MOV R0, [0x24]
    ADD R0, 0
    RRC R0
    AND R0, 7
    MOV R2, R0
    MOV R0, [0x25]
    AND R0, 1
    ADD R0, R0
    ADD R0, R0
    ADD R0, R0
    OR R0, R2
    MOV [0x21], R0
    MOV R0, [0x25]
    ADD R0, 0
    RRC R0
    AND R0, 7
    MOV [0x22], R0
    MOV R0, 0
    MOV [0x23], R0
    MOV [0x24], R0
    MOV [0x25], R0
    MOV R0, [0x2B]
    ADD R0, 0
    RRC R0
    MOV R2, R0
    MOV R0, [0x2C]
    AND R0, 1
    ADD R0, R0
    ADD R0, R0
    ADD R0, R0
    OR R0, R2
    MOV [0x28], R0
    MOV R0, [0x2C]
    ADD R0, 0
    RRC R0
    AND R0, 7
    MOV R2, R0
    MOV R0, [0x2D]
    AND R0, 1
    ADD R0, R0
    ADD R0, R0
    ADD R0, R0
    OR R0, R2
    MOV [0x29], R0
    MOV R0, [0x2D]
    ADD R0, 0
    RRC R0
    AND R0, 7
    MOV [0x2A], R0
    MOV R0, 0
    MOV [0x2B], R0
    MOV [0x2C], R0
    MOV [0x2D], R0
    MOV R0, [0x3F]
    CP R0, 1
    SKIP Z, 2
    GOTO .div_calc
    GOTO .mul_calc
.mul_calc:
    MOV R0, 0
    MOV [0x30], R0
    MOV [0x31], R0
    MOV [0x32], R0
    MOV [0x33], R0
    MOV [0x34], R0
    MOV [0x35], R0
    MOV R7, 11
.mul_loop_6:
    MOV R0, [0x28]
    AND R0, 1
    CP R0, 0
    SKIP NZ, 2
    GOTO .mul_skip_8
    MOV R0, [0x30]
    MOV R1, R0
    MOV R0, [0x20]
    ADD R1, R0
    MOV R0, R1
    MOV [0x30], R0
    MOV R0, [0x31]
    MOV R1, R0
    MOV R0, [0x21]
    ADC R1, R0
    MOV R0, R1
    MOV [0x31], R0
    MOV R0, [0x32]
    MOV R1, R0
    MOV R0, [0x22]
    ADC R1, R0
    MOV R0, R1
    MOV [0x32], R0
    MOV R0, [0x33]
    MOV R1, R0
    MOV R0, [0x23]
    ADC R1, R0
    MOV R0, R1
    MOV [0x33], R0
    MOV R0, [0x34]
    MOV R1, R0
    MOV R0, [0x24]
    ADC R1, R0
    MOV R0, R1
    MOV [0x34], R0
    MOV R0, [0x35]
    MOV R1, R0
    MOV R0, [0x25]
    ADC R1, R0
    MOV R0, R1
    MOV [0x35], R0
.mul_skip_8:
    MOV R0, [0x20]
    ADD R0, R0
    MOV [0x20], R0
    MOV R0, [0x21]
    ADC R0, R0
    MOV [0x21], R0
    MOV R0, [0x22]
    ADC R0, R0
    MOV [0x22], R0
    MOV R0, [0x23]
    ADC R0, R0
    MOV [0x23], R0
    MOV R0, [0x24]
    ADC R0, R0
    MOV [0x24], R0
    MOV R0, [0x25]
    ADC R0, R0
    MOV [0x25], R0
    MOV R0, 0
    ADD R0, 0
    MOV R0, [0x2A]
    RRC R0
    MOV [0x2A], R0
    MOV R0, [0x29]
    RRC R0
    MOV [0x29], R0
    MOV R0, [0x28]
    RRC R0
    MOV [0x28], R0
    DEC R7
    SKIP NZ, 2
    GOTO .mul_done_7
    GOTO .mul_loop_6
.mul_done_7:
    MOV R0, [0x38]
    MOV R1, R0
    MOV R0, [0x3B]
    ADD R1, R0
    MOV R0, R1
    MOV [0x38], R0
    MOV R0, [0x39]
    MOV R1, R0
    MOV R0, [0x3C]
    ADC R1, R0
    MOV R0, R1
    MOV [0x39], R0
    MOV R0, [0x3A]
    MOV R1, R0
    MOV R0, [0x3D]
    ADC R1, R0
    MOV R0, R1
    MOV [0x3A], R0
    MOV R0, [0x38]
    MOV R1, 0xD
    SUB R0, R1
    MOV [0x38], R0
    MOV R0, [0x39]
    MOV R1, 0xF
    SBB R0, R1
    MOV [0x39], R0
    MOV R0, [0x3A]
    MOV R1, 0
    SBB R0, R1
    MOV [0x3A], R0
    MOV R0, 0
    MOV [0x36], R0
    MOV [0x37], R0
    GOTO .normalize
.div_calc:
    MOV R0, 0
    MOV [0x23], R0
    MOV [0x24], R0
    MOV [0x25], R0
    MOV [0x26], R0
    MOV [0x27], R0
    MOV R7, 7
.div_shift_9:
    MOV R0, [0x20]
    ADD R0, R0
    MOV [0x20], R0
    MOV R0, [0x21]
    ADC R0, R0
    MOV [0x21], R0
    MOV R0, [0x22]
    ADC R0, R0
    MOV [0x22], R0
    MOV R0, [0x23]
    ADC R0, R0
    MOV [0x23], R0
    MOV R0, [0x24]
    ADC R0, R0
    MOV [0x24], R0
    MOV R0, [0x25]
    ADC R0, R0
    MOV [0x25], R0
    MOV R0, [0x26]
    ADC R0, R0
    MOV [0x26], R0
    MOV R0, [0x27]
    ADC R0, R0
    MOV [0x27], R0
    DEC R7
    SKIP NZ, 2
    GOTO .div_shift_done_10
    GOTO .div_shift_9
.div_shift_done_10:
    MOV R7, 7
.div_shift_11:
    MOV R0, [0x20]
    ADD R0, R0
    MOV [0x20], R0
    MOV R0, [0x21]
    ADC R0, R0
    MOV [0x21], R0
    MOV R0, [0x22]
    ADC R0, R0
    MOV [0x22], R0
    MOV R0, [0x23]
    ADC R0, R0
    MOV [0x23], R0
    MOV R0, [0x24]
    ADC R0, R0
    MOV [0x24], R0
    MOV R0, [0x25]
    ADC R0, R0
    MOV [0x25], R0
    MOV R0, [0x26]
    ADC R0, R0
    MOV [0x26], R0
    MOV R0, [0x27]
    ADC R0, R0
    MOV [0x27], R0
    DEC R7
    SKIP NZ, 2
    GOTO .div_shift_done_12
    GOTO .div_shift_11
.div_shift_done_12:
    MOV R7, 7
.div_shift_13:
    MOV R0, [0x20]
    ADD R0, R0
    MOV [0x20], R0
    MOV R0, [0x21]
    ADC R0, R0
    MOV [0x21], R0
    MOV R0, [0x22]
    ADC R0, R0
    MOV [0x22], R0
    MOV R0, [0x23]
    ADC R0, R0
    MOV [0x23], R0
    MOV R0, [0x24]
    ADC R0, R0
    MOV [0x24], R0
    MOV R0, [0x25]
    ADC R0, R0
    MOV [0x25], R0
    MOV R0, [0x26]
    ADC R0, R0
    MOV [0x26], R0
    MOV R0, [0x27]
    ADC R0, R0
    MOV [0x27], R0
    DEC R7
    SKIP NZ, 2
    GOTO .div_shift_done_14
    GOTO .div_shift_13
.div_shift_done_14:
    MOV R0, 0
    MOV [0x2B], R0
    MOV [0x2C], R0
    MOV [0x2D], R0
    MOV [0x2E], R0
    MOV [0x2F], R0
    MOV R0, R8
    MOV [0x3E], R0
    MOV R4, 2
    MOV R5, 0
    MOV R6, 2
    MOV R7, 8
    GOSUB __nib_divmod32
    MOV R0, [0x3E]
    MOV R8, R0
    MOV R0, [0x20]
    MOV [0x30], R0
    MOV R0, [0x21]
    MOV [0x31], R0
    MOV R0, [0x22]
    MOV [0x32], R0
    MOV R0, [0x23]
    MOV [0x33], R0
    MOV R0, [0x24]
    MOV [0x34], R0
    MOV R0, [0x25]
    MOV [0x35], R0
    MOV R0, [0x38]
    MOV R1, R0
    MOV R0, [0x3B]
    SUB R1, R0
    MOV R0, R1
    MOV [0x3B], R0
    MOV R0, [0x39]
    MOV R1, R0
    MOV R0, [0x3C]
    SBB R1, R0
    MOV R0, R1
    MOV [0x3C], R0
    MOV R0, [0x3A]
    MOV R1, R0
    MOV R0, [0x3D]
    SBB R1, R0
    MOV R0, R1
    MOV [0x3D], R0
    MOV R0, [0x3B]
    MOV R1, 2
    ADD R0, R1
    MOV [0x3B], R0
    MOV R0, [0x3C]
    MOV R1, 0
    ADC R0, R1
    MOV [0x3C], R0
    MOV R0, [0x3D]
    MOV R1, 1
    ADC R0, R1
    MOV [0x3D], R0
    MOV R0, [0x3B]
    MOV [0x38], R0
    MOV R0, [0x3C]
    MOV [0x39], R0
    MOV R0, [0x3D]
    MOV [0x3A], R0
    MOV R0, [0x28]
    MOV R1, R0
    MOV R0, [0x29]
    OR R1, R0
    MOV R0, [0x2A]
    OR R1, R0
    MOV R0, [0x2B]
    OR R1, R0
    MOV R0, [0x2C]
    OR R1, R0
    MOV R0, [0x2D]
    OR R1, R0
    MOV R0, [0x2E]
    OR R1, R0
    MOV R0, [0x2F]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    MOV R0, 0
    SKIP Z, 1
    INC R0
    MOV [0x36], R0
    MOV R0, 0
    MOV [0x37], R0
    GOTO .normalize
.muldiv_special:
    MOV R0, R8
    XOR R0, R9
    MOV R8, R0
    MOV R0, [0x38]
    CP R0, 0xF
    SKIP Z, 2
    GOTO .md_check_b_nan
    MOV R0, [0x39]
    CP R0, 1
    SKIP Z, 2
    GOTO .md_check_b_nan
    MOV R0, [0x20]
    MOV R1, R0
    MOV R0, [0x21]
    OR R1, R0
    MOV R0, [0x22]
    AND R0, 3
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP Z, 2
    GOTO .nan
.md_check_b_nan:
    MOV R0, [0x3B]
    CP R0, 0xF
    SKIP Z, 2
    GOTO .md_mode
    MOV R0, [0x3C]
    CP R0, 1
    SKIP Z, 2
    GOTO .md_mode
    MOV R0, [0x28]
    MOV R1, R0
    MOV R0, [0x29]
    OR R1, R0
    MOV R0, [0x2A]
    AND R0, 3
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP Z, 2
    GOTO .nan
.md_mode:
    MOV R0, [0x3F]
    CP R0, 1
    SKIP Z, 2
    GOTO .div_special
    GOTO .mul_special
.mul_special:
    MOV R0, [0x38]
    CP R0, 0xF
    SKIP Z, 2
    GOTO .mul_check_b_inf
    MOV R0, [0x39]
    CP R0, 1
    SKIP Z, 2
    GOTO .mul_check_b_inf
    MOV R0, [0x20]
    MOV R1, R0
    MOV R0, [0x21]
    OR R1, R0
    MOV R0, [0x22]
    AND R0, 3
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .mul_a_inf
    GOTO .mul_check_b_inf
.mul_a_inf:
    MOV R0, [0x28]
    MOV R1, R0
    MOV R0, [0x29]
    OR R1, R0
    MOV R0, [0x2A]
    AND R0, 3
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP Z, 2
    GOTO .mul_inf_result
    GOTO .mul_a_inf_exp
.mul_a_inf_exp:
    MOV R0, [0x3B]
    MOV R1, R0
    MOV R0, [0x3C]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .nan
    GOTO .mul_inf_result
.mul_inf_result:
    GOTO .pack_inf
.mul_check_b_inf:
    MOV R0, [0x3B]
    CP R0, 0xF
    SKIP Z, 2
    GOTO .mul_zero_check
    MOV R0, [0x3C]
    CP R0, 1
    SKIP Z, 2
    GOTO .mul_zero_check
    MOV R0, [0x28]
    MOV R1, R0
    MOV R0, [0x29]
    OR R1, R0
    MOV R0, [0x2A]
    AND R0, 3
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .mul_b_inf
    GOTO .mul_zero_check
.mul_b_inf:
    MOV R0, [0x20]
    MOV R1, R0
    MOV R0, [0x21]
    OR R1, R0
    MOV R0, [0x22]
    AND R0, 3
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP Z, 2
    GOTO .mul_inf_result
    GOTO .mul_b_inf_exp
.mul_b_inf_exp:
    MOV R0, [0x38]
    MOV R1, R0
    MOV R0, [0x39]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .nan
    GOTO .mul_inf_result
.mul_zero_check:
    MOV R0, [0x38]
    MOV R1, R0
    MOV R0, [0x39]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .mul_a_maybe_zero
    GOTO .mul_check_b_zero
.mul_a_maybe_zero:
    MOV R0, [0x20]
    MOV R1, R0
    MOV R0, [0x21]
    OR R1, R0
    MOV R0, [0x22]
    AND R0, 3
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP Z, 2
    GOTO .mul_check_b_zero
    GOTO .sub_zero
.mul_check_b_zero:
    MOV R0, [0x3B]
    MOV R1, R0
    MOV R0, [0x3C]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .mul_b_maybe_zero
    GOTO .unpack_a
.mul_b_maybe_zero:
    MOV R0, [0x28]
    MOV R1, R0
    MOV R0, [0x29]
    OR R1, R0
    MOV R0, [0x2A]
    AND R0, 3
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP Z, 2
    GOTO .unpack_a
    GOTO .sub_zero
.div_special:
    MOV R0, [0x3B]
    CP R0, 0xF
    SKIP NZ, 2
    GOTO .div_check_b_hi
    GOTO .div_b_not_inf
.div_check_b_hi:
    MOV R0, [0x3C]
    CP R0, 1
    SKIP Z, 2
    GOTO .div_b_not_inf
    MOV R0, [0x28]
    MOV R1, R0
    MOV R0, [0x29]
    OR R1, R0
    MOV R0, [0x2A]
    AND R0, 3
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .div_b_inf
    GOTO .div_b_not_inf
.div_b_inf:
    MOV R0, [0x38]
    CP R0, 0xF
    SKIP Z, 2
    GOTO .sub_zero
    MOV R0, [0x39]
    CP R0, 1
    SKIP Z, 2
    GOTO .sub_zero
    MOV R0, [0x20]
    MOV R1, R0
    MOV R0, [0x21]
    OR R1, R0
    MOV R0, [0x22]
    AND R0, 3
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .nan
    GOTO .sub_zero
.div_b_not_inf:
    MOV R0, [0x38]
    CP R0, 0xF
    SKIP Z, 2
    GOTO .div_check_b_zero
    MOV R0, [0x39]
    CP R0, 1
    SKIP Z, 2
    GOTO .div_check_b_zero
    MOV R0, [0x20]
    MOV R1, R0
    MOV R0, [0x21]
    OR R1, R0
    MOV R0, [0x22]
    AND R0, 3
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .pack_inf
    GOTO .div_check_b_zero
.div_check_b_zero:
    MOV R0, [0x3B]
    MOV R1, R0
    MOV R0, [0x3C]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .div_b_maybe_zero
    GOTO .div_check_a_zero
.div_b_maybe_zero:
    MOV R0, [0x28]
    MOV R1, R0
    MOV R0, [0x29]
    OR R1, R0
    MOV R0, [0x2A]
    AND R0, 3
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP Z, 2
    GOTO .div_check_a_zero
    MOV R0, [0x38]
    MOV R1, R0
    MOV R0, [0x39]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .div_a_maybe_zero
    GOTO .pack_inf
.div_a_maybe_zero:
    MOV R0, [0x20]
    MOV R1, R0
    MOV R0, [0x21]
    OR R1, R0
    MOV R0, [0x22]
    AND R0, 3
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP Z, 2
    GOTO .pack_inf
    GOTO .nan
.div_check_a_zero:
    MOV R0, [0x38]
    MOV R1, R0
    MOV R0, [0x39]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .div_a_zero_check
    GOTO .unpack_a
.div_a_zero_check:
    MOV R0, [0x20]
    MOV R1, R0
    MOV R0, [0x21]
    OR R1, R0
    MOV R0, [0x22]
    AND R0, 3
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP Z, 2
    GOTO .unpack_a
    GOTO .sub_zero
.align:
    MOV R0, [0x3A]
    MOV R1, R0
    MOV R0, [0x3D]
    SUB R1, R0
    SKIP Z, 2
    GOTO .cmp_diff_16
    GOTO .cmp_next_15
.cmp_diff_16:
    SKIP NC, 2
    GOTO .diff_exp
    GOTO .swap
.cmp_next_15:
    MOV R0, [0x39]
    MOV R1, R0
    MOV R0, [0x3C]
    SUB R1, R0
    SKIP Z, 2
    GOTO .cmp_diff_18
    GOTO .cmp_next_17
.cmp_diff_18:
    SKIP NC, 2
    GOTO .diff_exp
    GOTO .swap
.cmp_next_17:
    MOV R0, [0x38]
    MOV R1, R0
    MOV R0, [0x3B]
    SUB R1, R0
    SKIP Z, 2
    GOTO .cmp_diff_20
    GOTO .cmp_next_19
.cmp_diff_20:
    SKIP NC, 2
    GOTO .diff_exp
    GOTO .swap
.cmp_next_19:
    GOTO .diff_exp
.swap:
    MOV R0, [0x20]
    MOV R1, R0
    MOV R0, [0x28]
    MOV [0x20], R0
    MOV R0, R1
    MOV [0x28], R0
    MOV R0, [0x21]
    MOV R1, R0
    MOV R0, [0x29]
    MOV [0x21], R0
    MOV R0, R1
    MOV [0x29], R0
    MOV R0, [0x22]
    MOV R1, R0
    MOV R0, [0x2A]
    MOV [0x22], R0
    MOV R0, R1
    MOV [0x2A], R0
    MOV R0, [0x23]
    MOV R1, R0
    MOV R0, [0x2B]
    MOV [0x23], R0
    MOV R0, R1
    MOV [0x2B], R0
    MOV R0, [0x24]
    MOV R1, R0
    MOV R0, [0x2C]
    MOV [0x24], R0
    MOV R0, R1
    MOV [0x2C], R0
    MOV R0, [0x25]
    MOV R1, R0
    MOV R0, [0x2D]
    MOV [0x25], R0
    MOV R0, R1
    MOV [0x2D], R0
    MOV R0, [0x38]
    MOV R1, R0
    MOV R0, [0x3B]
    MOV [0x38], R0
    MOV R0, R1
    MOV [0x3B], R0
    MOV R0, [0x39]
    MOV R1, R0
    MOV R0, [0x3C]
    MOV [0x39], R0
    MOV R0, R1
    MOV [0x3C], R0
    MOV R0, [0x3A]
    MOV R1, R0
    MOV R0, [0x3D]
    MOV [0x3A], R0
    MOV R0, R1
    MOV [0x3D], R0
    MOV R0, R8
    MOV R8, R9
    MOV R9, R0
.diff_exp:
    MOV R0, [0x38]
    MOV R1, R0
    MOV R0, [0x3B]
    SUB R1, R0
    MOV R0, R1
    MOV [0x3B], R0
    MOV R0, [0x39]
    MOV R1, R0
    MOV R0, [0x3C]
    SBB R1, R0
    MOV R0, R1
    MOV [0x3C], R0
    MOV R0, [0x3A]
    MOV R1, R0
    MOV R0, [0x3D]
    SBB R1, R0
    MOV R0, R1
    MOV [0x3D], R0
    MOV R0, [0x3D]
    CP R0, 0
    SKIP Z, 2
    GOTO .cap_shift
    MOV R0, [0x3C]
    CP R0, 2
    SKIP C, 2
    GOTO .align_loop
    GOTO .cap_shift
.cap_shift:
    MOV R0, 0
    MOV [0x28], R0
    MOV [0x29], R0
    MOV [0x2A], R0
    MOV [0x2B], R0
    MOV [0x2C], R0
    MOV [0x2D], R0
    MOV R0, 1
    MOV [0x36], R0
    GOTO .align_done
.align_loop:
    MOV R0, [0x3B]
    MOV R1, R0
    MOV R0, [0x3C]
    OR R1, R0
    MOV R0, [0x3D]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .align_done
    MOV R0, 0
    ADD R0, 0
    MOV R0, [0x2D]
    RRC R0
    MOV [0x2D], R0
    MOV R0, [0x2C]
    RRC R0
    MOV [0x2C], R0
    MOV R0, [0x2B]
    RRC R0
    MOV [0x2B], R0
    MOV R0, [0x2A]
    RRC R0
    MOV [0x2A], R0
    MOV R0, [0x29]
    RRC R0
    MOV [0x29], R0
    MOV R0, [0x28]
    RRC R0
    MOV [0x28], R0
    MOV R0, 0
    ADC R0, R0
    MOV R1, R0
    MOV R0, [0x36]
    OR R0, R1
    MOV [0x36], R0
    MOV R1, 1
    MOV R0, [0x3B]
    SUB R0, R1
    MOV [0x3B], R0
    MOV R1, 0
    MOV R0, [0x3C]
    SBB R0, R1
    MOV [0x3C], R0
    MOV R1, 0
    MOV R0, [0x3D]
    SBB R0, R1
    MOV [0x3D], R0
    GOTO .align_loop
.align_done:
    MOV R0, R8
    MOV R1, R0
    MOV R0, R9
    SUB R1, R0
    MOV R0, 0
    SKIP Z, 2
    GOTO .mark_sub
    GOTO .mark_done
.mark_sub:
    INC R0
.mark_done:
    MOV [0x37], R0
    MOV R0, R8
    MOV R1, R0
    MOV R0, R9
    SUB R1, R0
    SKIP Z, 2
    GOTO .diff_signs
    GOTO .same_signs
.diff_signs:
    MOV R0, [0x25]
    MOV R1, R0
    MOV R0, [0x2D]
    SUB R1, R0
    SKIP Z, 2
    GOTO .cmp6_diff_22
    GOTO .cmp6_next_21
.cmp6_diff_22:
    SKIP NC, 2
    GOTO .sub_mag
    GOTO .swap_mag
.cmp6_next_21:
    MOV R0, [0x24]
    MOV R1, R0
    MOV R0, [0x2C]
    SUB R1, R0
    SKIP Z, 2
    GOTO .cmp6_diff_24
    GOTO .cmp6_next_23
.cmp6_diff_24:
    SKIP NC, 2
    GOTO .sub_mag
    GOTO .swap_mag
.cmp6_next_23:
    MOV R0, [0x23]
    MOV R1, R0
    MOV R0, [0x2B]
    SUB R1, R0
    SKIP Z, 2
    GOTO .cmp6_diff_26
    GOTO .cmp6_next_25
.cmp6_diff_26:
    SKIP NC, 2
    GOTO .sub_mag
    GOTO .swap_mag
.cmp6_next_25:
    MOV R0, [0x22]
    MOV R1, R0
    MOV R0, [0x2A]
    SUB R1, R0
    SKIP Z, 2
    GOTO .cmp6_diff_28
    GOTO .cmp6_next_27
.cmp6_diff_28:
    SKIP NC, 2
    GOTO .sub_mag
    GOTO .swap_mag
.cmp6_next_27:
    MOV R0, [0x21]
    MOV R1, R0
    MOV R0, [0x29]
    SUB R1, R0
    SKIP Z, 2
    GOTO .cmp6_diff_30
    GOTO .cmp6_next_29
.cmp6_diff_30:
    SKIP NC, 2
    GOTO .sub_mag
    GOTO .swap_mag
.cmp6_next_29:
    MOV R0, [0x20]
    MOV R1, R0
    MOV R0, [0x28]
    SUB R1, R0
    SKIP Z, 2
    GOTO .cmp6_diff_32
    GOTO .cmp6_next_31
.cmp6_diff_32:
    SKIP NC, 2
    GOTO .sub_mag
    GOTO .swap_mag
.cmp6_next_31:
    GOTO .sub_mag
.swap_mag:
    MOV R0, [0x20]
    MOV R1, R0
    MOV R0, [0x28]
    MOV [0x20], R0
    MOV R0, R1
    MOV [0x28], R0
    MOV R0, [0x21]
    MOV R1, R0
    MOV R0, [0x29]
    MOV [0x21], R0
    MOV R0, R1
    MOV [0x29], R0
    MOV R0, [0x22]
    MOV R1, R0
    MOV R0, [0x2A]
    MOV [0x22], R0
    MOV R0, R1
    MOV [0x2A], R0
    MOV R0, [0x23]
    MOV R1, R0
    MOV R0, [0x2B]
    MOV [0x23], R0
    MOV R0, R1
    MOV [0x2B], R0
    MOV R0, [0x24]
    MOV R1, R0
    MOV R0, [0x2C]
    MOV [0x24], R0
    MOV R0, R1
    MOV [0x2C], R0
    MOV R0, [0x25]
    MOV R1, R0
    MOV R0, [0x2D]
    MOV [0x25], R0
    MOV R0, R1
    MOV [0x2D], R0
    MOV R8, R9
.sub_mag:
    MOV R0, [0x20]
    MOV R1, R0
    MOV R0, [0x28]
    SUB R1, R0
    MOV R0, R1
    MOV [0x30], R0
    MOV R0, [0x21]
    MOV R1, R0
    MOV R0, [0x29]
    SBB R1, R0
    MOV R0, R1
    MOV [0x31], R0
    MOV R0, [0x22]
    MOV R1, R0
    MOV R0, [0x2A]
    SBB R1, R0
    MOV R0, R1
    MOV [0x32], R0
    MOV R0, [0x23]
    MOV R1, R0
    MOV R0, [0x2B]
    SBB R1, R0
    MOV R0, R1
    MOV [0x33], R0
    MOV R0, [0x24]
    MOV R1, R0
    MOV R0, [0x2C]
    SBB R1, R0
    MOV R0, R1
    MOV [0x34], R0
    MOV R0, [0x25]
    MOV R1, R0
    MOV R0, [0x2D]
    SBB R1, R0
    MOV R0, R1
    MOV [0x35], R0
    MOV R0, [0x30]
    MOV R1, R0
    MOV R0, [0x31]
    OR R1, R0
    MOV R0, [0x32]
    OR R1, R0
    MOV R0, [0x33]
    OR R1, R0
    MOV R0, [0x34]
    OR R1, R0
    MOV R0, [0x35]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .zero_result
    GOTO .normalize
.zero_result:
    MOV R1, 0
    MOV R2, 0
    MOV R3, 0
    MOV R4, 0
    RET R0, 0
.same_signs:
    MOV R0, [0x20]
    MOV R1, R0
    MOV R0, [0x28]
    ADD R1, R0
    MOV R0, R1
    MOV [0x30], R0
    MOV R0, [0x21]
    MOV R1, R0
    MOV R0, [0x29]
    ADC R1, R0
    MOV R0, R1
    MOV [0x31], R0
    MOV R0, [0x22]
    MOV R1, R0
    MOV R0, [0x2A]
    ADC R1, R0
    MOV R0, R1
    MOV [0x32], R0
    MOV R0, [0x23]
    MOV R1, R0
    MOV R0, [0x2B]
    ADC R1, R0
    MOV R0, R1
    MOV [0x33], R0
    MOV R0, [0x24]
    MOV R1, R0
    MOV R0, [0x2C]
    ADC R1, R0
    MOV R0, R1
    MOV [0x34], R0
    MOV R0, [0x25]
    MOV R1, R0
    MOV R0, [0x2D]
    ADC R1, R0
    MOV R0, R1
    MOV [0x35], R0
    SKIP NC, 2
    GOTO .add_carry
    GOTO .normalize
.add_carry:
    MOV R1, 0
    ADC R1, R1
    MOV R9, R1
    MOV R0, 0
    ADD R0, 0
    MOV R0, [0x35]
    RRC R0
    MOV [0x35], R0
    MOV R0, [0x34]
    RRC R0
    MOV [0x34], R0
    MOV R0, [0x33]
    RRC R0
    MOV [0x33], R0
    MOV R0, [0x32]
    RRC R0
    MOV [0x32], R0
    MOV R0, [0x31]
    RRC R0
    MOV [0x31], R0
    MOV R0, [0x30]
    RRC R0
    MOV [0x30], R0
    MOV R0, 0
    ADC R0, R0
    MOV R1, R0
    MOV R0, [0x36]
    OR R0, R1
    MOV [0x36], R0
    MOV R0, R9
    CP R0, 0
    SKIP Z, 2
    GOTO .set_carry_bit
    GOTO .after_carry_bit
.set_carry_bit:
    MOV R0, [0x35]
    OR R0, 8
    MOV [0x35], R0
.after_carry_bit:
    MOV R1, 1
    MOV R0, [0x38]
    ADD R0, R1
    MOV [0x38], R0
    MOV R1, 0
    MOV R0, [0x39]
    ADC R0, R1
    MOV [0x39], R0
    MOV R1, 0
    MOV R0, [0x3A]
    ADC R0, R1
    MOV [0x3A], R0
    GOTO .normalize
.normalize:
    MOV R0, [0x30]
    MOV R1, R0
    MOV R0, [0x31]
    OR R1, R0
    MOV R0, [0x32]
    OR R1, R0
    MOV R0, [0x33]
    OR R1, R0
    MOV R0, [0x34]
    OR R1, R0
    MOV R0, [0x35]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .zero_result
.norm_33:
    MOV R0, [0x35]
    AND R0, 8
    CP R0, 0
    SKIP Z, 2
    GOTO .norm_done
    MOV R0, [0x30]
    ADD R0, R0
    MOV [0x30], R0
    MOV R0, [0x31]
    ADC R0, R0
    MOV [0x31], R0
    MOV R0, [0x32]
    ADC R0, R0
    MOV [0x32], R0
    MOV R0, [0x33]
    ADC R0, R0
    MOV [0x33], R0
    MOV R0, [0x34]
    ADC R0, R0
    MOV [0x34], R0
    MOV R0, [0x35]
    ADC R0, R0
    MOV [0x35], R0
    MOV R1, 1
    MOV R0, [0x38]
    SUB R0, R1
    MOV [0x38], R0
    MOV R1, 0
    MOV R0, [0x39]
    SBB R0, R1
    MOV [0x39], R0
    MOV R1, 0
    MOV R0, [0x3A]
    SBB R0, R1
    MOV [0x3A], R0
    GOTO .norm_33
.norm_done:
.pack_dispatch:
    MOV R0, [0x3A]
    CP R0, 0
    SKIP Z, 2
    GOTO .high_nonzero
    GOTO .low_range
.high_nonzero:
    CP R0, 1
    SKIP Z, 2
    GOTO .pack_inf
    GOTO .high_one
.high_one:
    MOV R0, [0x39]
    CP R0, 0
    SKIP Z, 2
    GOTO .pack_inf
    GOTO .round_normal
.low_range:
    MOV R0, [0x39]
    CP R0, 0xF
    SKIP C, 2
    GOTO .mid_lt_15
    GOTO .mid_eq_15
.mid_lt_15:
    GOTO .pack_subnormal
.mid_eq_15:
    MOV R0, [0x38]
    CP R0, 2
    SKIP C, 2
    GOTO .pack_subnormal
    GOTO .round_normal
.round_normal:
    MOV R0, [0x33]
    AND R0, 1
    CP R0, 0
    SKIP NZ, 2
    GOTO .normal_clear_tail
    GOTO .normal_round_decision
.normal_round_decision:
    MOV R0, [0x32]
    AND R0, 8
    CP R0, 0
    SKIP NZ, 2
    GOTO .normal_check_sticky
    GOTO .normal_add_round
.normal_check_sticky:
    MOV R0, [0x32]
    AND R0, 7
    MOV R1, R0
    MOV R0, [0x31]
    OR R1, R0
    MOV R0, [0x30]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .normal_check_extra
    GOTO .normal_add_round
.normal_check_extra:
    MOV R0, [0x37]
    CP R0, 0
    SKIP NZ, 2
    GOTO .normal_check_positive_sticky
    GOTO .normal_check_sub_sticky
.normal_check_positive_sticky:
    MOV R0, [0x36]
    CP R0, 0
    SKIP NZ, 2
    GOTO .normal_tie_lsb
    GOTO .normal_add_round
.normal_check_sub_sticky:
    MOV R0, [0x36]
    CP R0, 0
    SKIP Z, 2
    GOTO .normal_clear_tail
    GOTO .normal_tie_lsb
.normal_tie_lsb:
    MOV R0, [0x33]
    AND R0, 2
    CP R0, 0
    SKIP NZ, 2
    GOTO .normal_clear_tail
    GOTO .normal_add_round
.normal_add_round:
    MOV R0, [0x33]
    MOV R1, 2
    ADD R0, R1
    MOV [0x33], R0
    MOV R1, 0
    MOV R0, [0x34]
    ADC R0, R1
    MOV [0x34], R0
    MOV R0, [0x35]
    ADC R0, R1
    MOV [0x35], R0
    SKIP NC, 2
    GOTO .round_overflow
    GOTO .normal_clear_tail
.round_overflow:
    MOV R0, 0
    MOV [0x30], R0
    MOV [0x31], R0
    MOV [0x32], R0
    MOV [0x33], R0
    MOV [0x34], R0
    MOV [0x35], R0
    MOV R0, 8
    MOV [0x35], R0
    MOV R1, 1
    MOV R0, [0x38]
    ADD R0, R1
    MOV [0x38], R0
    MOV R1, 0
    MOV R0, [0x39]
    ADC R0, R1
    MOV [0x39], R0
    MOV R1, 0
    MOV R0, [0x3A]
    ADC R0, R1
    MOV [0x3A], R0
    GOTO .pack_dispatch
.normal_clear_tail:
    MOV R0, 0
    MOV [0x30], R0
    MOV [0x31], R0
    MOV [0x32], R0
    MOV R0, [0x33]
    AND R0, 0xE
    MOV [0x33], R0
    MOV R0, [0x38]
    MOV R1, 1
    SUB R0, R1
    MOV [0x3E], R0
    MOV R0, [0x39]
    MOV R1, 0xF
    SBB R0, R1
    MOV [0x3F], R0
    MOV R0, [0x33]
    ADD R0, 0
    RRC R0
    MOV R2, R0
    MOV R0, [0x34]
    AND R0, 1
    ADD R0, R0
    ADD R0, R0
    ADD R0, R0
    OR R0, R2
    MOV R1, R0
    MOV R0, [0x34]
    ADD R0, 0
    RRC R0
    AND R0, 7
    MOV R3, R0
    MOV R0, [0x35]
    AND R0, 1
    ADD R0, R0
    ADD R0, R0
    ADD R0, R0
    OR R0, R3
    MOV R2, R0
    MOV R0, [0x35]
    ADD R0, 0
    RRC R0
    AND R0, 3
    MOV R3, R0
    MOV R0, [0x3E]
    AND R0, 1
    ADD R0, R0
    ADD R0, R0
    OR R3, R0
    MOV R0, [0x3E]
    AND R0, 2
    ADD R0, R0
    ADD R0, R0
    OR R3, R0
    MOV R0, [0x3E]
    AND R0, 4
    RRC R0
    RRC R0
    MOV R4, R0
    MOV R0, [0x3E]
    AND R0, 8
    RRC R0
    RRC R0
    RRC R0
    ADD R0, R0
    OR R4, R0
    MOV R0, [0x3F]
    AND R0, 1
    ADD R0, R0
    ADD R0, R0
    OR R4, R0
    OR R4, R8
    RET R0, 0
.pack_inf:
    MOV R1, 0
    MOV R2, 0
    MOV R3, 12
    MOV R0, R8
    MOV R1, 7
    OR R1, R0
    MOV R4, R1
    MOV R1, 0
    MOV R2, 0
    MOV R3, 12
    RET R0, 0
.pack_subnormal:
    MOV R0, [0x38]
    MOV R1, R0
    MOV R0, 0xF
    SUB R0, R1
    MOV [0x3B], R0
    MOV R0, [0x39]
    MOV R1, R0
    MOV R0, 0xF
    SBB R0, R1
    MOV [0x3C], R0
    MOV R0, [0x3A]
    MOV R1, R0
    MOV R0, 0
    SBB R0, R1
    MOV [0x3D], R0
    MOV R0, [0x3D]
    CP R0, 0
    SKIP Z, 2
    GOTO .sub_zero
    MOV R0, [0x3C]
    CP R0, 2
    SKIP C, 2
    GOTO .sub_shift_start
    GOTO .sub_mid_ge2
.sub_mid_ge2:
    CP R0, 2
    SKIP Z, 2
    GOTO .sub_zero
    GOTO .sub_check_k32
.sub_check_k32:
    MOV R0, [0x3B]
    CP R0, 0
    SKIP Z, 2
    GOTO .sub_zero
    GOTO .sub_shift_start
.sub_shift_start:
    MOV R6, 0
    MOV R0, [0x37]
    CP R0, 0
    SKIP NZ, 2
    GOTO .sub_add_sticky
    GOTO .sub_sticky_done
.sub_add_sticky:
    MOV R0, [0x36]
    MOV R6, R0
.sub_sticky_done:
    MOV R1, 1
    MOV R0, [0x3B]
    SUB R0, R1
    MOV [0x3B], R0
    MOV R1, 0
    MOV R0, [0x3C]
    SBB R0, R1
    MOV [0x3C], R0
    MOV R1, 0
    MOV R0, [0x3D]
    SBB R0, R1
    MOV [0x3D], R0
.sub_loop_34:
    MOV R0, [0x3B]
    MOV R1, R0
    MOV R0, [0x3C]
    OR R1, R0
    MOV R0, [0x3D]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .sub_guard_35
    MOV R0, [0x30]
    AND R0, 1
    MOV R1, R0
    MOV R0, R6
    OR R0, R1
    MOV R6, R0
    MOV R0, 0
    ADD R0, 0
    MOV R0, [0x35]
    RRC R0
    MOV [0x35], R0
    MOV R0, [0x34]
    RRC R0
    MOV [0x34], R0
    MOV R0, [0x33]
    RRC R0
    MOV [0x33], R0
    MOV R0, [0x32]
    RRC R0
    MOV [0x32], R0
    MOV R0, [0x31]
    RRC R0
    MOV [0x31], R0
    MOV R0, [0x30]
    RRC R0
    MOV [0x30], R0
    MOV R1, 1
    MOV R0, [0x3B]
    SUB R0, R1
    MOV [0x3B], R0
    MOV R1, 0
    MOV R0, [0x3C]
    SBB R0, R1
    MOV [0x3C], R0
    MOV R1, 0
    MOV R0, [0x3D]
    SBB R0, R1
    MOV [0x3D], R0
    GOTO .sub_loop_34
.sub_guard_35:
    MOV R0, [0x30]
    AND R0, 1
    MOV R7, R0
    MOV R0, 0
    ADD R0, 0
    MOV R0, [0x35]
    RRC R0
    MOV [0x35], R0
    MOV R0, [0x34]
    RRC R0
    MOV [0x34], R0
    MOV R0, [0x33]
    RRC R0
    MOV [0x33], R0
    MOV R0, [0x32]
    RRC R0
    MOV [0x32], R0
    MOV R0, [0x31]
    RRC R0
    MOV [0x31], R0
    MOV R0, [0x30]
    RRC R0
    MOV [0x30], R0
    MOV R0, R7
    CP R0, 0
    SKIP NZ, 2
    GOTO .sub_pack
    GOTO .sub_round_check
.sub_round_check:
    MOV R0, R6
    CP R0, 0
    SKIP NZ, 2
    GOTO .sub_round_tie
    GOTO .sub_round_up
.sub_round_tie:
    MOV R0, [0x37]
    CP R0, 0
    SKIP NZ, 2
    GOTO .sub_tie_lsb
    GOTO .sub_check_sub_sticky
.sub_check_sub_sticky:
    MOV R0, [0x36]
    CP R0, 0
    SKIP Z, 2
    GOTO .sub_pack
    GOTO .sub_tie_lsb
.sub_tie_lsb:
    MOV R0, [0x30]
    AND R0, 1
    CP R0, 0
    SKIP NZ, 2
    GOTO .sub_pack
    GOTO .sub_round_up
.sub_round_up:
    MOV R1, 1
    MOV R0, [0x30]
    ADD R0, R1
    MOV [0x30], R0
    MOV R1, 0
    MOV R0, [0x31]
    ADC R0, R1
    MOV [0x31], R0
    MOV R0, [0x32]
    ADC R0, R1
    MOV [0x32], R0
.sub_pack:
    MOV R0, [0x32]
    AND R0, 4
    CP R0, 0
    SKIP Z, 2
    GOTO .sub_smallest_normal
    GOTO .sub_pack_fraction
.sub_smallest_normal:
    MOV R1, 0
    MOV R2, 0
    MOV R3, 4
    MOV R4, R8
    RET R0, 0
.sub_pack_fraction:
    MOV R0, [0x30]
    MOV R1, R0
    MOV R0, [0x31]
    MOV R2, R0
    MOV R0, [0x32]
    AND R0, 3
    MOV R3, R0
    MOV R4, R8
    RET R0, 0
.sub_zero:
    MOV R1, 0
    MOV R2, 0
    MOV R3, 0
    MOV R4, R8
    RET R0, 0
.nan:
    MOV R1, 0
    MOV R2, 0
    MOV R3, 14
    MOV R4, 7
    RET R0, 0
.return_a:
    MOV R0, [0x20]
    MOV R1, R0
    MOV R0, [0x21]
    MOV R2, R0
    MOV R0, [0x22]
    MOV R3, R0
    MOV R0, [0x23]
    MOV R4, R0
    RET R0, 0
.return_b:
    MOV R0, [0x28]
    MOV R1, R0
    MOV R0, [0x29]
    MOV R2, R0
    MOV R0, [0x2A]
    MOV R3, R0
    MOV R0, [0x2B]
    MOV R4, R0
    RET R0, 0


fn___nib_f16_to_f32:
    MOV R0, [${a+0}]
    MOV [0x20], R0
    MOV R0, [${a+1}]
    MOV [0x21], R0
    MOV R0, [${a+2}]
    MOV [0x22], R0
    MOV R0, [${a+3}]
    MOV [0x23], R0
    MOV R0, [0x23]
    AND R0, 8
    MOV [0x24], R0
    MOV R0, [0x23]
    AND R0, 7
    ADD R0, R0
    ADD R0, R0
    MOV R2, R0
    MOV R0, [0x22]
    AND R0, 12
    ADD R0, 0
    RRC R0
    ADD R0, 0
    RRC R0
    OR R2, R0
    MOV R0, R2
    MOV [0x25], R0
    MOV R0, [0x23]
    AND R0, 4
    ADD R0, 0
    RRC R0
    ADD R0, 0
    RRC R0
    MOV [0x26], R0
    MOV R0, [0x20]
    MOV [0x29], R0
    MOV R0, [0x21]
    MOV [0x2A], R0
    MOV R0, [0x22]
    AND R0, 3
    MOV [0x2B], R0
    MOV R0, [0x25]
    MOV R1, R0
    MOV R0, [0x26]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .h2f_z_1
    GOTO .h2f_nz_2
.h2f_z_1:
    MOV R0, [0x29]
    MOV R1, R0
    MOV R0, [0x2A]
    OR R1, R0
    MOV R0, [0x2B]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .h2f_zz_3
    GOTO .h2f_sub_4
.h2f_zz_3:
    MOV R1, 0
    MOV R2, 0
    MOV R3, 0
    MOV R4, 0
    MOV R5, 0
    MOV R6, 0
    MOV R7, 0
    MOV R8, 0
    MOV R0, [0x24]
    MOV R8, R0
    RET R0, 0
.h2f_sub_4:
    MOV R0, 0
    MOV [0x2D], R0
    MOV R0, 0
    MOV [0x27], R0
    MOV R0, 7
    MOV [0x28], R0
.h2f_subloop_5:
    MOV R0, [0x2B]
    AND R0, 2
    CP R0, 0
    SKIP NZ, 2
    GOTO .h2f_subsh_7
    GOTO .h2f_subdone_6
.h2f_subsh_7:
    MOV R0, [0x29]
    ADD R0, R0
    MOV [0x29], R0
    MOV R0, [0x2A]
    ADC R0, R0
    MOV [0x2A], R0
    MOV R0, [0x2B]
    ADC R0, R0
    MOV [0x2B], R0
    MOV R1, 1
    MOV R0, [0x2D]
    ADD R0, R1
    MOV [0x2D], R0
    MOV R1, 1
    MOV R0, [0x27]
    SUB R0, R1
    MOV [0x27], R0
    MOV R1, 0
    MOV R0, [0x28]
    SBB R0, R1
    MOV [0x28], R0
    GOTO .h2f_subloop_5
.h2f_subdone_6:
    MOV R0, 14
    MOV [0x2C], R0
    GOTO .h2f_pack_8
.h2f_nz_2:
    MOV R0, [0x26]
    CP R0, 1
    SKIP Z, 2
    GOTO .h2f_ni_10
    GOTO .h2f_inf_9
.h2f_inf_9:
    MOV R0, [0x25]
    CP R0, 15
    SKIP Z, 2
    GOTO .h2f_ni_10
    GOTO .h2f_isz_11
.h2f_isz_11:
    MOV R0, [0x29]
    MOV R1, R0
    MOV R0, [0x2A]
    OR R1, R0
    MOV R0, [0x2B]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP Z, 2
    GOTO .h2f_nan_12
    GOTO .h2f_infres_13
.h2f_infres_13:
    MOV R1, 0
    MOV R2, 0
    MOV R3, 0
    MOV R4, 0
    MOV R5, 0
    MOV R6, 0
    MOV R7, 0
    MOV R8, 0
    MOV R6, 8
    MOV R7, 15
    MOV R0, [0x24]
    OR R0, 7
    MOV R8, R0
    RET R0, 0
.h2f_nan_12:
    MOV R1, 0
    MOV R2, 0
    MOV R3, 0
    MOV R4, 0
    MOV R5, 0
    MOV R6, 12
    MOV R7, 15
    MOV R8, 7
    RET R0, 0
.h2f_ni_10:
    MOV R0, [0x2B]
    OR R0, 4
    MOV [0x2B], R0
    MOV R0, 0
    MOV [0x27], R0
    MOV R0, 7
    MOV [0x28], R0
    MOV R0, [0x25]
    MOV R1, R0
    MOV R0, [0x27]
    ADD R0, R1
    MOV [0x27], R0
    MOV R0, [0x26]
    MOV R1, R0
    MOV R0, [0x28]
    ADC R0, R1
    MOV [0x28], R0
    MOV R0, 13
    MOV [0x2C], R0
    GOTO .h2f_pack_8
.h2f_pack_8:
    MOV R0, 0
    MOV [0x30], R0
    MOV [0x31], R0
    MOV [0x32], R0
    MOV [0x33], R0
    MOV [0x34], R0
    MOV [0x35], R0
    MOV [0x36], R0
    MOV [0x37], R0
    MOV R0, [0x29]
    MOV [0x30], R0
    MOV R0, [0x2A]
    MOV [0x31], R0
    MOV R0, [0x2B]
    MOV [0x32], R0
.h2f_shl_14:
    MOV R0, [0x2C]
    CP R0, 0
    SKIP NZ, 2
    GOTO .h2f_shld_15
    GOTO .h2f_shb_16
.h2f_shb_16:
    MOV R0, [0x30]
    ADD R0, R0
    MOV [0x30], R0
    MOV R0, [0x31]
    ADC R0, R0
    MOV [0x31], R0
    MOV R0, [0x32]
    ADC R0, R0
    MOV [0x32], R0
    MOV R0, [0x33]
    ADC R0, R0
    MOV [0x33], R0
    MOV R0, [0x34]
    ADC R0, R0
    MOV [0x34], R0
    MOV R0, [0x35]
    ADC R0, R0
    MOV [0x35], R0
    MOV R0, [0x36]
    ADC R0, R0
    MOV [0x36], R0
    MOV R0, [0x37]
    ADC R0, R0
    MOV [0x37], R0
    MOV R1, 1
    MOV R0, [0x2C]
    SUB R0, R1
    MOV [0x2C], R0
    GOTO .h2f_shl_14
.h2f_shld_15:
    MOV R0, [0x35]
    AND R0, 7
    MOV [0x35], R0
    MOV R0, [0x27]
    AND R0, 1
    ADD R0, R0
    ADD R0, R0
    ADD R0, R0
    MOV R1, R0
    MOV R0, [0x35]
    OR R0, R1
    MOV [0x35], R0
    MOV R0, [0x27]
    ADD R0, 0
    RRC R0
    AND R0, 7
    MOV R1, R0
    MOV R0, [0x28]
    AND R0, 1
    ADD R0, R0
    ADD R0, R0
    ADD R0, R0
    OR R1, R0
    MOV R0, [0x36]
    OR R0, R1
    MOV [0x36], R0
    MOV R0, [0x28]
    ADD R0, 0
    RRC R0
    AND R0, 7
    MOV R1, R0
    MOV R0, [0x24]
    OR R1, R0
    MOV R0, [0x37]
    OR R0, R1
    MOV [0x37], R0
    MOV R0, [0x30]
    MOV R1, R0
    MOV R0, [0x31]
    MOV R2, R0
    MOV R0, [0x32]
    MOV R3, R0
    MOV R0, [0x33]
    MOV R4, R0
    MOV R0, [0x34]
    MOV R5, R0
    MOV R0, [0x35]
    MOV R6, R0
    MOV R0, [0x36]
    MOV R7, R0
    MOV R0, [0x37]
    MOV R8, R0
    RET R0, 0
fn___nib_f32_to_f16:
    MOV R0, [${a+0}]
    MOV [0x20], R0
    MOV R0, [${a+1}]
    MOV [0x21], R0
    MOV R0, [${a+2}]
    MOV [0x22], R0
    MOV R0, [${a+3}]
    MOV [0x23], R0
    MOV R0, [${a+4}]
    MOV [0x24], R0
    MOV R0, [${a+5}]
    MOV [0x25], R0
    MOV R0, [${a+6}]
    MOV [0x26], R0
    MOV R0, [${a+7}]
    MOV [0x27], R0
    MOV R0, [0x27]
    AND R0, 8
    MOV [0x28], R0
    MOV R0, [0x25]
    AND R0, 8
    MOV R2, R0
    MOV R0, 0
    ADD R0, 0
    RRC R2
    RRC R2
    RRC R2
    MOV R0, [0x26]
    AND R0, 7
    ADD R0, R0
    OR R2, R0
    MOV R0, R2
    MOV [0x29], R0
    MOV R0, [0x26]
    AND R0, 8
    MOV R2, R0
    MOV R0, 0
    ADD R0, 0
    RRC R2
    RRC R2
    RRC R2
    MOV R0, [0x27]
    AND R0, 7
    ADD R0, R0
    OR R2, R0
    MOV R0, R2
    MOV [0x2A], R0
    MOV R0, [0x29]
    MOV R1, R0
    MOV R0, [0x2A]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .f2h_z_20
    GOTO .f2h_nz_21
.f2h_z_20:
    MOV R0, 0
    MOV [0x39], R0
    MOV [0x3A], R0
    MOV [0x3B], R0
    MOV R0, [0x28]
    MOV [0x3C], R0
    MOV R0, [0x39]
    MOV R1, R0
    MOV R0, [0x3A]
    MOV R2, R0
    MOV R0, [0x3B]
    MOV R3, R0
    MOV R0, [0x3C]
    MOV R4, R0
    RET R0, 0
.f2h_nz_21:
    MOV R0, [0x2A]
    CP R0, 15
    SKIP Z, 2
    GOTO .f2h_ni_23
    GOTO .f2h_inf_22
.f2h_inf_22:
    MOV R0, [0x29]
    CP R0, 15
    SKIP Z, 2
    GOTO .f2h_ni_23
    GOTO .f2h_isz_24
.f2h_isz_24:
    MOV R0, [0x20]
    MOV R1, R0
    MOV R0, [0x21]
    OR R1, R0
    MOV R0, [0x22]
    OR R1, R0
    MOV R0, [0x23]
    OR R1, R0
    MOV R0, [0x24]
    OR R1, R0
    MOV R0, [0x25]
    AND R0, 7
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP Z, 2
    GOTO .f2h_nan_25
    GOTO .f2h_infr_26
.f2h_infr_26:
    MOV R1, 0
    MOV R2, 0
    MOV R3, 12
    MOV R0, [0x28]
    OR R0, 7
    MOV R4, R0
    RET R0, 0
.f2h_nan_25:
    MOV R1, 0
    MOV R2, 0
    MOV R3, 14
    MOV R4, 7
    RET R0, 0
.f2h_ni_23:
    MOV R1, 15
    MOV R0, [0x29]
    SUB R0, R1
    MOV [0x2B], R0
    MOV R1, 7
    MOV R0, [0x2A]
    SBB R0, R1
    MOV [0x2C], R0
    MOV R0, [0x2C]
    AND R0, 8
    CP R0, 0
    SKIP Z, 2
    GOTO .f2h_neg_27
    GOTO .f2h_pos_28
.f2h_neg_27:
    MOV R0, [0x2C]
    CP R0, 15
    SKIP Z, 2
    GOTO .f2h_sub_30
    MOV R0, [0x2B]
    CP R0, 2
    SKIP NC, 2
    GOTO .f2h_normal_29
    GOTO .f2h_sub_30
.f2h_pos_28:
    MOV R0, [0x2C]
    CP R0, 0
    SKIP Z, 2
    GOTO .f2h_infr_26
    GOTO .f2h_normal_29
.f2h_normal_29:
    MOV R0, 0
    MOV [0x30], R0
    MOV [0x31], R0
    MOV [0x32], R0
    MOV [0x33], R0
    MOV [0x34], R0
    MOV [0x35], R0
    MOV R0, [0x20]
    MOV [0x30], R0
    MOV R0, [0x21]
    MOV [0x31], R0
    MOV R0, [0x22]
    MOV [0x32], R0
    MOV R0, [0x23]
    MOV [0x33], R0
    MOV R0, [0x24]
    MOV [0x34], R0
    MOV R0, [0x25]
    AND R0, 7
    OR R0, 8
    MOV [0x35], R0
    MOV R0, [0x33]
    AND R0, 1
    MOV [0x3D], R0
    MOV R0, [0x32]
    AND R0, 8
    MOV [0x3E], R0
    MOV R0, [0x32]
    AND R0, 7
    MOV R1, R0
    MOV R0, [0x31]
    OR R1, R0
    MOV R0, [0x30]
    OR R1, R0
    MOV R0, R1
    MOV [0x3F], R0
    MOV R0, 13
    MOV [0x36], R0
    MOV R0, 0
    MOV [0x37], R0
.f2h_shr_31:
    MOV R0, [0x36]
    MOV R1, R0
    MOV R0, [0x37]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .f2h_shrd_32
    GOTO .f2h_shrb_33
.f2h_shrb_33:
    MOV R0, 0
    ADD R0, 0
    MOV R0, [0x35]
    RRC R0
    MOV [0x35], R0
    MOV R0, [0x34]
    RRC R0
    MOV [0x34], R0
    MOV R0, [0x33]
    RRC R0
    MOV [0x33], R0
    MOV R0, [0x32]
    RRC R0
    MOV [0x32], R0
    MOV R0, [0x31]
    RRC R0
    MOV [0x31], R0
    MOV R0, [0x30]
    RRC R0
    MOV [0x30], R0
    MOV R1, 1
    MOV R0, [0x36]
    SUB R0, R1
    MOV [0x36], R0
    MOV R1, 0
    MOV R0, [0x37]
    SBB R0, R1
    MOV [0x37], R0
    GOTO .f2h_shr_31
.f2h_shrd_32:
    MOV R0, [0x3D]
    CP R0, 0
    SKIP Z, 2
    GOTO .rnorm_chk_35
    GOTO .rnorm_no_34
.rnorm_chk_35:
    MOV R0, [0x3E]
    CP R0, 0
    SKIP Z, 2
    GOTO .rnorm_up_38
    GOTO .rnorm_stk_36
.rnorm_stk_36:
    MOV R0, [0x3F]
    CP R0, 0
    SKIP Z, 2
    GOTO .rnorm_up_38
    GOTO .rnorm_lsb_37
.rnorm_lsb_37:
    MOV R0, [0x30]
    AND R0, 1
    CP R0, 0
    SKIP Z, 2
    GOTO .rnorm_up_38
    GOTO .rnorm_no_34
.rnorm_up_38:
    MOV R1, 1
    MOV R0, [0x30]
    ADD R0, R1
    MOV [0x30], R0
    MOV R1, 0
    MOV R0, [0x31]
    ADC R0, R1
    MOV [0x31], R0
    MOV R1, 0
    MOV R0, [0x32]
    ADC R0, R1
    MOV [0x32], R0
    MOV R0, [0x32]
    AND R0, 8
    CP R0, 0
    SKIP Z, 2
    GOTO .rnorm_ov_39
    GOTO .rnorm_af_40
.rnorm_ov_39:
    MOV R0, 0
    ADD R0, 0
    MOV R0, [0x32]
    RRC R0
    MOV [0x32], R0
    MOV R0, [0x31]
    RRC R0
    MOV [0x31], R0
    MOV R0, [0x30]
    RRC R0
    MOV [0x30], R0
    MOV R1, 1
    MOV R0, [0x2B]
    ADD R0, R1
    MOV [0x2B], R0
    MOV R1, 0
    MOV R0, [0x2C]
    ADC R0, R1
    MOV [0x2C], R0
.rnorm_af_40:
.rnorm_no_34:
    MOV R1, 15
    MOV R0, [0x2B]
    ADD R0, R1
    MOV [0x3D], R0
    MOV R1, 0
    MOV R0, [0x2C]
    ADC R0, R1
    MOV [0x3E], R0
    MOV R0, [0x30]
    MOV [0x39], R0
    MOV R0, [0x31]
    MOV [0x3A], R0
    MOV R0, [0x32]
    AND R0, 3
    MOV R1, R0
    MOV R0, [0x3D]
    AND R0, 3
    ADD R0, R0
    ADD R0, R0
    OR R1, R0
    MOV R0, R1
    MOV [0x3B], R0
    MOV R0, [0x3D]
    ADD R0, 0
    RRC R0
    ADD R0, 0
    RRC R0
    AND R0, 3
    MOV R1, R0
    MOV R0, [0x3E]
    AND R0, 1
    ADD R0, R0
    ADD R0, R0
    OR R1, R0
    MOV R0, [0x28]
    OR R1, R0
    MOV R0, R1
    MOV [0x3C], R0
    MOV R0, [0x39]
    MOV R1, R0
    MOV R0, [0x3A]
    MOV R2, R0
    MOV R0, [0x3B]
    MOV R3, R0
    MOV R0, [0x3C]
    MOV R4, R0
    RET R0, 0
.f2h_sub_30:
    MOV R0, [0x2B]
    MOV R1, R0
    MOV R0, 0
    SUB R0, R1
    MOV [0x36], R0
    MOV R0, [0x2C]
    MOV R1, R0
    MOV R0, 0
    SBB R0, R1
    MOV [0x37], R0
    MOV R1, 1
    MOV R0, [0x36]
    SUB R0, R1
    MOV [0x36], R0
    MOV R1, 0
    MOV R0, [0x37]
    SBB R0, R1
    MOV [0x37], R0
    MOV R0, [0x37]
    CP R0, 1
    SKIP Z, 2
    GOTO .f2h_hn1_42
    GOTO .f2h_h1_41
.f2h_hn1_42:
    CP R0, 0
    SKIP Z, 2
    GOTO .f2h_zerores_19
    GOTO .f2h_subok_17
.f2h_h1_41:
    MOV R0, [0x36]
    CP R0, 9
    SKIP NC, 2
    GOTO .f2h_zerores_19
    GOTO .f2h_subok_17
.f2h_subok_17:
    MOV R0, 0
    MOV [0x30], R0
    MOV [0x31], R0
    MOV [0x32], R0
    MOV [0x33], R0
    MOV [0x34], R0
    MOV [0x35], R0
    MOV R0, [0x20]
    MOV [0x30], R0
    MOV R0, [0x21]
    MOV [0x31], R0
    MOV R0, [0x22]
    MOV [0x32], R0
    MOV R0, [0x23]
    MOV [0x33], R0
    MOV R0, [0x24]
    MOV [0x34], R0
    MOV R0, [0x25]
    AND R0, 7
    OR R0, 8
    MOV [0x35], R0
    MOV R0, [0x36]
    MOV R1, 2
    SUB R0, R1
    MOV [0x36], R0
    MOV R1, 0
    MOV R0, [0x37]
    SBB R0, R1
    MOV [0x37], R0
    MOV R0, 0
    MOV [0x38], R0
.f2h_il_43:
    MOV R0, [0x36]
    MOV R1, R0
    MOV R0, [0x37]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .f2h_idn_44
    GOTO .f2h_ib_45
.f2h_ib_45:
    MOV R0, 0
    ADD R0, 0
    MOV R0, [0x35]
    RRC R0
    MOV [0x35], R0
    MOV R0, [0x34]
    RRC R0
    MOV [0x34], R0
    MOV R0, [0x33]
    RRC R0
    MOV [0x33], R0
    MOV R0, [0x32]
    RRC R0
    MOV [0x32], R0
    MOV R0, [0x31]
    RRC R0
    MOV [0x31], R0
    MOV R0, [0x30]
    RRC R0
    MOV [0x30], R0
    MOV R0, 0
    ADC R0, R0
    MOV R1, R0
    MOV R0, [0x38]
    OR R0, R1
    MOV [0x38], R0
    MOV R1, 1
    MOV R0, [0x36]
    SUB R0, R1
    MOV [0x36], R0
    MOV R1, 0
    MOV R0, [0x37]
    SBB R0, R1
    MOV [0x37], R0
    GOTO .f2h_il_43
.f2h_idn_44:
    MOV R0, [0x30]
    AND R0, 2
    MOV [0x3D], R0
    MOV R0, [0x30]
    AND R0, 1
    MOV [0x3E], R0
    MOV R0, [0x38]
    MOV [0x3F], R0
    MOV R0, 0
    ADD R0, 0
    MOV R0, [0x32]
    RRC R0
    MOV [0x32], R0
    MOV R0, [0x31]
    RRC R0
    MOV [0x31], R0
    MOV R0, [0x30]
    RRC R0
    MOV [0x30], R0
    MOV R0, 0
    ADD R0, 0
    MOV R0, [0x32]
    RRC R0
    MOV [0x32], R0
    MOV R0, [0x31]
    RRC R0
    MOV [0x31], R0
    MOV R0, [0x30]
    RRC R0
    MOV [0x30], R0
    MOV R0, [0x3D]
    CP R0, 0
    SKIP Z, 2
    GOTO .rnorm_chk_47
    GOTO .rnorm_no_46
.rnorm_chk_47:
    MOV R0, [0x3E]
    CP R0, 0
    SKIP Z, 2
    GOTO .rnorm_up_50
    GOTO .rnorm_stk_48
.rnorm_stk_48:
    MOV R0, [0x3F]
    CP R0, 0
    SKIP Z, 2
    GOTO .rnorm_up_50
    GOTO .rnorm_lsb_49
.rnorm_lsb_49:
    MOV R0, [0x30]
    AND R0, 1
    CP R0, 0
    SKIP Z, 2
    GOTO .rnorm_up_50
    GOTO .rnorm_no_46
.rnorm_up_50:
    MOV R1, 1
    MOV R0, [0x30]
    ADD R0, R1
    MOV [0x30], R0
    MOV R1, 0
    MOV R0, [0x31]
    ADC R0, R1
    MOV [0x31], R0
    MOV R1, 0
    MOV R0, [0x32]
    ADC R0, R1
    MOV [0x32], R0
    MOV R0, [0x32]
    AND R0, 8
    CP R0, 0
    SKIP Z, 2
    GOTO .rnorm_ov_51
    GOTO .rnorm_af_52
.rnorm_ov_51:
    MOV R0, 0
    ADD R0, 0
    MOV R0, [0x32]
    RRC R0
    MOV [0x32], R0
    MOV R0, [0x31]
    RRC R0
    MOV [0x31], R0
    MOV R0, [0x30]
    RRC R0
    MOV [0x30], R0
    MOV R1, 1
    MOV R0, [0x2B]
    ADD R0, R1
    MOV [0x2B], R0
    MOV R1, 0
    MOV R0, [0x2C]
    ADC R0, R1
    MOV [0x2C], R0
.rnorm_af_52:
.rnorm_no_46:
    MOV R0, [0x32]
    AND R0, 4
    CP R0, 0
    SKIP Z, 2
    GOTO .f2h_smallnorm_18
    MOV R0, [0x30]
    MOV [0x39], R0
    MOV R0, [0x31]
    MOV [0x3A], R0
    MOV R0, [0x32]
    AND R0, 3
    MOV [0x3B], R0
    MOV R0, [0x28]
    MOV [0x3C], R0
    MOV R0, [0x39]
    MOV R1, R0
    MOV R0, [0x3A]
    MOV R2, R0
    MOV R0, [0x3B]
    MOV R3, R0
    MOV R0, [0x3C]
    MOV R4, R0
    RET R0, 0
.f2h_smallnorm_18:
    MOV R1, 0
    MOV R2, 0
    MOV R3, 4
    MOV R0, [0x28]
    MOV R4, R0
    RET R0, 0
.f2h_zerores_19:
    MOV R1, 0
    MOV R2, 0
    MOV R3, 0
    MOV R0, [0x28]
    MOV R4, R0
    RET R0, 0

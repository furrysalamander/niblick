; Accurate binary32 add, subtract, multiply, and divide
; (round-to-nearest-even).
;
; Scratch: 0x20..0x27 A, 0x28..0x2F B, 0x30..0x37 result,
; 0x38 sticky, 0x39..0x3B exp A, 0x3C..0x3E exp B,
; 0x3F mode (0 add/sub, 1 multiply, 2 divide).

fn___bc_f32_add:
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
    MOV R0, [${b+0}]
    MOV [0x28], R0
    MOV R0, [${b+1}]
    MOV [0x29], R0
    MOV R0, [${b+2}]
    MOV [0x2A], R0
    MOV R0, [${b+3}]
    MOV [0x2B], R0
    MOV R0, [${b+4}]
    MOV [0x2C], R0
    MOV R0, [${b+5}]
    MOV [0x2D], R0
    MOV R0, [${b+6}]
    MOV [0x2E], R0
    MOV R0, [${b+7}]
    MOV [0x2F], R0
    MOV R0, 0
    MOV [0x3F], R0
    GOTO fn___bc_f32_core

fn___bc_f32_sub:
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
    MOV R0, [${b+0}]
    MOV [0x28], R0
    MOV R0, [${b+1}]
    MOV [0x29], R0
    MOV R0, [${b+2}]
    MOV [0x2A], R0
    MOV R0, [${b+3}]
    MOV [0x2B], R0
    MOV R0, [${b+4}]
    MOV [0x2C], R0
    MOV R0, [${b+5}]
    MOV [0x2D], R0
    MOV R0, [${b+6}]
    MOV [0x2E], R0
    MOV R0, [${b+7}]
    MOV [0x2F], R0
    MOV R0, [0x2F]
    XOR R0, 8
    MOV [0x2F], R0
    MOV R0, 0
    MOV [0x3F], R0
    GOTO fn___bc_f32_core

fn___bc_f32_mul:
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
    MOV R0, [${b+0}]
    MOV [0x28], R0
    MOV R0, [${b+1}]
    MOV [0x29], R0
    MOV R0, [${b+2}]
    MOV [0x2A], R0
    MOV R0, [${b+3}]
    MOV [0x2B], R0
    MOV R0, [${b+4}]
    MOV [0x2C], R0
    MOV R0, [${b+5}]
    MOV [0x2D], R0
    MOV R0, [${b+6}]
    MOV [0x2E], R0
    MOV R0, [${b+7}]
    MOV [0x2F], R0
    MOV R0, 1
    MOV [0x3F], R0
    GOTO fn___bc_f32_core

fn___bc_f32_div:
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
    MOV R0, [${b+0}]
    MOV [0x28], R0
    MOV R0, [${b+1}]
    MOV [0x29], R0
    MOV R0, [${b+2}]
    MOV [0x2A], R0
    MOV R0, [${b+3}]
    MOV [0x2B], R0
    MOV R0, [${b+4}]
    MOV [0x2C], R0
    MOV R0, [${b+5}]
    MOV [0x2D], R0
    MOV R0, [${b+6}]
    MOV [0x2E], R0
    MOV R0, [${b+7}]
    MOV [0x2F], R0
    MOV R0, 2
    MOV [0x3F], R0
    GOTO fn___bc_f32_core

fn___bc_f32_core:
    MOV R0, [0x27]
    AND R0, 8
    MOV R8, R0
    MOV R0, [0x2F]
    AND R0, 8
    MOV R9, R0
    MOV R0, [0x25]
    MOV R2, R0
    MOV R0, R2
    AND R0, 8
    MOV R2, R0
    MOV R0, 0
    ADD R0, 0
    RRC R2
    RRC R2
    RRC R2
    MOV R0, [0x26]
    MOV R3, R0
    MOV R0, R3
    AND R0, 7
    MOV R3, R0
    ADD R3, R3
    OR R2, R3
    MOV R0, R2
    MOV [0x39], R0
    MOV R0, [0x26]
    MOV R2, R0
    MOV R0, R2
    AND R0, 8
    MOV R2, R0
    MOV R0, 0
    ADD R0, 0
    RRC R2
    RRC R2
    RRC R2
    MOV R0, [0x27]
    MOV R3, R0
    MOV R0, R3
    AND R0, 7
    MOV R3, R0
    ADD R3, R3
    OR R2, R3
    MOV R0, R2
    MOV [0x3A], R0
    MOV R0, 0
    MOV [0x3B], R0
    MOV R0, [0x2D]
    MOV R2, R0
    MOV R0, R2
    AND R0, 8
    MOV R2, R0
    MOV R0, 0
    ADD R0, 0
    RRC R2
    RRC R2
    RRC R2
    MOV R0, [0x2E]
    MOV R3, R0
    MOV R0, R3
    AND R0, 7
    MOV R3, R0
    ADD R3, R3
    OR R2, R3
    MOV R0, R2
    MOV [0x3C], R0
    MOV R0, [0x2E]
    MOV R2, R0
    MOV R0, R2
    AND R0, 8
    MOV R2, R0
    MOV R0, 0
    ADD R0, 0
    RRC R2
    RRC R2
    RRC R2
    MOV R0, [0x2F]
    MOV R3, R0
    MOV R0, R3
    AND R0, 7
    MOV R3, R0
    ADD R3, R3
    OR R2, R3
    MOV R0, R2
    MOV [0x3D], R0
    MOV R0, 0
    MOV [0x3E], R0
; @badgec-f32: dispatch-begin
    MOV R0, [0x3F]
    CP R0, 1
    SKIP Z, 2
    GOTO .mode_not_mul
    GOTO .mul_special
.mode_not_mul:
    CP R0, 2
    SKIP Z, 2
    GOTO .mode_add
    GOTO .div_special
.mode_add:
; @badgec-f32: dispatch-end
    MOV R0, [0x39]
    CP R0, 0xF
    SKIP NZ, 2
    GOTO .check_a_hi
    GOTO .check_b_special
.check_a_hi:
    MOV R0, [0x3A]
    CP R0, 0xF
    SKIP NZ, 2
    GOTO .a_special
    GOTO .check_b_special
.a_special:
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
    GOTO .nan
    GOTO .a_inf
.a_inf:
    MOV R0, [0x3C]
    CP R0, 0xF
    SKIP NZ, 2
    GOTO .check_b_inf_hi
    GOTO .return_a
.check_b_inf_hi:
    MOV R0, [0x3D]
    CP R0, 0xF
    SKIP NZ, 2
    GOTO .b_inf_with_a_inf
    GOTO .return_a
.b_inf_with_a_inf:
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
    AND R0, 7
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
    MOV R0, [0x3C]
    CP R0, 0xF
    SKIP NZ, 2
    GOTO .check_b_hi
    GOTO .unpack
.check_b_hi:
    MOV R0, [0x3D]
    CP R0, 0xF
    SKIP NZ, 2
    GOTO .b_special
    GOTO .unpack
.b_special:
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
    AND R0, 7
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP Z, 2
    GOTO .nan
    GOTO .return_b
.unpack:
    MOV R0, [0x39]
    MOV R1, R0
    MOV R0, [0x3A]
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
    SKIP NZ, 2
    GOTO .a_zero
    GOTO .check_b_zero
.a_zero:
    MOV R0, [0x3C]
    MOV R1, R0
    MOV R0, [0x3D]
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
    OR R1, R0
    MOV R0, [0x2B]
    OR R1, R0
    MOV R0, [0x2C]
    OR R1, R0
    MOV R0, [0x2D]
    AND R0, 7
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .both_zero
    GOTO .return_b
.check_b_zero:
    MOV R0, [0x3C]
    MOV R1, R0
    MOV R0, [0x3D]
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
    OR R1, R0
    MOV R0, [0x2B]
    OR R1, R0
    MOV R0, [0x2C]
    OR R1, R0
    MOV R0, [0x2D]
    AND R0, 7
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
    MOV R4, 0
    MOV R5, 0
    MOV R6, 0
    MOV R7, 0
    RET R0, 0
.unpack_a:
    MOV R0, 0
    MOV [0x38], R0
    MOV R0, [0x20]
    MOV R1, R0
    MOV R0, [0x21]
    MOV R2, R0
    MOV R0, [0x22]
    MOV R3, R0
    MOV R0, [0x23]
    MOV R4, R0
    MOV R0, [0x24]
    MOV R5, R0
    MOV R0, [0x25]
    AND R0, 7
    MOV R6, R0
    MOV R0, 0
    MOV [0x20], R0
    MOV [0x21], R0
    MOV R0, R1
    MOV [0x22], R0
    MOV R0, R2
    MOV [0x23], R0
    MOV R0, R3
    MOV [0x24], R0
    MOV R0, R4
    MOV [0x25], R0
    MOV R0, R5
    MOV [0x26], R0
    MOV R0, R6
    MOV [0x27], R0
    MOV R0, [0x39]
    MOV R1, R0
    MOV R0, [0x3A]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .subnormal_a
    MOV R0, R6
    OR R0, 8
    MOV [0x27], R0
    MOV R1, 1
    MOV R0, [0x39]
    ADD R0, R1
    MOV [0x39], R0
    MOV R1, 8
    MOV R0, [0x3A]
    ADC R0, R1
    MOV [0x3A], R0
    MOV R1, 0
    MOV R0, [0x3B]
    ADC R0, R1
    MOV [0x3B], R0
    GOTO .unpack_b
.subnormal_a:
    MOV R0, 2
    MOV [0x39], R0
    MOV R0, 8
    MOV [0x3A], R0
    MOV R0, 0
    MOV [0x3B], R0
.subnorm_4:
    MOV R0, [0x27]
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
    MOV R0, [0x26]
    ADC R0, R0
    MOV [0x26], R0
    MOV R0, [0x27]
    ADC R0, R0
    MOV [0x27], R0
    MOV R1, 1
    MOV R0, [0x39]
    SUB R0, R1
    MOV [0x39], R0
    MOV R1, 0
    MOV R0, [0x3A]
    SBB R0, R1
    MOV [0x3A], R0
    MOV R1, 0
    MOV R0, [0x3B]
    SBB R0, R1
    MOV [0x3B], R0
    GOTO .subnorm_4
.unpack_b:
    MOV R0, [0x28]
    MOV R1, R0
    MOV R0, [0x29]
    MOV R2, R0
    MOV R0, [0x2A]
    MOV R3, R0
    MOV R0, [0x2B]
    MOV R4, R0
    MOV R0, [0x2C]
    MOV R5, R0
    MOV R0, [0x2D]
    AND R0, 7
    MOV R6, R0
    MOV R0, 0
    MOV [0x28], R0
    MOV [0x29], R0
    MOV R0, R1
    MOV [0x2A], R0
    MOV R0, R2
    MOV [0x2B], R0
    MOV R0, R3
    MOV [0x2C], R0
    MOV R0, R4
    MOV [0x2D], R0
    MOV R0, R5
    MOV [0x2E], R0
    MOV R0, R6
    MOV [0x2F], R0
    MOV R0, [0x3C]
    MOV R1, R0
    MOV R0, [0x3D]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .subnormal_b
    MOV R0, R6
    OR R0, 8
    MOV [0x2F], R0
    MOV R1, 1
    MOV R0, [0x3C]
    ADD R0, R1
    MOV [0x3C], R0
    MOV R1, 8
    MOV R0, [0x3D]
    ADC R0, R1
    MOV [0x3D], R0
    MOV R1, 0
    MOV R0, [0x3E]
    ADC R0, R1
    MOV [0x3E], R0
    GOTO .align
.subnormal_b:
    MOV R0, 2
    MOV [0x3C], R0
    MOV R0, 8
    MOV [0x3D], R0
    MOV R0, 0
    MOV [0x3E], R0
.subnorm_5:
    MOV R0, [0x2F]
    AND R0, 8
    CP R0, 0
    SKIP Z, 2
    GOTO .align
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
    MOV R0, [0x2E]
    ADC R0, R0
    MOV [0x2E], R0
    MOV R0, [0x2F]
    ADC R0, R0
    MOV [0x2F], R0
    MOV R1, 1
    MOV R0, [0x3C]
    SUB R0, R1
    MOV [0x3C], R0
    MOV R1, 0
    MOV R0, [0x3D]
    SBB R0, R1
    MOV [0x3D], R0
    MOV R1, 0
    MOV R0, [0x3E]
    SBB R0, R1
    MOV [0x3E], R0
    GOTO .subnorm_5
.align:
; @badgec-f32: align-dispatch-begin
    MOV R0, [0x3F]
    CP R0, 1
    SKIP Z, 2
    GOTO .align_not_mul
    GOTO .mul_calc
.align_not_mul:
    CP R0, 2
    SKIP Z, 2
    GOTO .align_addsub
    GOTO .div_calc
.align_addsub:
; @badgec-f32: align-dispatch-end
    MOV R0, [0x3B]
    MOV R1, R0
    MOV R0, [0x3E]
    SUB R1, R0
    SKIP Z, 2
    GOTO .cmp_diff_7
    GOTO .cmp_next_6
.cmp_diff_7:
    SKIP NC, 2
    GOTO .diff_exp
    GOTO .swap
.cmp_next_6:
    MOV R0, [0x3A]
    MOV R1, R0
    MOV R0, [0x3D]
    SUB R1, R0
    SKIP Z, 2
    GOTO .cmp_diff_9
    GOTO .cmp_next_8
.cmp_diff_9:
    SKIP NC, 2
    GOTO .diff_exp
    GOTO .swap
.cmp_next_8:
    MOV R0, [0x39]
    MOV R1, R0
    MOV R0, [0x3C]
    SUB R1, R0
    SKIP Z, 2
    GOTO .cmp_diff_11
    GOTO .cmp_next_10
.cmp_diff_11:
    SKIP NC, 2
    GOTO .diff_exp
    GOTO .swap
.cmp_next_10:
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
    MOV R0, [0x26]
    MOV R1, R0
    MOV R0, [0x2E]
    MOV [0x26], R0
    MOV R0, R1
    MOV [0x2E], R0
    MOV R0, [0x27]
    MOV R1, R0
    MOV R0, [0x2F]
    MOV [0x27], R0
    MOV R0, R1
    MOV [0x2F], R0
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
    MOV R0, [0x3B]
    MOV R1, R0
    MOV R0, [0x3E]
    MOV [0x3B], R0
    MOV R0, R1
    MOV [0x3E], R0
    MOV R0, R8
    MOV R8, R9
    MOV R9, R0
.diff_exp:
    MOV R0, [0x39]
    MOV R1, R0
    MOV R0, [0x3C]
    SUB R1, R0
    MOV R0, R1
    MOV [0x3C], R0
    MOV R0, [0x3A]
    MOV R1, R0
    MOV R0, [0x3D]
    SBB R1, R0
    MOV R0, R1
    MOV [0x3D], R0
    MOV R0, [0x3B]
    MOV R1, R0
    MOV R0, [0x3E]
    SBB R1, R0
    MOV R0, R1
    MOV [0x3E], R0
    MOV R0, [0x3E]
    CP R0, 0
    SKIP Z, 2
    GOTO .cap_shift
    MOV R0, [0x3D]
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
    MOV [0x2E], R0
    MOV [0x2F], R0
    MOV R0, 1
    MOV [0x38], R0
    GOTO .align_done
.align_loop:
    MOV R0, [0x3C]
    MOV R1, R0
    MOV R0, [0x3D]
    OR R1, R0
    MOV R0, [0x3E]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .align_done
    MOV R0, 0
    ADD R0, 0
    MOV R0, [0x2F]
    RRC R0
    MOV [0x2F], R0
    MOV R0, [0x2E]
    RRC R0
    MOV [0x2E], R0
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
    MOV R0, [0x38]
    OR R0, R1
    MOV [0x38], R0
    MOV R1, 1
    MOV R0, [0x3C]
    SUB R0, R1
    MOV [0x3C], R0
    MOV R1, 0
    MOV R0, [0x3D]
    SBB R0, R1
    MOV [0x3D], R0
    MOV R1, 0
    MOV R0, [0x3E]
    SBB R0, R1
    MOV [0x3E], R0
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
    MOV [0x3F], R0
    MOV R0, R8
    MOV R1, R0
    MOV R0, R9
    SUB R1, R0
    SKIP Z, 2
    GOTO .diff_signs
    GOTO .same_signs
.diff_signs:
    MOV R0, [0x27]
    MOV R1, R0
    MOV R0, [0x2F]
    SUB R1, R0
    SKIP Z, 2
    GOTO .cmp8_diff_13
    GOTO .cmp8_next_12
.cmp8_diff_13:
    SKIP NC, 2
    GOTO .sub_mag
    GOTO .swap_mag
.cmp8_next_12:
    MOV R0, [0x26]
    MOV R1, R0
    MOV R0, [0x2E]
    SUB R1, R0
    SKIP Z, 2
    GOTO .cmp8_diff_15
    GOTO .cmp8_next_14
.cmp8_diff_15:
    SKIP NC, 2
    GOTO .sub_mag
    GOTO .swap_mag
.cmp8_next_14:
    MOV R0, [0x25]
    MOV R1, R0
    MOV R0, [0x2D]
    SUB R1, R0
    SKIP Z, 2
    GOTO .cmp8_diff_17
    GOTO .cmp8_next_16
.cmp8_diff_17:
    SKIP NC, 2
    GOTO .sub_mag
    GOTO .swap_mag
.cmp8_next_16:
    MOV R0, [0x24]
    MOV R1, R0
    MOV R0, [0x2C]
    SUB R1, R0
    SKIP Z, 2
    GOTO .cmp8_diff_19
    GOTO .cmp8_next_18
.cmp8_diff_19:
    SKIP NC, 2
    GOTO .sub_mag
    GOTO .swap_mag
.cmp8_next_18:
    MOV R0, [0x23]
    MOV R1, R0
    MOV R0, [0x2B]
    SUB R1, R0
    SKIP Z, 2
    GOTO .cmp8_diff_21
    GOTO .cmp8_next_20
.cmp8_diff_21:
    SKIP NC, 2
    GOTO .sub_mag
    GOTO .swap_mag
.cmp8_next_20:
    MOV R0, [0x22]
    MOV R1, R0
    MOV R0, [0x2A]
    SUB R1, R0
    SKIP Z, 2
    GOTO .cmp8_diff_23
    GOTO .cmp8_next_22
.cmp8_diff_23:
    SKIP NC, 2
    GOTO .sub_mag
    GOTO .swap_mag
.cmp8_next_22:
    MOV R0, [0x21]
    MOV R1, R0
    MOV R0, [0x29]
    SUB R1, R0
    SKIP Z, 2
    GOTO .cmp8_diff_25
    GOTO .cmp8_next_24
.cmp8_diff_25:
    SKIP NC, 2
    GOTO .sub_mag
    GOTO .swap_mag
.cmp8_next_24:
    MOV R0, [0x20]
    MOV R1, R0
    MOV R0, [0x28]
    SUB R1, R0
    SKIP Z, 2
    GOTO .cmp8_diff_27
    GOTO .cmp8_next_26
.cmp8_diff_27:
    SKIP NC, 2
    GOTO .sub_mag
    GOTO .swap_mag
.cmp8_next_26:
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
    MOV R0, [0x26]
    MOV R1, R0
    MOV R0, [0x2E]
    MOV [0x26], R0
    MOV R0, R1
    MOV [0x2E], R0
    MOV R0, [0x27]
    MOV R1, R0
    MOV R0, [0x2F]
    MOV [0x27], R0
    MOV R0, R1
    MOV [0x2F], R0
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
    MOV R0, [0x26]
    MOV R1, R0
    MOV R0, [0x2E]
    SBB R1, R0
    MOV R0, R1
    MOV [0x36], R0
    MOV R0, [0x27]
    MOV R1, R0
    MOV R0, [0x2F]
    SBB R1, R0
    MOV R0, R1
    MOV [0x37], R0
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
    MOV R0, [0x36]
    OR R1, R0
    MOV R0, [0x37]
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
    MOV R5, 0
    MOV R6, 0
    MOV R7, 0
    MOV R8, 0
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
    MOV R0, [0x26]
    MOV R1, R0
    MOV R0, [0x2E]
    ADC R1, R0
    MOV R0, R1
    MOV [0x36], R0
    MOV R0, [0x27]
    MOV R1, R0
    MOV R0, [0x2F]
    ADC R1, R0
    MOV R0, R1
    MOV [0x37], R0
    SKIP NC, 2
    GOTO .add_carry
    GOTO .normalize
.add_carry:
    MOV R1, 0
    ADC R1, R1
    MOV R9, R1
    MOV R0, 0
    ADD R0, 0
    MOV R0, [0x37]
    RRC R0
    MOV [0x37], R0
    MOV R0, [0x36]
    RRC R0
    MOV [0x36], R0
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
    MOV R0, R9
    CP R0, 0
    SKIP Z, 2
    GOTO .set_carry_bit
    GOTO .after_carry_bit
.set_carry_bit:
    MOV R0, [0x37]
    OR R0, 8
    MOV [0x37], R0
.after_carry_bit:
    MOV R1, 1
    MOV R0, [0x39]
    ADD R0, R1
    MOV [0x39], R0
    MOV R1, 0
    MOV R0, [0x3A]
    ADC R0, R1
    MOV [0x3A], R0
    MOV R1, 0
    MOV R0, [0x3B]
    ADC R0, R1
    MOV [0x3B], R0
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
    MOV R0, [0x36]
    OR R1, R0
    MOV R0, [0x37]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .zero_result
.norm_28:
    MOV R0, [0x37]
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
    MOV R0, [0x36]
    ADC R0, R0
    MOV [0x36], R0
    MOV R0, [0x37]
    ADC R0, R0
    MOV [0x37], R0
    MOV R1, 1
    MOV R0, [0x39]
    SUB R0, R1
    MOV [0x39], R0
    MOV R1, 0
    MOV R0, [0x3A]
    SBB R0, R1
    MOV [0x3A], R0
    MOV R1, 0
    MOV R0, [0x3B]
    SBB R0, R1
    MOV [0x3B], R0
    GOTO .norm_28
.norm_done:
.pack_dispatch:
    MOV R0, [0x3B]
    AND R0, 8
    CP R0, 0
    SKIP Z, 2
    GOTO .pack_subnormal
    MOV R0, [0x3B]
    CP R0, 0
    SKIP Z, 2
    GOTO .ea_high_nonzero
    GOTO .ea_lt_0x100
.ea_high_nonzero:
    CP R0, 1
    SKIP Z, 2
    GOTO .pack_inf
    GOTO .ea_high_1
.ea_high_1:
    MOV R0, [0x3A]
    CP R0, 8
    SKIP NC, 2
    GOTO .pack_inf
    GOTO .round_normal
.ea_lt_0x100:
    MOV R0, [0x3A]
    CP R0, 8
    SKIP NC, 2
    GOTO .ea_mid_8plus
    GOTO .pack_subnormal
.ea_mid_8plus:
    CP R0, 8
    SKIP Z, 2
    GOTO .round_normal
    GOTO .ea_mid_eq8
.ea_mid_eq8:
    MOV R0, [0x39]
    CP R0, 2
    SKIP NC, 2
    GOTO .round_normal
    GOTO .pack_subnormal
.round_normal:
    MOV R0, [0x31]
    AND R0, 8
    CP R0, 0
    SKIP NZ, 2
    GOTO .normal_clear_tail
    GOTO .normal_round_decision
.normal_round_decision:
    MOV R0, [0x31]
    AND R0, 4
    CP R0, 0
    SKIP NZ, 2
    GOTO .normal_check_sticky
    GOTO .normal_add_round
.normal_check_sticky:
    MOV R0, [0x31]
    AND R0, 3
    MOV R1, R0
    MOV R0, [0x30]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .normal_check_extra
    GOTO .normal_add_round
.normal_check_extra:
    MOV R0, [0x3F]
    CP R0, 0
    SKIP NZ, 2
    GOTO .normal_check_positive_sticky
    GOTO .normal_check_sub_sticky
.normal_check_positive_sticky:
    MOV R0, [0x38]
    CP R0, 0
    SKIP NZ, 2
    GOTO .normal_tie_lsb
    GOTO .normal_add_round
.normal_check_sub_sticky:
    MOV R0, [0x38]
    CP R0, 0
    SKIP Z, 2
    GOTO .normal_clear_tail
    GOTO .normal_tie_lsb
.normal_tie_lsb:
    MOV R0, [0x32]
    AND R0, 1
    CP R0, 0
    SKIP NZ, 2
    GOTO .normal_clear_tail
    GOTO .normal_add_round
.normal_add_round:
    MOV R1, 1
    MOV R0, [0x32]
    ADD R0, R1
    MOV [0x32], R0
    MOV R1, 0
    MOV R0, [0x33]
    ADC R0, R1
    MOV [0x33], R0
    MOV R0, [0x34]
    ADC R0, R1
    MOV [0x34], R0
    MOV R0, [0x35]
    ADC R0, R1
    MOV [0x35], R0
    MOV R0, [0x36]
    ADC R0, R1
    MOV [0x36], R0
    MOV R0, [0x37]
    ADC R0, R1
    MOV [0x37], R0
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
    MOV [0x36], R0
    MOV [0x37], R0
    MOV R0, 8
    MOV [0x37], R0
    MOV R1, 1
    MOV R0, [0x39]
    ADD R0, R1
    MOV [0x39], R0
    MOV R1, 0
    MOV R0, [0x3A]
    ADC R0, R1
    MOV [0x3A], R0
    MOV R1, 0
    MOV R0, [0x3B]
    ADC R0, R1
    MOV [0x3B], R0
    GOTO .pack_dispatch
.normal_clear_tail:
    MOV R0, 0
    MOV [0x30], R0
    MOV [0x31], R0
    MOV R1, 1
    MOV R0, [0x39]
    SUB R0, R1
    MOV [0x3C], R0
    MOV R1, 8
    MOV R0, [0x3A]
    SBB R0, R1
    MOV [0x3D], R0
    MOV R0, [0x32]
    MOV R1, R0
    MOV R0, [0x33]
    MOV R2, R0
    MOV R0, [0x34]
    MOV R3, R0
    MOV R0, [0x35]
    MOV R4, R0
    MOV R0, [0x36]
    MOV R5, R0
    MOV R0, [0x37]
    AND R0, 7
    MOV R6, R0
    MOV R0, [0x3C]
    AND R0, 1
    ADD R0, R0
    ADD R0, R0
    ADD R0, R0
    OR R6, R0
    MOV R0, [0x3C]
    ADD R0, 0
    RRC R0
    AND R0, 7
    MOV R7, R0
    MOV R0, [0x3D]
    AND R0, 1
    ADD R0, R0
    ADD R0, R0
    ADD R0, R0
    OR R7, R0
    MOV R0, [0x3D]
    ADD R0, 0
    RRC R0
    AND R0, 7
    OR R0, R8
    MOV R8, R0
    RET R0, 0
.pack_inf:
    MOV R0, R8
    MOV R1, 7
    OR R1, R0
    MOV R8, R1
    MOV R1, 0
    MOV R2, 0
    MOV R3, 0
    MOV R4, 0
    MOV R5, 0
    MOV R6, 8
    MOV R7, 15
    RET R0, 0
.pack_subnormal:
    MOV R0, [0x39]
    MOV R1, R0
    MOV R0, 10
    SUB R0, R1
    MOV [0x3C], R0
    MOV R0, [0x3A]
    MOV R1, R0
    MOV R0, 8
    SBB R0, R1
    MOV [0x3D], R0
    MOV R0, [0x3B]
    MOV R1, R0
    MOV R0, 0
    SBB R0, R1
    MOV [0x3E], R0
    MOV R0, [0x3E]
    CP R0, 0
    SKIP Z, 2
    GOTO .sub_zero
    MOV R0, [0x3D]
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
    MOV R0, [0x3C]
    CP R0, 0
    SKIP Z, 2
    GOTO .sub_zero
    GOTO .sub_shift_start
.sub_shift_start:
    MOV R6, 0
    MOV R0, [0x3F]
    CP R0, 0
    SKIP NZ, 2
    GOTO .sub_add_sticky
    GOTO .sub_sticky_done
.sub_add_sticky:
    MOV R0, [0x38]
    MOV R6, R0
.sub_sticky_done:
    MOV R1, 1
    MOV R0, [0x3C]
    SUB R0, R1
    MOV [0x3C], R0
    MOV R1, 0
    MOV R0, [0x3D]
    SBB R0, R1
    MOV [0x3D], R0
    MOV R1, 0
    MOV R0, [0x3E]
    SBB R0, R1
    MOV [0x3E], R0
.sub_loop_29:
    MOV R0, [0x3C]
    MOV R1, R0
    MOV R0, [0x3D]
    OR R1, R0
    MOV R0, [0x3E]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .sub_guard_30
    MOV R0, [0x30]
    AND R0, 1
    MOV R1, R0
    MOV R0, R6
    OR R0, R1
    MOV R6, R0
    MOV R0, 0
    ADD R0, 0
    MOV R0, [0x37]
    RRC R0
    MOV [0x37], R0
    MOV R0, [0x36]
    RRC R0
    MOV [0x36], R0
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
    MOV R0, [0x3C]
    SUB R0, R1
    MOV [0x3C], R0
    MOV R1, 0
    MOV R0, [0x3D]
    SBB R0, R1
    MOV [0x3D], R0
    MOV R1, 0
    MOV R0, [0x3E]
    SBB R0, R1
    MOV [0x3E], R0
    GOTO .sub_loop_29
.sub_guard_30:
    MOV R0, [0x30]
    AND R0, 1
    MOV R7, R0
    MOV R0, 0
    ADD R0, 0
    MOV R0, [0x37]
    RRC R0
    MOV [0x37], R0
    MOV R0, [0x36]
    RRC R0
    MOV [0x36], R0
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
    MOV R0, [0x3F]
    CP R0, 0
    SKIP NZ, 2
    GOTO .sub_tie_lsb
    GOTO .sub_check_sub_sticky
.sub_check_sub_sticky:
    MOV R0, [0x38]
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
    MOV R0, [0x33]
    ADC R0, R1
    MOV [0x33], R0
    MOV R0, [0x34]
    ADC R0, R1
    MOV [0x34], R0
    MOV R0, [0x35]
    ADC R0, R1
    MOV [0x35], R0
.sub_pack:
    MOV R0, [0x35]
    AND R0, 8
    CP R0, 0
    SKIP Z, 2
    GOTO .sub_smallest_normal
    GOTO .sub_pack_fraction
.sub_smallest_normal:
    MOV R1, 0
    MOV R2, 0
    MOV R3, 0
    MOV R4, 0
    MOV R5, 0
    MOV R6, 8
    MOV R7, 0
    MOV R8, R8
    RET R0, 0
.sub_pack_fraction:
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
    AND R0, 7
    MOV R6, R0
    MOV R7, 0
    MOV R8, R8
    RET R0, 0
.sub_zero:
    MOV R1, 0
    MOV R2, 0
    MOV R3, 0
    MOV R4, 0
    MOV R5, 0
    MOV R6, 0
    MOV R7, 0
    MOV R8, R8
    RET R0, 0
.nan:
    MOV R1, 0
    MOV R2, 0
    MOV R3, 0
    MOV R4, 0
    MOV R5, 0
    MOV R6, 12
    MOV R7, 15
    MOV R8, 7
    RET R0, 0
; @badgec-f32: muldiv-begin
.mul_special:
; @badgec-f32: mul-special-begin
    MOV R0, [0x39]
    CP R0, 15
    SKIP Z, 2
    GOTO .no_nan_31
    MOV R0, [0x3A]
    CP R0, 15
    SKIP Z, 2
    GOTO .no_nan_31
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
    GOTO .nan
.no_nan_31:
    MOV R0, [0x3C]
    CP R0, 15
    SKIP Z, 2
    GOTO .no_nan_32
    MOV R0, [0x3D]
    CP R0, 15
    SKIP Z, 2
    GOTO .no_nan_32
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
    AND R0, 7
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP Z, 2
    GOTO .nan
.no_nan_32:
    MOV R0, [0x39]
    MOV R1, R0
    MOV R0, [0x3A]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP Z, 2
    GOTO .mul_a_nonzero
    GOTO .zfrac_33
.zfrac_33:
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
    SKIP NZ, 2
    GOTO .mul_a_zero
    GOTO .mul_a_nonzero
.mul_a_zero:
    MOV R0, [0x3C]
    CP R0, 15
    SKIP Z, 2
    GOTO .not_inf_34
    MOV R0, [0x3D]
    CP R0, 15
    SKIP Z, 2
    GOTO .not_inf_34
    GOTO .nan
.not_inf_34:
    GOTO .ret_zero_signed
.mul_a_nonzero:
    MOV R0, [0x3C]
    MOV R1, R0
    MOV R0, [0x3D]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP Z, 2
    GOTO .mul_b_nonzero
    GOTO .zfrac_35
.zfrac_35:
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
    AND R0, 7
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .mul_b_zero
    GOTO .mul_b_nonzero
.mul_b_zero:
    MOV R0, [0x39]
    CP R0, 15
    SKIP Z, 2
    GOTO .not_inf_36
    MOV R0, [0x3A]
    CP R0, 15
    SKIP Z, 2
    GOTO .not_inf_36
    GOTO .nan
.not_inf_36:
    GOTO .ret_zero_signed
.mul_b_nonzero:
    MOV R0, [0x39]
    CP R0, 15
    SKIP Z, 2
    GOTO .not_inf_37
    MOV R0, [0x3A]
    CP R0, 15
    SKIP Z, 2
    GOTO .not_inf_37
    GOTO .ret_inf_signed
.not_inf_37:
    MOV R0, [0x3C]
    CP R0, 15
    SKIP Z, 2
    GOTO .not_inf_38
    MOV R0, [0x3D]
    CP R0, 15
    SKIP Z, 2
    GOTO .not_inf_38
    GOTO .ret_inf_signed
.not_inf_38:
    GOTO .unpack_a
; @badgec-f32: mul-special-end
.div_special:
; @badgec-f32: div-special-begin
    MOV R0, [0x39]
    CP R0, 15
    SKIP Z, 2
    GOTO .no_nan_39
    MOV R0, [0x3A]
    CP R0, 15
    SKIP Z, 2
    GOTO .no_nan_39
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
    GOTO .nan
.no_nan_39:
    MOV R0, [0x3C]
    CP R0, 15
    SKIP Z, 2
    GOTO .no_nan_40
    MOV R0, [0x3D]
    CP R0, 15
    SKIP Z, 2
    GOTO .no_nan_40
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
    AND R0, 7
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP Z, 2
    GOTO .nan
.no_nan_40:
    MOV R0, [0x3C]
    MOV R1, R0
    MOV R0, [0x3D]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP Z, 2
    GOTO .div_b_nonzero
    GOTO .zfrac_41
.zfrac_41:
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
    AND R0, 7
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .div_b_zero
    GOTO .div_b_nonzero
.div_b_zero:
    MOV R0, [0x39]
    MOV R1, R0
    MOV R0, [0x3A]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP Z, 2
    GOTO .div_b_zero_a_nonzero
    GOTO .zfrac_42
.zfrac_42:
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
    SKIP NZ, 2
    GOTO .nan
    GOTO .div_b_zero_a_nonzero
.div_b_zero_a_nonzero:
    GOTO .ret_inf_signed
.div_b_nonzero:
    MOV R0, [0x39]
    MOV R1, R0
    MOV R0, [0x3A]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP Z, 2
    GOTO .div_a_nonzero
    GOTO .zfrac_43
.zfrac_43:
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
    SKIP NZ, 2
    GOTO .div_ret_zero
    GOTO .div_a_nonzero
.div_ret_zero:
    GOTO .ret_zero_signed
.div_a_nonzero:
    MOV R0, [0x39]
    CP R0, 15
    SKIP Z, 2
    GOTO .not_inf_44
    MOV R0, [0x3A]
    CP R0, 15
    SKIP Z, 2
    GOTO .not_inf_44
    GOTO .div_a_inf
.not_inf_44:
    MOV R0, [0x3C]
    CP R0, 15
    SKIP Z, 2
    GOTO .not_inf_45
    MOV R0, [0x3D]
    CP R0, 15
    SKIP Z, 2
    GOTO .not_inf_45
    GOTO .div_ret_zero
.not_inf_45:
    GOTO .unpack_a
.div_a_inf:
    MOV R0, [0x3C]
    CP R0, 15
    SKIP Z, 2
    GOTO .not_inf_46
    MOV R0, [0x3D]
    CP R0, 15
    SKIP Z, 2
    GOTO .not_inf_46
    GOTO .nan
.not_inf_46:
    GOTO .ret_inf_signed
; @badgec-f32: div-special-end
.ret_zero_signed:
    MOV R1, R8
    XOR R1, R9
    MOV R8, R1
    MOV R1, 0
    MOV R2, 0
    MOV R3, 0
    MOV R4, 0
    MOV R5, 0
    MOV R6, 0
    MOV R7, 0
    RET R0, 0
.ret_inf_signed:
    MOV R1, R8
    XOR R1, R9
    MOV R8, R1
    GOTO .pack_inf
.mul_calc:
; @badgec-f32: mul-calc-begin
    MOV R0, [0x39]
    MOV R1, R0
    MOV R0, [0x3C]
    ADD R1, R0
    MOV R0, R1
    MOV [${__bc_f32_tmp+0}], R0
    MOV R0, [0x3A]
    MOV R1, R0
    MOV R0, [0x3D]
    ADC R1, R0
    MOV R0, R1
    MOV [${__bc_f32_tmp+1}], R0
    MOV R0, [0x3B]
    MOV R1, R0
    MOV R0, [0x3E]
    ADC R1, R0
    MOV R0, R1
    MOV [${__bc_f32_tmp+2}], R0
    MOV R1, 1
    MOV R0, [${__bc_f32_tmp+2}]
    SUB R0, R1
    MOV [${__bc_f32_tmp+2}], R0
    MOV R0, R8
    XOR R0, R9
    MOV [${__bc_f32_tmp2+0}], R0
    MOV R0, [0x25]
    MOV [0x3C], R0
    MOV R0, [0x26]
    MOV [0x3D], R0
    MOV R0, [0x27]
    MOV [0x3E], R0
    MOV R0, [0x2D]
    MOV [${__bc_f32_tmp+3}], R0
    MOV R0, [0x2E]
    MOV [${__bc_f32_tmp+4}], R0
    MOV R0, [0x2F]
    MOV [${__bc_f32_tmp+5}], R0
    MOV R0, [0x2A]
    MOV [0x3F], R0
    MOV R0, [0x2B]
    MOV [${__bc_f32_tmp+6}], R0
    MOV R0, [0x2C]
    MOV [${__bc_f32_tmp+7}], R0
    MOV R0, [0x22]
    MOV [0x20], R0
    MOV R0, [0x23]
    MOV [0x21], R0
    MOV R0, [0x24]
    MOV [0x22], R0
    MOV R0, 0
    MOV [0x23], R0
    MOV [0x24], R0
    MOV [0x25], R0
    MOV [0x26], R0
    MOV [0x27], R0
    MOV R0, 0
    MOV [0x28], R0
    MOV [0x29], R0
    MOV [0x2A], R0
    MOV [0x2B], R0
    MOV [0x2C], R0
    MOV [0x2D], R0
    MOV [0x2E], R0
    MOV [0x2F], R0
    MOV R0, [0x3F]
    MOV [0x28], R0
    MOV R0, [${__bc_f32_tmp+6}]
    MOV [0x29], R0
    MOV R0, [${__bc_f32_tmp+7}]
    MOV [0x2A], R0
    MOV R0, 0
    MOV [0x30], R0
    MOV [0x31], R0
    MOV [0x32], R0
    MOV [0x33], R0
    MOV [0x34], R0
    MOV [0x35], R0
    MOV [0x36], R0
    MOV [0x37], R0
    MOV [0x38], R0
    MOV [0x39], R0
    MOV [0x3A], R0
    MOV [0x3B], R0
    MOV R4, 2
    MOV R5, 0
    MOV R6, 2
    MOV R7, 8
    GOSUB __bc_mul32
    MOV R0, [0x30]
    ADD R0, R1
    MOV [0x30], R0
    MOV R0, [0x31]
    ADC R0, R2
    MOV [0x31], R0
    MOV R0, [0x32]
    ADC R0, R3
    MOV [0x32], R0
    MOV R0, [0x33]
    ADC R0, R4
    MOV [0x33], R0
    MOV R0, [0x34]
    ADC R0, R5
    MOV [0x34], R0
    MOV R0, [0x35]
    ADC R0, R6
    MOV [0x35], R0
    MOV R0, [0x36]
    ADC R0, R7
    MOV [0x36], R0
    MOV R0, [${__bc_f32_tmp+3}]
    MOV [0x28], R0
    MOV R0, [${__bc_f32_tmp+4}]
    MOV [0x29], R0
    MOV R0, [${__bc_f32_tmp+5}]
    MOV [0x2A], R0
    MOV R4, 2
    MOV R5, 0
    MOV R6, 2
    MOV R7, 8
    GOSUB __bc_mul32
    MOV R0, [0x33]
    ADD R0, R1
    MOV [0x33], R0
    MOV R0, [0x34]
    ADC R0, R2
    MOV [0x34], R0
    MOV R0, [0x35]
    ADC R0, R3
    MOV [0x35], R0
    MOV R0, [0x36]
    ADC R0, R4
    MOV [0x36], R0
    MOV R0, [0x37]
    ADC R0, R5
    MOV [0x37], R0
    MOV R0, [0x38]
    ADC R0, R6
    MOV [0x38], R0
    MOV R0, [0x39]
    ADC R0, R7
    MOV [0x39], R0
    MOV R0, [0x3C]
    MOV [0x20], R0
    MOV R0, [0x3D]
    MOV [0x21], R0
    MOV R0, [0x3E]
    MOV [0x22], R0
    MOV R0, [0x3F]
    MOV [0x28], R0
    MOV R0, [${__bc_f32_tmp+6}]
    MOV [0x29], R0
    MOV R0, [${__bc_f32_tmp+7}]
    MOV [0x2A], R0
    MOV R4, 2
    MOV R5, 0
    MOV R6, 2
    MOV R7, 8
    GOSUB __bc_mul32
    MOV R0, [0x33]
    ADD R0, R1
    MOV [0x33], R0
    MOV R0, [0x34]
    ADC R0, R2
    MOV [0x34], R0
    MOV R0, [0x35]
    ADC R0, R3
    MOV [0x35], R0
    MOV R0, [0x36]
    ADC R0, R4
    MOV [0x36], R0
    MOV R0, [0x37]
    ADC R0, R5
    MOV [0x37], R0
    MOV R0, [0x38]
    ADC R0, R6
    MOV [0x38], R0
    MOV R0, [0x39]
    ADC R0, R7
    MOV [0x39], R0
    MOV R0, [${__bc_f32_tmp+3}]
    MOV [0x28], R0
    MOV R0, [${__bc_f32_tmp+4}]
    MOV [0x29], R0
    MOV R0, [${__bc_f32_tmp+5}]
    MOV [0x2A], R0
    MOV R4, 2
    MOV R5, 0
    MOV R6, 2
    MOV R7, 8
    GOSUB __bc_mul32
    MOV R0, [0x36]
    ADD R0, R1
    MOV [0x36], R0
    MOV R0, [0x37]
    ADC R0, R2
    MOV [0x37], R0
    MOV R0, [0x38]
    ADC R0, R3
    MOV [0x38], R0
    MOV R0, [0x39]
    ADC R0, R4
    MOV [0x39], R0
    MOV R0, [0x3A]
    ADC R0, R5
    MOV [0x3A], R0
    MOV R0, [0x3B]
    ADC R0, R6
    MOV [0x3B], R0
    MOV R0, [0x3B]
    AND R0, 8
    CP R0, 0
    SKIP NZ, 2
    GOTO .mul_shift_p
    GOTO .mul_no_shift_p
.mul_no_shift_p:
    MOV R1, 1
    MOV R0, [${__bc_f32_tmp+0}]
    ADD R0, R1
    MOV [${__bc_f32_tmp+0}], R0
    MOV R1, 0
    MOV R0, [${__bc_f32_tmp+1}]
    ADC R0, R1
    MOV [${__bc_f32_tmp+1}], R0
    MOV R1, 0
    MOV R0, [${__bc_f32_tmp+2}]
    ADC R0, R1
    MOV [${__bc_f32_tmp+2}], R0
    GOTO .mul_wrapup
.mul_shift_p:
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
    MOV R0, [0x38]
    ADC R0, R0
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
.mul_wrapup:
    MOV R0, [0x30]
    MOV R1, R0
    MOV R0, [0x31]
    OR R1, R0
    MOV R0, [0x32]
    OR R1, R0
    MOV R0, [0x33]
    OR R1, R0
    MOV R0, R1
    MOV [${__bc_f32_tmp+6}], R0
    MOV R0, [0x34]
    MOV [0x30], R0
    MOV R0, [0x35]
    MOV [0x31], R0
    MOV R0, [0x36]
    MOV [0x32], R0
    MOV R0, [0x37]
    MOV [0x33], R0
    MOV R0, [0x38]
    MOV [0x34], R0
    MOV R0, [0x39]
    MOV [0x35], R0
    MOV R0, [0x3A]
    MOV [0x36], R0
    MOV R0, [0x3B]
    MOV [0x37], R0
    MOV R0, [${__bc_f32_tmp+6}]
    MOV [0x38], R0
    MOV R0, [${__bc_f32_tmp2+0}]
    MOV R8, R0
    MOV R0, [${__bc_f32_tmp+0}]
    MOV [0x39], R0
    MOV R0, [${__bc_f32_tmp+1}]
    MOV [0x3A], R0
    MOV R0, [${__bc_f32_tmp+2}]
    MOV [0x3B], R0
    MOV R0, 0
    MOV [0x3F], R0
    GOTO .normalize
; @badgec-f32: mul-calc-end
.div_calc:
; @badgec-f32: div-calc-begin
    MOV R0, R8
    XOR R0, R9
    MOV [${__bc_f32_tmp+5}], R0
    MOV R0, [0x39]
    MOV R1, R0
    MOV R0, [0x3C]
    SUB R1, R0
    MOV R0, R1
    MOV [${__bc_f32_tmp+0}], R0
    MOV R0, [0x3A]
    MOV R1, R0
    MOV R0, [0x3D]
    SBB R1, R0
    MOV R0, R1
    MOV [${__bc_f32_tmp+1}], R0
    MOV R0, [0x3B]
    MOV R1, R0
    MOV R0, [0x3E]
    SBB R1, R0
    MOV R0, R1
    MOV [${__bc_f32_tmp+2}], R0
    MOV R1, 1
    MOV R0, [${__bc_f32_tmp+2}]
    ADD R0, R1
    MOV [${__bc_f32_tmp+2}], R0
    MOV R0, [0x22]
    MOV [0x30], R0
    MOV R0, [0x23]
    MOV [0x31], R0
    MOV R0, [0x24]
    MOV [0x32], R0
    MOV R0, [0x25]
    MOV [0x33], R0
    MOV R0, [0x26]
    MOV [0x34], R0
    MOV R0, [0x27]
    MOV [0x35], R0
    MOV R0, 0
    MOV [0x36], R0
    MOV [0x37], R0
    MOV R0, [0x27]
    MOV R1, R0
    MOV R0, [0x2F]
    SUB R1, R0
    SKIP Z, 2
    GOTO .cmpn_diff_48
    GOTO .cmpn_next_47
.cmpn_diff_48:
    SKIP NC, 2
    GOTO .div_ge
    GOTO .div_less
.cmpn_next_47:
    MOV R0, [0x26]
    MOV R1, R0
    MOV R0, [0x2E]
    SUB R1, R0
    SKIP Z, 2
    GOTO .cmpn_diff_50
    GOTO .cmpn_next_49
.cmpn_diff_50:
    SKIP NC, 2
    GOTO .div_ge
    GOTO .div_less
.cmpn_next_49:
    MOV R0, [0x25]
    MOV R1, R0
    MOV R0, [0x2D]
    SUB R1, R0
    SKIP Z, 2
    GOTO .cmpn_diff_52
    GOTO .cmpn_next_51
.cmpn_diff_52:
    SKIP NC, 2
    GOTO .div_ge
    GOTO .div_less
.cmpn_next_51:
    MOV R0, [0x24]
    MOV R1, R0
    MOV R0, [0x2C]
    SUB R1, R0
    SKIP Z, 2
    GOTO .cmpn_diff_54
    GOTO .cmpn_next_53
.cmpn_diff_54:
    SKIP NC, 2
    GOTO .div_ge
    GOTO .div_less
.cmpn_next_53:
    MOV R0, [0x23]
    MOV R1, R0
    MOV R0, [0x2B]
    SUB R1, R0
    SKIP Z, 2
    GOTO .cmpn_diff_56
    GOTO .cmpn_next_55
.cmpn_diff_56:
    SKIP NC, 2
    GOTO .div_ge
    GOTO .div_less
.cmpn_next_55:
    MOV R0, [0x22]
    MOV R1, R0
    MOV R0, [0x2A]
    SUB R1, R0
    SKIP Z, 2
    GOTO .cmpn_diff_58
    GOTO .cmpn_next_57
.cmpn_diff_58:
    SKIP NC, 2
    GOTO .div_ge
    GOTO .div_less
.cmpn_next_57:
    GOTO .div_ge
.div_ge:
    MOV R0, 1
    MOV [${__bc_f32_tmp+3}], R0
    MOV R0, [0x30]
    MOV R1, R0
    MOV R0, [0x2A]
    SUB R1, R0
    MOV R0, R1
    MOV [0x30], R0
    MOV R0, [0x31]
    MOV R1, R0
    MOV R0, [0x2B]
    SBB R1, R0
    MOV R0, R1
    MOV [0x31], R0
    MOV R0, [0x32]
    MOV R1, R0
    MOV R0, [0x2C]
    SBB R1, R0
    MOV R0, R1
    MOV [0x32], R0
    MOV R0, [0x33]
    MOV R1, R0
    MOV R0, [0x2D]
    SBB R1, R0
    MOV R0, R1
    MOV [0x33], R0
    MOV R0, [0x34]
    MOV R1, R0
    MOV R0, [0x2E]
    SBB R1, R0
    MOV R0, R1
    MOV [0x34], R0
    MOV R0, [0x35]
    MOV R1, R0
    MOV R0, [0x2F]
    SBB R1, R0
    MOV R0, R1
    MOV [0x35], R0
    GOTO .div_saved
.div_less:
    MOV R0, 0
    MOV [${__bc_f32_tmp+3}], R0
.div_saved:
    MOV R0, [0x2A]
    MOV [0x20], R0
    MOV R0, [0x2B]
    MOV [0x21], R0
    MOV R0, [0x2C]
    MOV [0x22], R0
    MOV R0, [0x2D]
    MOV [0x23], R0
    MOV R0, [0x2E]
    MOV [0x24], R0
    MOV R0, [0x2F]
    MOV [0x25], R0
    MOV R0, 0
    MOV [0x38], R0
    MOV [0x39], R0
    MOV [0x3A], R0
    MOV [0x3B], R0
    MOV [0x3C], R0
    MOV [0x3D], R0
    MOV [0x3E], R0
    MOV [0x3F], R0
    MOV R0, 0
    MOV [0x28], R0
    MOV [0x29], R0
    MOV R0, [0x30]
    MOV [0x2A], R0
    MOV R0, [0x31]
    MOV [0x2B], R0
    MOV R0, [0x32]
    MOV [0x2C], R0
    MOV R0, [0x33]
    MOV [0x2D], R0
    MOV R0, [0x34]
    MOV [0x2E], R0
    MOV R0, [0x35]
    MOV [0x2F], R0
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
    MOV R0, 0
    MOV [0x36], R0
    MOV [0x37], R0
    MOV R4, 2
    MOV R5, 8
    MOV R6, 3
    MOV R7, 0
    GOSUB __bc_divmod32
    MOV R0, [0x3D]
    MOV [0x3F], R0
    MOV R0, [0x3C]
    MOV [0x3E], R0
    MOV R0, [0x3B]
    MOV [0x3D], R0
    MOV R0, [0x3A]
    MOV [0x3C], R0
    MOV R0, [0x39]
    MOV [0x3B], R0
    MOV R0, [0x38]
    MOV [0x3A], R0
    MOV R0, [0x28]
    MOV [0x38], R0
    MOV R0, [0x29]
    MOV [0x39], R0
    MOV R0, 0
    MOV [0x28], R0
    MOV [0x29], R0
    MOV R0, [0x30]
    MOV [0x2A], R0
    MOV R0, [0x31]
    MOV [0x2B], R0
    MOV R0, [0x32]
    MOV [0x2C], R0
    MOV R0, [0x33]
    MOV [0x2D], R0
    MOV R0, [0x34]
    MOV [0x2E], R0
    MOV R0, [0x35]
    MOV [0x2F], R0
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
    MOV R0, 0
    MOV [0x36], R0
    MOV [0x37], R0
    MOV R4, 2
    MOV R5, 8
    MOV R6, 3
    MOV R7, 0
    GOSUB __bc_divmod32
    MOV R0, [0x3D]
    MOV [0x3F], R0
    MOV R0, [0x3C]
    MOV [0x3E], R0
    MOV R0, [0x3B]
    MOV [0x3D], R0
    MOV R0, [0x3A]
    MOV [0x3C], R0
    MOV R0, [0x39]
    MOV [0x3B], R0
    MOV R0, [0x38]
    MOV [0x3A], R0
    MOV R0, [0x28]
    MOV [0x38], R0
    MOV R0, [0x29]
    MOV [0x39], R0
    MOV R0, 0
    MOV [0x28], R0
    MOV [0x29], R0
    MOV R0, [0x30]
    MOV [0x2A], R0
    MOV R0, [0x31]
    MOV [0x2B], R0
    MOV R0, [0x32]
    MOV [0x2C], R0
    MOV R0, [0x33]
    MOV [0x2D], R0
    MOV R0, [0x34]
    MOV [0x2E], R0
    MOV R0, [0x35]
    MOV [0x2F], R0
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
    MOV R0, 0
    MOV [0x36], R0
    MOV [0x37], R0
    MOV R4, 2
    MOV R5, 8
    MOV R6, 3
    MOV R7, 0
    GOSUB __bc_divmod32
    MOV R0, [0x3D]
    MOV [0x3F], R0
    MOV R0, [0x3C]
    MOV [0x3E], R0
    MOV R0, [0x3B]
    MOV [0x3D], R0
    MOV R0, [0x3A]
    MOV [0x3C], R0
    MOV R0, [0x39]
    MOV [0x3B], R0
    MOV R0, [0x38]
    MOV [0x3A], R0
    MOV R0, [0x28]
    MOV [0x38], R0
    MOV R0, [0x29]
    MOV [0x39], R0
    MOV R0, 0
    MOV [0x28], R0
    MOV [0x29], R0
    MOV R0, [0x30]
    MOV [0x2A], R0
    MOV R0, [0x31]
    MOV [0x2B], R0
    MOV R0, [0x32]
    MOV [0x2C], R0
    MOV R0, [0x33]
    MOV [0x2D], R0
    MOV R0, [0x34]
    MOV [0x2E], R0
    MOV R0, [0x35]
    MOV [0x2F], R0
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
    MOV R0, 0
    MOV [0x36], R0
    MOV [0x37], R0
    MOV R4, 2
    MOV R5, 8
    MOV R6, 3
    MOV R7, 0
    GOSUB __bc_divmod32
    MOV R0, [0x3D]
    MOV [0x3F], R0
    MOV R0, [0x3C]
    MOV [0x3E], R0
    MOV R0, [0x3B]
    MOV [0x3D], R0
    MOV R0, [0x3A]
    MOV [0x3C], R0
    MOV R0, [0x39]
    MOV [0x3B], R0
    MOV R0, [0x38]
    MOV [0x3A], R0
    MOV R0, [0x28]
    MOV [0x38], R0
    MOV R0, [0x29]
    MOV [0x39], R0
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
    MOV [${__bc_f32_tmp+4}], R0
    MOV R0, 0
    ADD R0, 0
    MOV R0, [0x3F]
    RRC R0
    MOV [0x37], R0
    MOV R0, [0x3E]
    RRC R0
    MOV [0x36], R0
    MOV R0, [0x3D]
    RRC R0
    MOV [0x35], R0
    MOV R0, [0x3C]
    RRC R0
    MOV [0x34], R0
    MOV R0, [0x3B]
    RRC R0
    MOV [0x33], R0
    MOV R0, [0x3A]
    RRC R0
    MOV [0x32], R0
    MOV R0, [0x39]
    RRC R0
    MOV [0x31], R0
    MOV R0, [0x38]
    RRC R0
    MOV [0x30], R0
    MOV R0, 0
    ADC R0, R0
    MOV R1, R0
    MOV R0, [${__bc_f32_tmp+4}]
    OR R1, R0
    MOV R0, R1
    MOV [0x38], R0
    MOV R0, [${__bc_f32_tmp+3}]
    CP R0, 0
    SKIP Z, 2
    GOTO .div_set_q0
    GOTO .div_no_q0
.div_set_q0:
    MOV R0, [0x37]
    OR R0, 8
    MOV [0x37], R0
.div_no_q0:
    MOV R0, [${__bc_f32_tmp+5}]
    MOV R8, R0
    MOV R0, [${__bc_f32_tmp+0}]
    MOV [0x39], R0
    MOV R0, [${__bc_f32_tmp+1}]
    MOV [0x3A], R0
    MOV R0, [${__bc_f32_tmp+2}]
    MOV [0x3B], R0
    MOV R0, 0
    MOV [0x3F], R0
    GOTO .normalize
; @badgec-f32: div-calc-end
; @badgec-f32: muldiv-end
.return_a:
    MOV R0, [0x20]
    MOV R1, R0
    MOV R0, [0x21]
    MOV R2, R0
    MOV R0, [0x22]
    MOV R3, R0
    MOV R0, [0x23]
    MOV R4, R0
    MOV R0, [0x24]
    MOV R5, R0
    MOV R0, [0x25]
    MOV R6, R0
    MOV R0, [0x26]
    MOV R7, R0
    MOV R0, [0x27]
    MOV R8, R0
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
    MOV R0, [0x2C]
    MOV R5, R0
    MOV R0, [0x2D]
    MOV R6, R0
    MOV R0, [0x2E]
    MOV R7, R0
    MOV R0, [0x2F]
    MOV R8, R0
    RET R0, 0


; nibble __bc_f32_cmp(float a, float b)
fn___bc_f32_cmp:
    ; -0 and +0 compare equal.
    MOV R0, [${a}]
    MOV R1, R0
    MOV R0, [${a+1}]
    OR R1, R0
    MOV R0, [${a+2}]
    OR R1, R0
    MOV R0, [${a+3}]
    OR R1, R0
    MOV R0, [${a+4}]
    OR R1, R0
    MOV R0, [${a+5}]
    OR R1, R0
    MOV R0, [${a+6}]
    OR R1, R0
    MOV R0, [${a+7}]
    AND R0, 7
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .cmp_a_zero
    GOTO .cmp_signs
.cmp_a_zero:
    MOV R0, [${b}]
    MOV R1, R0
    MOV R0, [${b+1}]
    OR R1, R0
    MOV R0, [${b+2}]
    OR R1, R0
    MOV R0, [${b+3}]
    OR R1, R0
    MOV R0, [${b+4}]
    OR R1, R0
    MOV R0, [${b+5}]
    OR R1, R0
    MOV R0, [${b+6}]
    OR R1, R0
    MOV R0, [${b+7}]
    AND R0, 7
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .cmp_equal
    GOTO .cmp_signs
.cmp_equal:
    MOV R1, 0
    RET R0, 0
.cmp_signs:
    MOV R0, [${a+7}]
    AND R0, 8
    MOV R9, R0
    MOV R0, [${b+7}]
    AND R0, 8
    MOV R8, R0

    MOV R0, R9
    SUB R0, R8
    SKIP Z, 2
    GOTO .signs_differ
    GOTO .same_sign

.signs_differ:
    MOV R1, 15
    SKIP C, 1
    MOV R1, 1
    RET R0, 0

.same_sign:
    MOV R0, [${a+7}]
    AND R0, 7
    MOV R1, R0
    MOV R0, [${b+7}]
    AND R0, 7
    SUB R1, R0
    SKIP Z, 2
    GOTO .diff

    MOV R0, [${a+6}]
    MOV R1, R0
    MOV R0, [${b+6}]
    SUB R1, R0
    SKIP Z, 2
    GOTO .diff

    MOV R0, [${a+5}]
    MOV R1, R0
    MOV R0, [${b+5}]
    SUB R1, R0
    SKIP Z, 2
    GOTO .diff

    MOV R0, [${a+4}]
    MOV R1, R0
    MOV R0, [${b+4}]
    SUB R1, R0
    SKIP Z, 2
    GOTO .diff

    MOV R0, [${a+3}]
    MOV R1, R0
    MOV R0, [${b+3}]
    SUB R1, R0
    SKIP Z, 2
    GOTO .diff

    MOV R0, [${a+2}]
    MOV R1, R0
    MOV R0, [${b+2}]
    SUB R1, R0
    SKIP Z, 2
    GOTO .diff

    MOV R0, [${a+1}]
    MOV R1, R0
    MOV R0, [${b+1}]
    SUB R1, R0
    SKIP Z, 2
    GOTO .diff

    MOV R0, [${a}]
    MOV R1, R0
    MOV R0, [${b}]
    SUB R1, R0
    SKIP Z, 2
    GOTO .diff

    MOV R1, 0
    RET R0, 0

.diff:
    ; Preserve the magnitude comparison before testing the sign: the
    ; immediate AND used to inspect the sign clears C.
    MOV R7, 0
    ADC R7, R7
    MOV R0, R9
    AND R0, 8
    CP R0, 0
    SKIP Z, 2
    GOTO .negative

.positive:
    MOV R1, 1
    MOV R0, R7
    CP R0, 0
    SKIP NZ, 1
    MOV R1, 15
    RET R0, 0

.negative:
    MOV R1, 15
    MOV R0, R7
    CP R0, 0
    SKIP NZ, 1
    MOV R1, 1
    RET R0, 0

; bool __bc_f32_is_zero(float a)
fn___bc_f32_is_zero:
    MOV R0, [${a}]
    MOV R1, R0
    MOV R0, [${a+1}]
    OR R1, R0
    MOV R0, [${a+2}]
    OR R1, R0
    MOV R0, [${a+3}]
    OR R1, R0
    MOV R0, [${a+4}]
    OR R1, R0
    MOV R0, [${a+5}]
    OR R1, R0
    MOV R0, [${a+6}]
    OR R1, R0
    MOV R0, [${a+7}]
    AND R0, 7
    OR R1, R0

    MOV R0, R1
    CP R0, 0
    MOV R1, 0
    SKIP NZ, 1
    INC R1
    RET R0, 0

fn___bc_u32_to_f32:
    MOV R0, [${v+0}]
    MOV [0x20], R0
    MOV R0, [${v+1}]
    MOV [0x21], R0
    MOV R0, [${v+2}]
    MOV [0x22], R0
    MOV R0, [${v+3}]
    MOV [0x23], R0
    MOV R0, [${v+4}]
    MOV [0x24], R0
    MOV R0, [${v+5}]
    MOV [0x25], R0
    MOV R0, [${v+6}]
    MOV [0x26], R0
    MOV R0, [${v+7}]
    MOV [0x27], R0
    MOV R0, 0
    MOV [0x3A], R0
    GOTO fn___bc_f32_int32_core
fn___bc_i32_to_f32:
    MOV R0, [${v+0}]
    MOV [0x20], R0
    MOV R0, [${v+1}]
    MOV [0x21], R0
    MOV R0, [${v+2}]
    MOV [0x22], R0
    MOV R0, [${v+3}]
    MOV [0x23], R0
    MOV R0, [${v+4}]
    MOV [0x24], R0
    MOV R0, [${v+5}]
    MOV [0x25], R0
    MOV R0, [${v+6}]
    MOV [0x26], R0
    MOV R0, [${v+7}]
    MOV [0x27], R0
    MOV R0, [0x27]
    AND R0, 8
    CP R0, 0
    SKIP NZ, 2
    GOTO .i32p_1
    GOTO .i32n_2
.i32p_1:
    MOV R0, 0
    MOV [0x3A], R0
    GOTO fn___bc_f32_int32_core
.i32n_2:
    MOV R0, 8
    MOV [0x3A], R0
    MOV R0, [0x20]
    XOR R0, 15
    MOV [0x20], R0
    MOV R0, [0x21]
    XOR R0, 15
    MOV [0x21], R0
    MOV R0, [0x22]
    XOR R0, 15
    MOV [0x22], R0
    MOV R0, [0x23]
    XOR R0, 15
    MOV [0x23], R0
    MOV R0, [0x24]
    XOR R0, 15
    MOV [0x24], R0
    MOV R0, [0x25]
    XOR R0, 15
    MOV [0x25], R0
    MOV R0, [0x26]
    XOR R0, 15
    MOV [0x26], R0
    MOV R0, [0x27]
    XOR R0, 15
    MOV [0x27], R0
    MOV R1, 1
    MOV R0, [0x20]
    ADD R0, R1
    MOV [0x20], R0
    MOV R1, 0
    MOV R0, [0x21]
    ADC R0, R1
    MOV [0x21], R0
    MOV R1, 0
    MOV R0, [0x22]
    ADC R0, R1
    MOV [0x22], R0
    MOV R1, 0
    MOV R0, [0x23]
    ADC R0, R1
    MOV [0x23], R0
    MOV R1, 0
    MOV R0, [0x24]
    ADC R0, R1
    MOV [0x24], R0
    MOV R1, 0
    MOV R0, [0x25]
    ADC R0, R1
    MOV [0x25], R0
    MOV R1, 0
    MOV R0, [0x26]
    ADC R0, R1
    MOV [0x26], R0
    MOV R1, 0
    MOV R0, [0x27]
    ADC R0, R1
    MOV [0x27], R0
    GOTO fn___bc_f32_int32_core
fn___bc_f32_int32_core:
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
    OR R1, R0
    MOV R0, [0x26]
    OR R1, R0
    MOV R0, [0x27]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .c32z_3
    GOTO .c32nz_4
.c32z_3:
    MOV R1, 0
    MOV R2, 0
    MOV R3, 0
    MOV R4, 0
    MOV R5, 0
    MOV R6, 0
    MOV R7, 0
    MOV R8, 0
    RET R0, 0
.c32nz_4:
    MOV R0, 14
    MOV [0x38], R0
    MOV R0, 9
    MOV [0x39], R0
.c32loop_5:
    MOV R0, [0x27]
    AND R0, 8
    CP R0, 0
    SKIP Z, 2
    GOTO .c32done_6
    GOTO .c32sh_7
.c32sh_7:
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
    MOV R1, 1
    MOV R0, [0x38]
    SUB R0, R1
    MOV [0x38], R0
    MOV R1, 0
    MOV R0, [0x39]
    SBB R0, R1
    MOV [0x39], R0
    GOTO .c32loop_5
.c32done_6:
    MOV R0, [0x21]
    AND R0, 8
    CP R0, 0
    SKIP NZ, 2
    GOTO .noround_8
    GOTO .rchk_9
.rchk_9:
    MOV R0, [0x21]
    AND R0, 4
    CP R0, 0
    SKIP NZ, 2
    GOTO .stk_10
    GOTO .rup_12
.stk_10:
    MOV R0, [0x21]
    AND R0, 3
    MOV R1, R0
    MOV R0, [0x20]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .lsb_11
    GOTO .rup_12
.lsb_11:
    MOV R0, [0x22]
    AND R0, 1
    CP R0, 0
    SKIP NZ, 2
    GOTO .noround_8
    GOTO .rup_12
.rup_12:
    MOV R1, 1
    MOV R0, [0x22]
    ADD R0, R1
    MOV [0x22], R0
    MOV R1, 0
    MOV R0, [0x23]
    ADC R0, R1
    MOV [0x23], R0
    MOV R1, 0
    MOV R0, [0x24]
    ADC R0, R1
    MOV [0x24], R0
    MOV R1, 0
    MOV R0, [0x25]
    ADC R0, R1
    MOV [0x25], R0
    MOV R1, 0
    MOV R0, [0x26]
    ADC R0, R1
    MOV [0x26], R0
    MOV R1, 0
    MOV R0, [0x27]
    ADC R0, R1
    MOV [0x27], R0
    SKIP NC, 2
    GOTO .rov_13
    GOTO .raf_14
.rov_13:
    MOV R0, 0
    ADD R0, 0
    MOV R0, [0x27]
    RRC R0
    MOV [0x27], R0
    MOV R0, [0x26]
    RRC R0
    MOV [0x26], R0
    MOV R0, [0x25]
    RRC R0
    MOV [0x25], R0
    MOV R0, [0x24]
    RRC R0
    MOV [0x24], R0
    MOV R0, [0x23]
    RRC R0
    MOV [0x23], R0
    MOV R0, [0x22]
    RRC R0
    MOV [0x22], R0
    MOV R1, 1
    MOV R0, [0x38]
    ADD R0, R1
    MOV [0x38], R0
    MOV R1, 0
    MOV R0, [0x39]
    ADC R0, R1
    MOV [0x39], R0
.raf_14:
.noround_8:
    MOV R0, [0x22]
    MOV R1, R0
    MOV R0, [0x23]
    MOV R2, R0
    MOV R0, [0x24]
    MOV R3, R0
    MOV R0, [0x25]
    MOV R4, R0
    MOV R0, [0x26]
    MOV R5, R0
    MOV R0, [0x27]
    AND R0, 7
    MOV R6, R0
    MOV R0, [0x38]
    AND R0, 1
    ADD R0, R0
    ADD R0, R0
    ADD R0, R0
    OR R6, R0
    MOV R0, [0x38]
    ADD R0, 0
    RRC R0
    AND R0, 7
    MOV R7, R0
    MOV R0, [0x39]
    AND R0, 1
    ADD R0, R0
    ADD R0, R0
    ADD R0, R0
    OR R7, R0
    MOV R0, [0x3A]
    MOV R9, R0
    MOV R0, [0x39]
    ADD R0, 0
    RRC R0
    AND R0, 7
    OR R0, R9
    MOV R8, R0
    RET R0, 0
fn___bc_u64_to_f32:
    MOV R0, [${v+0}]
    MOV [0x20], R0
    MOV R0, [${v+1}]
    MOV [0x21], R0
    MOV R0, [${v+2}]
    MOV [0x22], R0
    MOV R0, [${v+3}]
    MOV [0x23], R0
    MOV R0, [${v+4}]
    MOV [0x24], R0
    MOV R0, [${v+5}]
    MOV [0x25], R0
    MOV R0, [${v+6}]
    MOV [0x26], R0
    MOV R0, [${v+7}]
    MOV [0x27], R0
    MOV R0, [${v+8}]
    MOV [0x28], R0
    MOV R0, [${v+9}]
    MOV [0x29], R0
    MOV R0, [${v+10}]
    MOV [0x2A], R0
    MOV R0, [${v+11}]
    MOV [0x2B], R0
    MOV R0, [${v+12}]
    MOV [0x2C], R0
    MOV R0, [${v+13}]
    MOV [0x2D], R0
    MOV R0, [${v+14}]
    MOV [0x2E], R0
    MOV R0, [${v+15}]
    MOV [0x2F], R0
    MOV R0, 0
    MOV [0x32], R0
    GOTO fn___bc_f32_int64_core
fn___bc_i64_to_f32:
    MOV R0, [${v+0}]
    MOV [0x20], R0
    MOV R0, [${v+1}]
    MOV [0x21], R0
    MOV R0, [${v+2}]
    MOV [0x22], R0
    MOV R0, [${v+3}]
    MOV [0x23], R0
    MOV R0, [${v+4}]
    MOV [0x24], R0
    MOV R0, [${v+5}]
    MOV [0x25], R0
    MOV R0, [${v+6}]
    MOV [0x26], R0
    MOV R0, [${v+7}]
    MOV [0x27], R0
    MOV R0, [${v+8}]
    MOV [0x28], R0
    MOV R0, [${v+9}]
    MOV [0x29], R0
    MOV R0, [${v+10}]
    MOV [0x2A], R0
    MOV R0, [${v+11}]
    MOV [0x2B], R0
    MOV R0, [${v+12}]
    MOV [0x2C], R0
    MOV R0, [${v+13}]
    MOV [0x2D], R0
    MOV R0, [${v+14}]
    MOV [0x2E], R0
    MOV R0, [${v+15}]
    MOV [0x2F], R0
    MOV R0, [0x2F]
    AND R0, 8
    CP R0, 0
    SKIP NZ, 2
    GOTO .i64p_15
    GOTO .i64n_16
.i64p_15:
    MOV R0, 0
    MOV [0x32], R0
    GOTO fn___bc_f32_int64_core
.i64n_16:
    MOV R0, 8
    MOV [0x32], R0
    MOV R0, [0x20]
    XOR R0, 15
    MOV [0x20], R0
    MOV R0, [0x21]
    XOR R0, 15
    MOV [0x21], R0
    MOV R0, [0x22]
    XOR R0, 15
    MOV [0x22], R0
    MOV R0, [0x23]
    XOR R0, 15
    MOV [0x23], R0
    MOV R0, [0x24]
    XOR R0, 15
    MOV [0x24], R0
    MOV R0, [0x25]
    XOR R0, 15
    MOV [0x25], R0
    MOV R0, [0x26]
    XOR R0, 15
    MOV [0x26], R0
    MOV R0, [0x27]
    XOR R0, 15
    MOV [0x27], R0
    MOV R0, [0x28]
    XOR R0, 15
    MOV [0x28], R0
    MOV R0, [0x29]
    XOR R0, 15
    MOV [0x29], R0
    MOV R0, [0x2A]
    XOR R0, 15
    MOV [0x2A], R0
    MOV R0, [0x2B]
    XOR R0, 15
    MOV [0x2B], R0
    MOV R0, [0x2C]
    XOR R0, 15
    MOV [0x2C], R0
    MOV R0, [0x2D]
    XOR R0, 15
    MOV [0x2D], R0
    MOV R0, [0x2E]
    XOR R0, 15
    MOV [0x2E], R0
    MOV R0, [0x2F]
    XOR R0, 15
    MOV [0x2F], R0
    MOV R1, 1
    MOV R0, [0x20]
    ADD R0, R1
    MOV [0x20], R0
    MOV R1, 0
    MOV R0, [0x21]
    ADC R0, R1
    MOV [0x21], R0
    MOV R1, 0
    MOV R0, [0x22]
    ADC R0, R1
    MOV [0x22], R0
    MOV R1, 0
    MOV R0, [0x23]
    ADC R0, R1
    MOV [0x23], R0
    MOV R1, 0
    MOV R0, [0x24]
    ADC R0, R1
    MOV [0x24], R0
    MOV R1, 0
    MOV R0, [0x25]
    ADC R0, R1
    MOV [0x25], R0
    MOV R1, 0
    MOV R0, [0x26]
    ADC R0, R1
    MOV [0x26], R0
    MOV R1, 0
    MOV R0, [0x27]
    ADC R0, R1
    MOV [0x27], R0
    MOV R1, 0
    MOV R0, [0x28]
    ADC R0, R1
    MOV [0x28], R0
    MOV R1, 0
    MOV R0, [0x29]
    ADC R0, R1
    MOV [0x29], R0
    MOV R1, 0
    MOV R0, [0x2A]
    ADC R0, R1
    MOV [0x2A], R0
    MOV R1, 0
    MOV R0, [0x2B]
    ADC R0, R1
    MOV [0x2B], R0
    MOV R1, 0
    MOV R0, [0x2C]
    ADC R0, R1
    MOV [0x2C], R0
    MOV R1, 0
    MOV R0, [0x2D]
    ADC R0, R1
    MOV [0x2D], R0
    MOV R1, 0
    MOV R0, [0x2E]
    ADC R0, R1
    MOV [0x2E], R0
    MOV R1, 0
    MOV R0, [0x2F]
    ADC R0, R1
    MOV [0x2F], R0
    GOTO fn___bc_f32_int64_core
fn___bc_f32_int64_core:
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
    OR R1, R0
    MOV R0, [0x26]
    OR R1, R0
    MOV R0, [0x27]
    OR R1, R0
    MOV R0, [0x28]
    OR R1, R0
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
    SKIP NZ, 2
    GOTO .c64z_17
    GOTO .c64nz_18
.c64z_17:
    MOV R1, 0
    MOV R2, 0
    MOV R3, 0
    MOV R4, 0
    MOV R5, 0
    MOV R6, 0
    MOV R7, 0
    MOV R8, 0
    RET R0, 0
.c64nz_18:
    MOV R0, 14
    MOV [0x30], R0
    MOV R0, 11
    MOV [0x31], R0
.c64loop_19:
    MOV R0, [0x2F]
    AND R0, 8
    CP R0, 0
    SKIP Z, 2
    GOTO .c64done_20
    GOTO .c64sh_21
.c64sh_21:
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
    MOV R0, [0x28]
    ADC R0, R0
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
    MOV R0, [0x2E]
    ADC R0, R0
    MOV [0x2E], R0
    MOV R0, [0x2F]
    ADC R0, R0
    MOV [0x2F], R0
    MOV R1, 1
    MOV R0, [0x30]
    SUB R0, R1
    MOV [0x30], R0
    MOV R1, 0
    MOV R0, [0x31]
    SBB R0, R1
    MOV [0x31], R0
    GOTO .c64loop_19
.c64done_20:
    MOV R0, [0x29]
    AND R0, 8
    CP R0, 0
    SKIP NZ, 2
    GOTO .noround_22
    GOTO .rchk_23
.rchk_23:
    MOV R0, [0x29]
    AND R0, 4
    CP R0, 0
    SKIP NZ, 2
    GOTO .stk_24
    GOTO .rup_26
.stk_24:
    MOV R0, [0x29]
    AND R0, 3
    MOV R1, R0
    MOV R0, [0x28]
    OR R1, R0
    MOV R0, [0x20]
    OR R1, R0
    MOV R0, [0x21]
    OR R1, R0
    MOV R0, [0x22]
    OR R1, R0
    MOV R0, [0x23]
    OR R1, R0
    MOV R0, [0x24]
    OR R1, R0
    MOV R0, [0x25]
    OR R1, R0
    MOV R0, [0x26]
    OR R1, R0
    MOV R0, [0x27]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .lsb_25
    GOTO .rup_26
.lsb_25:
    MOV R0, [0x2A]
    AND R0, 1
    CP R0, 0
    SKIP NZ, 2
    GOTO .noround_22
    GOTO .rup_26
.rup_26:
    MOV R1, 1
    MOV R0, [0x2A]
    ADD R0, R1
    MOV [0x2A], R0
    MOV R1, 0
    MOV R0, [0x2B]
    ADC R0, R1
    MOV [0x2B], R0
    MOV R1, 0
    MOV R0, [0x2C]
    ADC R0, R1
    MOV [0x2C], R0
    MOV R1, 0
    MOV R0, [0x2D]
    ADC R0, R1
    MOV [0x2D], R0
    MOV R1, 0
    MOV R0, [0x2E]
    ADC R0, R1
    MOV [0x2E], R0
    MOV R1, 0
    MOV R0, [0x2F]
    ADC R0, R1
    MOV [0x2F], R0
    SKIP NC, 2
    GOTO .rov_27
    GOTO .raf_28
.rov_27:
    MOV R0, 0
    ADD R0, 0
    MOV R0, [0x2F]
    RRC R0
    MOV [0x2F], R0
    MOV R0, [0x2E]
    RRC R0
    MOV [0x2E], R0
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
    MOV R1, 1
    MOV R0, [0x30]
    ADD R0, R1
    MOV [0x30], R0
    MOV R1, 0
    MOV R0, [0x31]
    ADC R0, R1
    MOV [0x31], R0
.raf_28:
.noround_22:
    MOV R0, [0x2A]
    MOV R1, R0
    MOV R0, [0x2B]
    MOV R2, R0
    MOV R0, [0x2C]
    MOV R3, R0
    MOV R0, [0x2D]
    MOV R4, R0
    MOV R0, [0x2E]
    MOV R5, R0
    MOV R0, [0x2F]
    AND R0, 7
    MOV R6, R0
    MOV R0, [0x30]
    AND R0, 1
    ADD R0, R0
    ADD R0, R0
    ADD R0, R0
    OR R6, R0
    MOV R0, [0x30]
    ADD R0, 0
    RRC R0
    AND R0, 7
    MOV R7, R0
    MOV R0, [0x31]
    AND R0, 1
    ADD R0, R0
    ADD R0, R0
    ADD R0, R0
    OR R7, R0
    MOV R0, [0x32]
    MOV R9, R0
    MOV R0, [0x31]
    ADD R0, 0
    RRC R0
    AND R0, 7
    OR R0, R9
    MOV R8, R0
    RET R0, 0
fn___bc_f32_to_u32:
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
    MOV [0x28], R0
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
    MOV [0x29], R0
    MOV R0, [0x27]
    AND R0, 8
    MOV [0x37], R0
    MOV R0, [0x28]
    MOV R1, R0
    MOV R0, [0x29]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .f2i_z_32
    GOTO .f2i_nz_33
.f2i_z_32:
    MOV R1, 0
    MOV R2, 0
    MOV R3, 0
    MOV R4, 0
    MOV R5, 0
    MOV R6, 0
    MOV R7, 0
    MOV R8, 0
    RET R0, 0
.f2i_nz_33:
    MOV R0, [0x29]
    CP R0, 15
    SKIP Z, 2
    GOTO .f2i_ni_35
    GOTO .f2i_inf_34
.f2i_inf_34:
    MOV R0, [0x28]
    CP R0, 15
    SKIP Z, 2
    GOTO .f2i_ni_35
    GOTO .f2i_z_32
.f2i_ni_35:
    MOV R1, 15
    MOV R0, [0x28]
    SUB R0, R1
    MOV [0x2A], R0
    MOV R1, 7
    MOV R0, [0x29]
    SBB R0, R1
    MOV [0x2B], R0
    MOV R0, [0x2B]
    AND R0, 8
    CP R0, 0
    SKIP Z, 2
    GOTO .f2i_en_36
    GOTO .f2i_ep_37
.f2i_en_36:
    GOTO .f2i_z_32
.f2i_ep_37:
    MOV R0, [0x37]
    CP R0, 0
    SKIP Z, 2
    GOTO .f2i_un_39
    GOTO .f2i_up_38
.f2i_un_39:
    GOTO .f2i_z_32
.f2i_up_38:
    MOV R0, [0x2B]
    CP R0, 0
    SKIP Z, 2
    GOTO .f2i_high_41
    GOTO .f2i_low_42
.f2i_high_41:
    CP R0, 1
    SKIP Z, 2
    GOTO .f2i_sat_29
    GOTO .f2i_rng_40
.f2i_low_42:
.f2i_rng_40:
    MOV R0, 0
    MOV [0x2C], R0
    MOV [0x2D], R0
    MOV [0x2E], R0
    MOV [0x2F], R0
    MOV [0x30], R0
    MOV [0x31], R0
    MOV [0x32], R0
    MOV [0x33], R0
    MOV R0, [0x20]
    MOV [0x2C], R0
    MOV R0, [0x21]
    MOV [0x2D], R0
    MOV R0, [0x22]
    MOV [0x2E], R0
    MOV R0, [0x23]
    MOV [0x2F], R0
    MOV R0, [0x24]
    MOV [0x30], R0
    MOV R0, [0x25]
    AND R0, 7
    OR R0, 8
    MOV [0x31], R0
    MOV R0, [0x2B]
    CP R0, 0
    SKIP Z, 2
    GOTO .f2i_hdir_45
    GOTO .f2i_right_44
.f2i_hdir_45:
    MOV R0, [0x2A]
    CP R0, 7
    SKIP NC, 2
    GOTO .f2i_left_43
    GOTO .f2i_right_44
.f2i_left_43:
    MOV R1, 7
    MOV R0, [0x2A]
    SUB R0, R1
    MOV [0x34], R0
    MOV R1, 1
    MOV R0, [0x2B]
    SBB R0, R1
    MOV [0x35], R0
    MOV R0, 0
    MOV [0x36], R0
    GOTO .f2i_shift_46
.f2i_right_44:
    MOV R0, [0x2A]
    MOV R1, R0
    MOV R0, 7
    SUB R0, R1
    MOV [0x34], R0
    MOV R0, [0x2B]
    MOV R1, R0
    MOV R0, 1
    SBB R0, R1
    MOV [0x35], R0
    MOV R0, 1
    MOV [0x36], R0
    GOTO .f2i_shift_46
.f2i_shift_46:
.f2i_loop_47:
    MOV R0, [0x34]
    MOV R1, R0
    MOV R0, [0x35]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .f2i_done_49
    GOTO .f2i_body_48
.f2i_body_48:
    MOV R0, [0x36]
    CP R0, 0
    SKIP Z, 2
    GOTO .f2i_dor_51
    GOTO .f2i_dol_50
.f2i_dol_50:
    MOV R0, [0x2C]
    ADD R0, R0
    MOV [0x2C], R0
    MOV R0, [0x2D]
    ADC R0, R0
    MOV [0x2D], R0
    MOV R0, [0x2E]
    ADC R0, R0
    MOV [0x2E], R0
    MOV R0, [0x2F]
    ADC R0, R0
    MOV [0x2F], R0
    MOV R0, [0x30]
    ADC R0, R0
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
    GOTO .f2i_dec_52
.f2i_dor_51:
    MOV R0, 0
    ADD R0, 0
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
    MOV R0, [0x2F]
    RRC R0
    MOV [0x2F], R0
    MOV R0, [0x2E]
    RRC R0
    MOV [0x2E], R0
    MOV R0, [0x2D]
    RRC R0
    MOV [0x2D], R0
    MOV R0, [0x2C]
    RRC R0
    MOV [0x2C], R0
.f2i_dec_52:
    MOV R1, 1
    MOV R0, [0x34]
    SUB R0, R1
    MOV [0x34], R0
    MOV R1, 0
    MOV R0, [0x35]
    SBB R0, R1
    MOV [0x35], R0
    GOTO .f2i_loop_47
.f2i_done_49:
    MOV R0, [0x2C]
    MOV R1, R0
    MOV R0, [0x2D]
    MOV R2, R0
    MOV R0, [0x2E]
    MOV R3, R0
    MOV R0, [0x2F]
    MOV R4, R0
    MOV R0, [0x30]
    MOV R5, R0
    MOV R0, [0x31]
    MOV R6, R0
    MOV R0, [0x32]
    MOV R7, R0
    MOV R0, [0x33]
    MOV R8, R0
    RET R0, 0
.f2i_sat_29:
    GOTO .f2i_smax_30
.f2i_smax_30:
    MOV R1, 15
    MOV R2, 15
    MOV R3, 15
    MOV R4, 15
    MOV R5, 15
    MOV R6, 15
    MOV R7, 15
    MOV R8, 15
    RET R0, 0
.f2i_smin_31:
    MOV R1, 0
    MOV R2, 0
    MOV R3, 0
    MOV R4, 0
    MOV R5, 0
    MOV R6, 0
    MOV R7, 0
    MOV R8, 8
    RET R0, 0
fn___bc_f32_to_i32:
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
    MOV [0x28], R0
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
    MOV [0x29], R0
    MOV R0, [0x27]
    AND R0, 8
    MOV [0x37], R0
    MOV R0, [0x28]
    MOV R1, R0
    MOV R0, [0x29]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .f2i_z_56
    GOTO .f2i_nz_57
.f2i_z_56:
    MOV R1, 0
    MOV R2, 0
    MOV R3, 0
    MOV R4, 0
    MOV R5, 0
    MOV R6, 0
    MOV R7, 0
    MOV R8, 0
    RET R0, 0
.f2i_nz_57:
    MOV R0, [0x29]
    CP R0, 15
    SKIP Z, 2
    GOTO .f2i_ni_59
    GOTO .f2i_inf_58
.f2i_inf_58:
    MOV R0, [0x28]
    CP R0, 15
    SKIP Z, 2
    GOTO .f2i_ni_59
    GOTO .f2i_z_56
.f2i_ni_59:
    MOV R1, 15
    MOV R0, [0x28]
    SUB R0, R1
    MOV [0x2A], R0
    MOV R1, 7
    MOV R0, [0x29]
    SBB R0, R1
    MOV [0x2B], R0
    MOV R0, [0x2B]
    AND R0, 8
    CP R0, 0
    SKIP Z, 2
    GOTO .f2i_en_60
    GOTO .f2i_ep_61
.f2i_en_60:
    GOTO .f2i_z_56
.f2i_ep_61:
    MOV R0, [0x2B]
    CP R0, 0
    SKIP Z, 2
    GOTO .f2i_high_63
    GOTO .f2i_low_64
.f2i_high_63:
    CP R0, 1
    SKIP Z, 2
    GOTO .f2i_sat_53
    MOV R0, [0x2A]
    CP R0, 15
    SKIP NC, 2
    GOTO .f2i_sat_53
    GOTO .f2i_rng_62
.f2i_low_64:
.f2i_rng_62:
    MOV R0, 0
    MOV [0x2C], R0
    MOV [0x2D], R0
    MOV [0x2E], R0
    MOV [0x2F], R0
    MOV [0x30], R0
    MOV [0x31], R0
    MOV [0x32], R0
    MOV [0x33], R0
    MOV R0, [0x20]
    MOV [0x2C], R0
    MOV R0, [0x21]
    MOV [0x2D], R0
    MOV R0, [0x22]
    MOV [0x2E], R0
    MOV R0, [0x23]
    MOV [0x2F], R0
    MOV R0, [0x24]
    MOV [0x30], R0
    MOV R0, [0x25]
    AND R0, 7
    OR R0, 8
    MOV [0x31], R0
    MOV R0, [0x2B]
    CP R0, 0
    SKIP Z, 2
    GOTO .f2i_hdir_67
    GOTO .f2i_right_66
.f2i_hdir_67:
    MOV R0, [0x2A]
    CP R0, 7
    SKIP NC, 2
    GOTO .f2i_left_65
    GOTO .f2i_right_66
.f2i_left_65:
    MOV R1, 7
    MOV R0, [0x2A]
    SUB R0, R1
    MOV [0x34], R0
    MOV R1, 1
    MOV R0, [0x2B]
    SBB R0, R1
    MOV [0x35], R0
    MOV R0, 0
    MOV [0x36], R0
    GOTO .f2i_shift_68
.f2i_right_66:
    MOV R0, [0x2A]
    MOV R1, R0
    MOV R0, 7
    SUB R0, R1
    MOV [0x34], R0
    MOV R0, [0x2B]
    MOV R1, R0
    MOV R0, 1
    SBB R0, R1
    MOV [0x35], R0
    MOV R0, 1
    MOV [0x36], R0
    GOTO .f2i_shift_68
.f2i_shift_68:
.f2i_loop_69:
    MOV R0, [0x34]
    MOV R1, R0
    MOV R0, [0x35]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .f2i_done_71
    GOTO .f2i_body_70
.f2i_body_70:
    MOV R0, [0x36]
    CP R0, 0
    SKIP Z, 2
    GOTO .f2i_dor_73
    GOTO .f2i_dol_72
.f2i_dol_72:
    MOV R0, [0x2C]
    ADD R0, R0
    MOV [0x2C], R0
    MOV R0, [0x2D]
    ADC R0, R0
    MOV [0x2D], R0
    MOV R0, [0x2E]
    ADC R0, R0
    MOV [0x2E], R0
    MOV R0, [0x2F]
    ADC R0, R0
    MOV [0x2F], R0
    MOV R0, [0x30]
    ADC R0, R0
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
    GOTO .f2i_dec_74
.f2i_dor_73:
    MOV R0, 0
    ADD R0, 0
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
    MOV R0, [0x2F]
    RRC R0
    MOV [0x2F], R0
    MOV R0, [0x2E]
    RRC R0
    MOV [0x2E], R0
    MOV R0, [0x2D]
    RRC R0
    MOV [0x2D], R0
    MOV R0, [0x2C]
    RRC R0
    MOV [0x2C], R0
.f2i_dec_74:
    MOV R1, 1
    MOV R0, [0x34]
    SUB R0, R1
    MOV [0x34], R0
    MOV R1, 0
    MOV R0, [0x35]
    SBB R0, R1
    MOV [0x35], R0
    GOTO .f2i_loop_69
.f2i_done_71:
    MOV R0, [0x37]
    CP R0, 0
    SKIP Z, 2
    GOTO .f2i_sn_76
    GOTO .f2i_sp_75
.f2i_sn_76:
    MOV R0, [0x2C]
    XOR R0, 15
    MOV [0x2C], R0
    MOV R0, [0x2D]
    XOR R0, 15
    MOV [0x2D], R0
    MOV R0, [0x2E]
    XOR R0, 15
    MOV [0x2E], R0
    MOV R0, [0x2F]
    XOR R0, 15
    MOV [0x2F], R0
    MOV R0, [0x30]
    XOR R0, 15
    MOV [0x30], R0
    MOV R0, [0x31]
    XOR R0, 15
    MOV [0x31], R0
    MOV R0, [0x32]
    XOR R0, 15
    MOV [0x32], R0
    MOV R0, [0x33]
    XOR R0, 15
    MOV [0x33], R0
    MOV R1, 1
    MOV R0, [0x2C]
    ADD R0, R1
    MOV [0x2C], R0
    MOV R1, 0
    MOV R0, [0x2D]
    ADC R0, R1
    MOV [0x2D], R0
    MOV R1, 0
    MOV R0, [0x2E]
    ADC R0, R1
    MOV [0x2E], R0
    MOV R1, 0
    MOV R0, [0x2F]
    ADC R0, R1
    MOV [0x2F], R0
    MOV R1, 0
    MOV R0, [0x30]
    ADC R0, R1
    MOV [0x30], R0
    MOV R1, 0
    MOV R0, [0x31]
    ADC R0, R1
    MOV [0x31], R0
    MOV R1, 0
    MOV R0, [0x32]
    ADC R0, R1
    MOV [0x32], R0
    MOV R1, 0
    MOV R0, [0x33]
    ADC R0, R1
    MOV [0x33], R0
    GOTO .f2i_sd_77
.f2i_sp_75:
.f2i_sd_77:
    MOV R0, [0x2C]
    MOV R1, R0
    MOV R0, [0x2D]
    MOV R2, R0
    MOV R0, [0x2E]
    MOV R3, R0
    MOV R0, [0x2F]
    MOV R4, R0
    MOV R0, [0x30]
    MOV R5, R0
    MOV R0, [0x31]
    MOV R6, R0
    MOV R0, [0x32]
    MOV R7, R0
    MOV R0, [0x33]
    MOV R8, R0
    RET R0, 0
.f2i_sat_53:
    MOV R0, [0x37]
    CP R0, 0
    SKIP Z, 2
    GOTO .f2i_smin_55
    GOTO .f2i_smax_54
.f2i_smax_54:
    MOV R1, 15
    MOV R2, 15
    MOV R3, 15
    MOV R4, 15
    MOV R5, 15
    MOV R6, 15
    MOV R7, 15
    MOV R8, 7
    RET R0, 0
.f2i_smin_55:
    MOV R1, 0
    MOV R2, 0
    MOV R3, 0
    MOV R4, 0
    MOV R5, 0
    MOV R6, 0
    MOV R7, 0
    MOV R8, 8
    RET R0, 0
fn___bc_f32_to_u64_asm:
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
    MOV [0x28], R0
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
    MOV [0x29], R0
    MOV R0, [0x27]
    AND R0, 8
    MOV [0x2F], R0
    MOV R0, [0x28]
    MOV R1, R0
    MOV R0, [0x29]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .f2l_z_81
    GOTO .f2l_nz_82
.f2l_z_81:
    GOTO .f2l_zero_83
.f2l_nz_82:
    MOV R0, [0x29]
    CP R0, 15
    SKIP Z, 2
    GOTO .f2l_ni_85
    GOTO .f2l_inf_84
.f2l_inf_84:
    MOV R0, [0x28]
    CP R0, 15
    SKIP Z, 2
    GOTO .f2l_ni_85
    GOTO .f2l_zero_83
.f2l_ni_85:
    MOV R1, 15
    MOV R0, [0x28]
    SUB R0, R1
    MOV [0x2A], R0
    MOV R1, 7
    MOV R0, [0x29]
    SBB R0, R1
    MOV [0x2B], R0
    MOV R0, [0x2B]
    AND R0, 8
    CP R0, 0
    SKIP Z, 2
    GOTO .f2l_en_86
    GOTO .f2l_ep_87
.f2l_en_86:
    GOTO .f2l_zero_83
.f2l_ep_87:
    MOV R0, [0x2F]
    CP R0, 0
    SKIP Z, 2
    GOTO .f2l_un_89
    GOTO .f2l_up_88
.f2l_un_89:
    GOTO .f2l_zero_83
.f2l_up_88:
    MOV R0, [0x2B]
    CP R0, 0
    SKIP Z, 2
    GOTO .f2l_high_91
    GOTO .f2l_low_92
.f2l_high_91:
    CP R0, 4
    SKIP NC, 2
    GOTO .f2l_sat_78
    GOTO .f2l_rng_90
.f2l_low_92:
.f2l_rng_90:
    MOV R0, 0
    MOV [0x30], R0
    MOV [0x31], R0
    MOV [0x32], R0
    MOV [0x33], R0
    MOV [0x34], R0
    MOV [0x35], R0
    MOV [0x36], R0
    MOV [0x37], R0
    MOV [0x38], R0
    MOV [0x39], R0
    MOV [0x3A], R0
    MOV [0x3B], R0
    MOV [0x3C], R0
    MOV [0x3D], R0
    MOV [0x3E], R0
    MOV [0x3F], R0
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
    MOV R0, [0x2B]
    CP R0, 0
    SKIP Z, 2
    GOTO .f2i_hdir_95
    GOTO .f2l_right_94
.f2i_hdir_95:
    CP R0, 1
    SKIP Z, 2
    GOTO .f2l_left_93
    MOV R0, [0x2A]
    CP R0, 7
    SKIP NC, 2
    GOTO .f2l_left_93
    GOTO .f2l_right_94
.f2l_left_93:
    MOV R1, 7
    MOV R0, [0x2A]
    SUB R0, R1
    MOV [0x2C], R0
    MOV R1, 1
    MOV R0, [0x2B]
    SBB R0, R1
    MOV [0x2D], R0
    MOV R0, 0
    MOV [0x2E], R0
    GOTO .f2l_shift_96
.f2l_right_94:
    MOV R0, [0x2A]
    MOV R1, R0
    MOV R0, 7
    SUB R0, R1
    MOV [0x2C], R0
    MOV R0, [0x2B]
    MOV R1, R0
    MOV R0, 1
    SBB R0, R1
    MOV [0x2D], R0
    MOV R0, 1
    MOV [0x2E], R0
    GOTO .f2l_shift_96
.f2l_shift_96:
.f2l_loop_97:
    MOV R0, [0x2C]
    MOV R1, R0
    MOV R0, [0x2D]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .f2l_done_99
    GOTO .f2l_body_98
.f2l_body_98:
    MOV R0, [0x2E]
    CP R0, 0
    SKIP Z, 2
    GOTO .f2l_dor_101
    GOTO .f2l_dol_100
.f2l_dol_100:
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
    MOV R0, [0x38]
    ADC R0, R0
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
    GOTO .f2l_dec_102
.f2l_dor_101:
    MOV R0, 0
    ADD R0, 0
    MOV R0, [0x3F]
    RRC R0
    MOV [0x3F], R0
    MOV R0, [0x3E]
    RRC R0
    MOV [0x3E], R0
    MOV R0, [0x3D]
    RRC R0
    MOV [0x3D], R0
    MOV R0, [0x3C]
    RRC R0
    MOV [0x3C], R0
    MOV R0, [0x3B]
    RRC R0
    MOV [0x3B], R0
    MOV R0, [0x3A]
    RRC R0
    MOV [0x3A], R0
    MOV R0, [0x39]
    RRC R0
    MOV [0x39], R0
    MOV R0, [0x38]
    RRC R0
    MOV [0x38], R0
    MOV R0, [0x37]
    RRC R0
    MOV [0x37], R0
    MOV R0, [0x36]
    RRC R0
    MOV [0x36], R0
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
.f2l_dec_102:
    MOV R1, 1
    MOV R0, [0x2C]
    SUB R0, R1
    MOV [0x2C], R0
    MOV R1, 0
    MOV R0, [0x2D]
    SBB R0, R1
    MOV [0x2D], R0
    GOTO .f2l_loop_97
.f2l_done_99:
    MOV R0, [0x30]
    MOV [${__bc_conv64_f32+0}], R0
    MOV R0, [0x31]
    MOV [${__bc_conv64_f32+1}], R0
    MOV R0, [0x32]
    MOV [${__bc_conv64_f32+2}], R0
    MOV R0, [0x33]
    MOV [${__bc_conv64_f32+3}], R0
    MOV R0, [0x34]
    MOV [${__bc_conv64_f32+4}], R0
    MOV R0, [0x35]
    MOV [${__bc_conv64_f32+5}], R0
    MOV R0, [0x36]
    MOV [${__bc_conv64_f32+6}], R0
    MOV R0, [0x37]
    MOV [${__bc_conv64_f32+7}], R0
    MOV R0, [0x38]
    MOV [${__bc_conv64_f32+8}], R0
    MOV R0, [0x39]
    MOV [${__bc_conv64_f32+9}], R0
    MOV R0, [0x3A]
    MOV [${__bc_conv64_f32+10}], R0
    MOV R0, [0x3B]
    MOV [${__bc_conv64_f32+11}], R0
    MOV R0, [0x3C]
    MOV [${__bc_conv64_f32+12}], R0
    MOV R0, [0x3D]
    MOV [${__bc_conv64_f32+13}], R0
    MOV R0, [0x3E]
    MOV [${__bc_conv64_f32+14}], R0
    MOV R0, [0x3F]
    MOV [${__bc_conv64_f32+15}], R0
    RET R0, 0
.f2l_zero_83:
    MOV R0, 0
    MOV [${__bc_conv64_f32+0}], R0
    MOV [${__bc_conv64_f32+1}], R0
    MOV [${__bc_conv64_f32+2}], R0
    MOV [${__bc_conv64_f32+3}], R0
    MOV [${__bc_conv64_f32+4}], R0
    MOV [${__bc_conv64_f32+5}], R0
    MOV [${__bc_conv64_f32+6}], R0
    MOV [${__bc_conv64_f32+7}], R0
    MOV [${__bc_conv64_f32+8}], R0
    MOV [${__bc_conv64_f32+9}], R0
    MOV [${__bc_conv64_f32+10}], R0
    MOV [${__bc_conv64_f32+11}], R0
    MOV [${__bc_conv64_f32+12}], R0
    MOV [${__bc_conv64_f32+13}], R0
    MOV [${__bc_conv64_f32+14}], R0
    MOV [${__bc_conv64_f32+15}], R0
    RET R0, 0
.f2l_sat_78:
    GOTO .f2l_smax_79
.f2l_smax_79:
    MOV R0, 15
    MOV [${__bc_conv64_f32+0}], R0
    MOV [${__bc_conv64_f32+1}], R0
    MOV [${__bc_conv64_f32+2}], R0
    MOV [${__bc_conv64_f32+3}], R0
    MOV [${__bc_conv64_f32+4}], R0
    MOV [${__bc_conv64_f32+5}], R0
    MOV [${__bc_conv64_f32+6}], R0
    MOV [${__bc_conv64_f32+7}], R0
    MOV [${__bc_conv64_f32+8}], R0
    MOV [${__bc_conv64_f32+9}], R0
    MOV [${__bc_conv64_f32+10}], R0
    MOV [${__bc_conv64_f32+11}], R0
    MOV [${__bc_conv64_f32+12}], R0
    MOV [${__bc_conv64_f32+13}], R0
    MOV [${__bc_conv64_f32+14}], R0
    MOV R0, 15
    MOV [${__bc_conv64_f32+15}], R0
    RET R0, 0
.f2l_smin_80:
    MOV R0, 0
    MOV [${__bc_conv64_f32+0}], R0
    MOV [${__bc_conv64_f32+1}], R0
    MOV [${__bc_conv64_f32+2}], R0
    MOV [${__bc_conv64_f32+3}], R0
    MOV [${__bc_conv64_f32+4}], R0
    MOV [${__bc_conv64_f32+5}], R0
    MOV [${__bc_conv64_f32+6}], R0
    MOV [${__bc_conv64_f32+7}], R0
    MOV [${__bc_conv64_f32+8}], R0
    MOV [${__bc_conv64_f32+9}], R0
    MOV [${__bc_conv64_f32+10}], R0
    MOV [${__bc_conv64_f32+11}], R0
    MOV [${__bc_conv64_f32+12}], R0
    MOV [${__bc_conv64_f32+13}], R0
    MOV [${__bc_conv64_f32+14}], R0
    MOV R0, 8
    MOV [${__bc_conv64_f32+15}], R0
    RET R0, 0
fn___bc_f32_to_i64_asm:
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
    MOV [0x28], R0
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
    MOV [0x29], R0
    MOV R0, [0x27]
    AND R0, 8
    MOV [0x2F], R0
    MOV R0, [0x28]
    MOV R1, R0
    MOV R0, [0x29]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .f2l_z_106
    GOTO .f2l_nz_107
.f2l_z_106:
    GOTO .f2l_zero_108
.f2l_nz_107:
    MOV R0, [0x29]
    CP R0, 15
    SKIP Z, 2
    GOTO .f2l_ni_110
    GOTO .f2l_inf_109
.f2l_inf_109:
    MOV R0, [0x28]
    CP R0, 15
    SKIP Z, 2
    GOTO .f2l_ni_110
    GOTO .f2l_zero_108
.f2l_ni_110:
    MOV R1, 15
    MOV R0, [0x28]
    SUB R0, R1
    MOV [0x2A], R0
    MOV R1, 7
    MOV R0, [0x29]
    SBB R0, R1
    MOV [0x2B], R0
    MOV R0, [0x2B]
    AND R0, 8
    CP R0, 0
    SKIP Z, 2
    GOTO .f2l_en_111
    GOTO .f2l_ep_112
.f2l_en_111:
    GOTO .f2l_zero_108
.f2l_ep_112:
    MOV R0, [0x2B]
    CP R0, 0
    SKIP Z, 2
    GOTO .f2l_high_114
    GOTO .f2l_low_115
.f2l_high_114:
    CP R0, 4
    SKIP NC, 2
    GOTO .f2l_sat_103
    CP R0, 3
    SKIP Z, 2
    GOTO .f2l_rng_113
    MOV R0, [0x2A]
    CP R0, 15
    SKIP NC, 2
    GOTO .f2l_sat_103
    GOTO .f2l_rng_113
.f2l_low_115:
.f2l_rng_113:
    MOV R0, 0
    MOV [0x30], R0
    MOV [0x31], R0
    MOV [0x32], R0
    MOV [0x33], R0
    MOV [0x34], R0
    MOV [0x35], R0
    MOV [0x36], R0
    MOV [0x37], R0
    MOV [0x38], R0
    MOV [0x39], R0
    MOV [0x3A], R0
    MOV [0x3B], R0
    MOV [0x3C], R0
    MOV [0x3D], R0
    MOV [0x3E], R0
    MOV [0x3F], R0
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
    MOV R0, [0x2B]
    CP R0, 0
    SKIP Z, 2
    GOTO .f2i_hdir_118
    GOTO .f2l_right_117
.f2i_hdir_118:
    CP R0, 1
    SKIP Z, 2
    GOTO .f2l_left_116
    MOV R0, [0x2A]
    CP R0, 7
    SKIP NC, 2
    GOTO .f2l_left_116
    GOTO .f2l_right_117
.f2l_left_116:
    MOV R1, 7
    MOV R0, [0x2A]
    SUB R0, R1
    MOV [0x2C], R0
    MOV R1, 1
    MOV R0, [0x2B]
    SBB R0, R1
    MOV [0x2D], R0
    MOV R0, 0
    MOV [0x2E], R0
    GOTO .f2l_shift_119
.f2l_right_117:
    MOV R0, [0x2A]
    MOV R1, R0
    MOV R0, 7
    SUB R0, R1
    MOV [0x2C], R0
    MOV R0, [0x2B]
    MOV R1, R0
    MOV R0, 1
    SBB R0, R1
    MOV [0x2D], R0
    MOV R0, 1
    MOV [0x2E], R0
    GOTO .f2l_shift_119
.f2l_shift_119:
.f2l_loop_120:
    MOV R0, [0x2C]
    MOV R1, R0
    MOV R0, [0x2D]
    OR R1, R0
    MOV R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .f2l_done_122
    GOTO .f2l_body_121
.f2l_body_121:
    MOV R0, [0x2E]
    CP R0, 0
    SKIP Z, 2
    GOTO .f2l_dor_124
    GOTO .f2l_dol_123
.f2l_dol_123:
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
    MOV R0, [0x38]
    ADC R0, R0
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
    GOTO .f2l_dec_125
.f2l_dor_124:
    MOV R0, 0
    ADD R0, 0
    MOV R0, [0x3F]
    RRC R0
    MOV [0x3F], R0
    MOV R0, [0x3E]
    RRC R0
    MOV [0x3E], R0
    MOV R0, [0x3D]
    RRC R0
    MOV [0x3D], R0
    MOV R0, [0x3C]
    RRC R0
    MOV [0x3C], R0
    MOV R0, [0x3B]
    RRC R0
    MOV [0x3B], R0
    MOV R0, [0x3A]
    RRC R0
    MOV [0x3A], R0
    MOV R0, [0x39]
    RRC R0
    MOV [0x39], R0
    MOV R0, [0x38]
    RRC R0
    MOV [0x38], R0
    MOV R0, [0x37]
    RRC R0
    MOV [0x37], R0
    MOV R0, [0x36]
    RRC R0
    MOV [0x36], R0
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
.f2l_dec_125:
    MOV R1, 1
    MOV R0, [0x2C]
    SUB R0, R1
    MOV [0x2C], R0
    MOV R1, 0
    MOV R0, [0x2D]
    SBB R0, R1
    MOV [0x2D], R0
    GOTO .f2l_loop_120
.f2l_done_122:
    MOV R0, [0x2F]
    CP R0, 0
    SKIP Z, 2
    GOTO .f2l_sn_127
    GOTO .f2l_sp_126
.f2l_sn_127:
    MOV R0, [0x30]
    XOR R0, 15
    MOV [0x30], R0
    MOV R0, [0x31]
    XOR R0, 15
    MOV [0x31], R0
    MOV R0, [0x32]
    XOR R0, 15
    MOV [0x32], R0
    MOV R0, [0x33]
    XOR R0, 15
    MOV [0x33], R0
    MOV R0, [0x34]
    XOR R0, 15
    MOV [0x34], R0
    MOV R0, [0x35]
    XOR R0, 15
    MOV [0x35], R0
    MOV R0, [0x36]
    XOR R0, 15
    MOV [0x36], R0
    MOV R0, [0x37]
    XOR R0, 15
    MOV [0x37], R0
    MOV R0, [0x38]
    XOR R0, 15
    MOV [0x38], R0
    MOV R0, [0x39]
    XOR R0, 15
    MOV [0x39], R0
    MOV R0, [0x3A]
    XOR R0, 15
    MOV [0x3A], R0
    MOV R0, [0x3B]
    XOR R0, 15
    MOV [0x3B], R0
    MOV R0, [0x3C]
    XOR R0, 15
    MOV [0x3C], R0
    MOV R0, [0x3D]
    XOR R0, 15
    MOV [0x3D], R0
    MOV R0, [0x3E]
    XOR R0, 15
    MOV [0x3E], R0
    MOV R0, [0x3F]
    XOR R0, 15
    MOV [0x3F], R0
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
    MOV R1, 0
    MOV R0, [0x33]
    ADC R0, R1
    MOV [0x33], R0
    MOV R1, 0
    MOV R0, [0x34]
    ADC R0, R1
    MOV [0x34], R0
    MOV R1, 0
    MOV R0, [0x35]
    ADC R0, R1
    MOV [0x35], R0
    MOV R1, 0
    MOV R0, [0x36]
    ADC R0, R1
    MOV [0x36], R0
    MOV R1, 0
    MOV R0, [0x37]
    ADC R0, R1
    MOV [0x37], R0
    MOV R1, 0
    MOV R0, [0x38]
    ADC R0, R1
    MOV [0x38], R0
    MOV R1, 0
    MOV R0, [0x39]
    ADC R0, R1
    MOV [0x39], R0
    MOV R1, 0
    MOV R0, [0x3A]
    ADC R0, R1
    MOV [0x3A], R0
    MOV R1, 0
    MOV R0, [0x3B]
    ADC R0, R1
    MOV [0x3B], R0
    MOV R1, 0
    MOV R0, [0x3C]
    ADC R0, R1
    MOV [0x3C], R0
    MOV R1, 0
    MOV R0, [0x3D]
    ADC R0, R1
    MOV [0x3D], R0
    MOV R1, 0
    MOV R0, [0x3E]
    ADC R0, R1
    MOV [0x3E], R0
    MOV R1, 0
    MOV R0, [0x3F]
    ADC R0, R1
    MOV [0x3F], R0
    GOTO .f2l_sd_128
.f2l_sp_126:
.f2l_sd_128:
    MOV R0, [0x30]
    MOV [${__bc_conv64_f32+0}], R0
    MOV R0, [0x31]
    MOV [${__bc_conv64_f32+1}], R0
    MOV R0, [0x32]
    MOV [${__bc_conv64_f32+2}], R0
    MOV R0, [0x33]
    MOV [${__bc_conv64_f32+3}], R0
    MOV R0, [0x34]
    MOV [${__bc_conv64_f32+4}], R0
    MOV R0, [0x35]
    MOV [${__bc_conv64_f32+5}], R0
    MOV R0, [0x36]
    MOV [${__bc_conv64_f32+6}], R0
    MOV R0, [0x37]
    MOV [${__bc_conv64_f32+7}], R0
    MOV R0, [0x38]
    MOV [${__bc_conv64_f32+8}], R0
    MOV R0, [0x39]
    MOV [${__bc_conv64_f32+9}], R0
    MOV R0, [0x3A]
    MOV [${__bc_conv64_f32+10}], R0
    MOV R0, [0x3B]
    MOV [${__bc_conv64_f32+11}], R0
    MOV R0, [0x3C]
    MOV [${__bc_conv64_f32+12}], R0
    MOV R0, [0x3D]
    MOV [${__bc_conv64_f32+13}], R0
    MOV R0, [0x3E]
    MOV [${__bc_conv64_f32+14}], R0
    MOV R0, [0x3F]
    MOV [${__bc_conv64_f32+15}], R0
    RET R0, 0
.f2l_zero_108:
    MOV R0, 0
    MOV [${__bc_conv64_f32+0}], R0
    MOV [${__bc_conv64_f32+1}], R0
    MOV [${__bc_conv64_f32+2}], R0
    MOV [${__bc_conv64_f32+3}], R0
    MOV [${__bc_conv64_f32+4}], R0
    MOV [${__bc_conv64_f32+5}], R0
    MOV [${__bc_conv64_f32+6}], R0
    MOV [${__bc_conv64_f32+7}], R0
    MOV [${__bc_conv64_f32+8}], R0
    MOV [${__bc_conv64_f32+9}], R0
    MOV [${__bc_conv64_f32+10}], R0
    MOV [${__bc_conv64_f32+11}], R0
    MOV [${__bc_conv64_f32+12}], R0
    MOV [${__bc_conv64_f32+13}], R0
    MOV [${__bc_conv64_f32+14}], R0
    MOV [${__bc_conv64_f32+15}], R0
    RET R0, 0
.f2l_sat_103:
    MOV R0, [0x2F]
    CP R0, 0
    SKIP Z, 2
    GOTO .f2l_smin_105
    GOTO .f2l_smax_104
.f2l_smax_104:
    MOV R0, 15
    MOV [${__bc_conv64_f32+0}], R0
    MOV [${__bc_conv64_f32+1}], R0
    MOV [${__bc_conv64_f32+2}], R0
    MOV [${__bc_conv64_f32+3}], R0
    MOV [${__bc_conv64_f32+4}], R0
    MOV [${__bc_conv64_f32+5}], R0
    MOV [${__bc_conv64_f32+6}], R0
    MOV [${__bc_conv64_f32+7}], R0
    MOV [${__bc_conv64_f32+8}], R0
    MOV [${__bc_conv64_f32+9}], R0
    MOV [${__bc_conv64_f32+10}], R0
    MOV [${__bc_conv64_f32+11}], R0
    MOV [${__bc_conv64_f32+12}], R0
    MOV [${__bc_conv64_f32+13}], R0
    MOV [${__bc_conv64_f32+14}], R0
    MOV R0, 7
    MOV [${__bc_conv64_f32+15}], R0
    RET R0, 0
.f2l_smin_105:
    MOV R0, 0
    MOV [${__bc_conv64_f32+0}], R0
    MOV [${__bc_conv64_f32+1}], R0
    MOV [${__bc_conv64_f32+2}], R0
    MOV [${__bc_conv64_f32+3}], R0
    MOV [${__bc_conv64_f32+4}], R0
    MOV [${__bc_conv64_f32+5}], R0
    MOV [${__bc_conv64_f32+6}], R0
    MOV [${__bc_conv64_f32+7}], R0
    MOV [${__bc_conv64_f32+8}], R0
    MOV [${__bc_conv64_f32+9}], R0
    MOV [${__bc_conv64_f32+10}], R0
    MOV [${__bc_conv64_f32+11}], R0
    MOV [${__bc_conv64_f32+12}], R0
    MOV [${__bc_conv64_f32+13}], R0
    MOV [${__bc_conv64_f32+14}], R0
    MOV R0, 8
    MOV [${__bc_conv64_f32+15}], R0
    RET R0, 0

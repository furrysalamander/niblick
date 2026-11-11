; void mc_adjust_pos(char face)
;
; Adjusts the packed 8-byte block position in the BadgeC global `pong` by one
; block along the clicked face.  Face values are Minecraft 1.8:
;   0 = down (-Y), 1 = up (+Y), 2 = north (-Z), 3 = south (+Z),
;   4 = west (-X), 5 = east (+X).
;
; This operates directly on the packed bytes instead of decoding a 64-bit
; position.  The z field is assumed to stay below 256 for this void-world
; demo, so only byte 7 carries z; bytes 6/5 are handled for completeness.

fn_mc_adjust_pos:
    MOV R2, 0
    MOV R0, [${face}]
    CP R0, 0
    SKIP NZ, 2
    GOTO .down
    CP R0, 1
    SKIP NZ, 2
    GOTO .up
    CP R0, 2
    SKIP NZ, 2
    GOTO .north
    CP R0, 3
    SKIP NZ, 2
    GOTO .south
    CP R0, 4
    SKIP NZ, 2
    GOTO .west
    CP R0, 5
    SKIP NZ, 2
    GOTO .east
.done:
    RET R0, 0

; ---- up: y += 1 ----------------------------------------------------------
.up:
    MOV R0, [${pong+8}]
    ADD R0, 4
    MOV [${pong+8}], R0
    MOV R0, [${pong+9}]
    ADC R0, R2
    MOV [${pong+9}], R0
    SKIP C, 2
    GOTO .up_done
    MOV R0, [${pong+6}]
    ADD R0, 1
    MOV [${pong+6}], R0
    MOV R0, [${pong+7}]
    ADC R0, R2
    MOV [${pong+7}], R0
.up_done:
    GOTO .done

; ---- down: y -= 1 --------------------------------------------------------
.down:
    MOV R0, [${pong+8}]
    ADD R0, 0xC
    MOV [${pong+8}], R0
    MOV R0, [${pong+9}]
    MOV R4, 0xF
    ADC R0, R4
    MOV [${pong+9}], R0
    SKIP C, 2
    GOTO .down_borrow
    GOTO .down_done
.down_borrow:
    MOV R0, [${pong+6}]
    ADD R0, 0xF
    MOV [${pong+6}], R0
    MOV R0, [${pong+7}]
    MOV R4, 0xF
    ADC R0, R4
    MOV [${pong+7}], R0
.down_done:
    GOTO .done

; ---- north: z -= 1 -------------------------------------------------------
.north:
    MOV R0, [${pong+14}]
    MOV R1, R0
    MOV R0, [${pong+15}]
    OR R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .done
    MOV R0, [${pong+14}]
    ADD R0, 0xF
    MOV [${pong+14}], R0
    MOV R0, [${pong+15}]
    MOV R4, 0xF
    ADC R0, R4
    MOV [${pong+15}], R0
    GOTO .done

; ---- south: z += 1 -------------------------------------------------------
.south:
    MOV R0, [${pong+14}]
    ADD R0, 1
    MOV [${pong+14}], R0
    MOV R0, [${pong+15}]
    ADC R0, R2
    MOV [${pong+15}], R0
    GOTO .done

; ---- west: x -= 1 --------------------------------------------------------
.west:
    MOV R0, [${pong+4}]
    MOV R1, R0
    MOV R0, [${pong+5}]
    OR R0, R1
    MOV R6, R0
    MOV R0, [${pong+7}]
    MOV R1, R0
    MOV R3, 3
    AND R1, R3
    MOV R0, R6
    OR R0, R1
    CP R0, 0
    SKIP NZ, 2
    GOTO .done
    MOV R0, [${pong+6}]
    ADD R0, 0
    MOV [${pong+6}], R0
    MOV R0, [${pong+7}]
    MOV R4, 0xC
    ADC R0, R4
    MOV [${pong+7}], R0
    SKIP C, 2
    GOTO .west_b2
    GOTO .done
.west_b2:
    MOV R0, [${pong+4}]
    ADD R0, 0xF
    MOV [${pong+4}], R0
    MOV R0, [${pong+5}]
    MOV R4, 0xF
    ADC R0, R4
    MOV [${pong+5}], R0
    GOTO .done

; ---- east: x += 1 --------------------------------------------------------
.east:
    MOV R0, [${pong+6}]
    ADD R0, 0
    MOV [${pong+6}], R0
    MOV R0, [${pong+7}]
    MOV R4, 4
    ADC R0, R4
    MOV [${pong+7}], R0
    SKIP NC, 2
    GOTO .east_b2
    GOTO .done
.east_b2:
    MOV R0, [${pong+4}]
    ADD R0, 1
    MOV [${pong+4}], R0
    MOV R0, [${pong+5}]
    ADC R0, R2
    MOV [${pong+5}], R0
    GOTO .done

"""End-to-end tests for the Niblick library modules in ``lib/``."""

from __future__ import annotations

from pathlib import Path

from niblick.assembler import assemble_file
from niblick.compiler import Compiler
from niblick.emulator import Emulator
from niblick.loader import load_source


def compile_source(tmp_path: Path, source: str, name: str = "libtest", rx: list[int] | None = None, trace: bool = False):
    filename = tmp_path / f"{name}.nbl"
    program = load_source(source, filename=str(filename))
    compiler = Compiler(program, str(filename))
    asm = compiler.compile()
    asm_path = tmp_path / f"{name}.asm"
    asm_path.write_text(asm)
    hex_path = tmp_path / f"{name}.hex"
    assemble_file(asm_path, hex_path)

    emu = Emulator()
    emu.load_hex(hex_path)
    if rx is not None:
        emu.uart_rx = list(rx)
    if trace:
        emu.trace_io()
    emu.run(500000)
    return compiler, emu


def value(compiler: Compiler, emu: Emulator, name: str) -> int:
    base = compiler.globals[name].address
    assert base is not None
    if compiler.globals[name].type.name == "nibble":
        return emu.ram[base]
    return emu.ram[base] | (emu.ram[base + 1] << 4)


def test_uart_formatting(tmp_path: Path) -> None:
    _, emu = compile_source(
        tmp_path,
        """
        import "lib/uart.nbl";
        fn main() {
            uart_route(1);
            uart_init(3);
            uart_print_hex8(171);
            uart_putc(' ');
            uart_print_dec8(234);
            uart_putc(' ');
            uart_print_bin8(165);
            uart_nl();
        }
        """,
    )
    assert bytes(emu.uart_tx) == b"AB 234 10100101\n"


def test_uart_16bit_formatting(tmp_path: Path) -> None:
    _, emu = compile_source(
        tmp_path,
        """
        import "lib/uart.nbl";
        fn main() {
            uart_route(1);
            uart_init(3);
            uart_print_hex16(0x9088);
            uart_putc(' ');
            uart_print_dec16(37000);
            uart_nl();
        }
        """,
    )
    assert bytes(emu.uart_tx) == b"9088 37000\n"


def test_uart_32bit_formatting(tmp_path: Path) -> None:
    _, emu = compile_source(
        tmp_path,
        """
        import "lib/uart.nbl";
        fn main() {
            uart_route(1);
            uart_init(3);
            uart_print_hex32(0x00387520);
            uart_putc(' ');
            uart_print_dec32(3700000);
            uart_nl();
        }
        """,
    )
    assert bytes(emu.uart_tx) == b"00387520 3700000\n"


def test_string_module(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        import "lib/string.nbl";
        import "lib/uart.nbl";
        char a[24];
        char b[12];
        char len;
        nibble eq;
        char found;
        char base;
        fn main() {
            uart_route(1);
            uart_init(3);
            str_copy_flash(&a, "hello");
            str_copy_flash(&b, "hello");
            len = str_len(&a);
            eq = str_eq(&a, &b);
            base = &a;
            found = str_chr(&a, 'l');
            str_cat(&a, &b);
            uart_print_str(&a);
            uart_putc(' ');
            uart_print_dec8(len);
            uart_putc(' ');
            uart_print_dec8(eq);
            uart_putc(' ');
            uart_print_dec8(found - base);
            uart_nl();
        }
        """,
    )
    assert bytes(emu.uart_tx) == b"hellohello 5 1 4\n"
    assert value(compiler, emu, "len") == 5


def test_math_module(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        import "lib/math.nbl";
        char product;
        char quotient;
        nibble remainder;
        nibble root;
        char big_quotient;
        char power;
        fn main() {
            product = math_mul(7, 9);
            quotient = math_div(15, 4);
            remainder = math_mod(15, 4);
            root = math_isqrt(49);
            big_quotient = math_div8(200, 7);
            power = math_pow2(5);
        }
        """,
    )
    assert value(compiler, emu, "product") == 63
    assert value(compiler, emu, "quotient") == 3
    assert value(compiler, emu, "remainder") == 3
    assert value(compiler, emu, "root") == 7
    assert value(compiler, emu, "big_quotient") == 28
    assert value(compiler, emu, "power") == 32


def test_mem_module(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        import "lib/mem.nbl";
        char a[16];
        char b[16];
        nibble same;
        nibble bit;
        nibble bits;
        fn main() {
            mem_fill(&a, 3, 8);
            a[0] = 5;
            mem_bit_set(&a, 0);
            bit = mem_bit_test(&a, 0);
            bits = mem_popcount(15);
            mem_copy(&b, &a, 8);
            same = mem_cmp(&a, &b, 8);
            mem_bit_clear(&a, 0);
            mem_bit_toggle(&a, 1);
            mem_swap(&a, &b);
        }
        """,
    )
    assert value(compiler, emu, "bit") == 1
    assert value(compiler, emu, "bits") == 4
    assert value(compiler, emu, "same") == 0
    # a[0]: 5 -> set bit0 (5) -> clear bit0 (4) -> toggle bit1 (6).
    # mem_swap then puts b's original copy back into a.
    a_base = compiler.globals["a"].address
    b_base = compiler.globals["b"].address
    assert a_base is not None and b_base is not None
    assert emu.ram[a_base] == 5
    assert emu.ram[b_base] == 6


def test_display_module(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        import "lib/display.nbl";
        nibble screen[32];
        nibble corner;
        nibble empty;
        nibble bottom;
        nibble page_value;
        fn main() {
            clear_screen(&screen);
            pixel_set(&screen, 0, 0, 1);
            pixel_set(&screen, 7, 15, 1);
            corner = pixel_get(&screen, 0, 0);
            empty = pixel_get(&screen, 1, 0);
            bottom = pixel_get(&screen, 7, 15);
            hline(&screen, 0, 7, 5, 1);
            display_fill(8, 5);
            page_value = display_peek(8, 3);
            display_clear(8);
        }
        """,
    )
    assert value(compiler, emu, "corner") == 1
    assert value(compiler, emu, "empty") == 0
    assert value(compiler, emu, "bottom") == 1
    assert value(compiler, emu, "page_value") == 5

    base = compiler.globals["screen"].address
    assert base is not None
    # Row 5 occupies nibbles 10 and 11; hline set all eight pixels.
    assert emu.ram[base + 10] == 15
    assert emu.ram[base + 11] == 15
    # display_clear cleared page 8.
    assert emu.ram[0x80] == 0


def test_key_names_and_clock(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        import "lib/key.nbl";
        import "lib/time.nbl";
        import "lib/uart.nbl";
        nibble clock;
        fn main() {
            uart_route(1);
            uart_init(3);
            uart_puts(key_name(key_op8()));
            uart_nl();
            time_clock_set(5);
            clock = time_clock_get();
        }
        """,
    )
    assert bytes(emu.uart_tx) == b"OPCODE 8\n"
    assert value(compiler, emu, "clock") == 5


def test_uart_read_line(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        import "lib/uart.nbl";
        char buf[8];
        nibble count;
        fn main() {
            uart_route(1);
            uart_init(3);
            count = uart_read_line(&buf, 4);
            uart_print_dec8(count);
            uart_putc(':');
            uart_print_str(&buf);
        }
        """,
        rx=list(b"abc\n"),
    )
    assert value(compiler, emu, "count") == 3
    assert bytes(emu.uart_tx) == b"3:abc"


def test_system_power_and_time_helpers(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        import "lib/display.nbl";
        import "lib/power.nbl";
        import "lib/system.nbl";
        import "lib/time.nbl";
        import "lib/uart.nbl";
        nibble power80;
        nibble power150;
        nibble power255;
        nibble sync;
        nibble baud;
        nibble error;
        nibble flags;
        nibble dim;
        fn main() {
            uart_init(3);
            dimmer(7);
            power_auto_off_minutes(80);
            power80 = power_remaining();
            power_auto_off_minutes(150);
            power150 = power_remaining();
            power_auto_off_minutes(255);
            power255 = power_remaining();
            power_keep_awake();
            time_clock_set(CLOCK_100K);
            time_sync_set(SYNC_10HZ);
            sync = time_sync_get();
            system_wr_flags_set(10);
            flags = system_wr_flags();
            baud = system_uart_baud();
            error = system_uart_error();
            dim = system_dimmer();
            time_delay_ms(2);
        }
        """,
    )
    assert value(compiler, emu, "power80") == 8
    assert value(compiler, emu, "power150") == 15
    assert value(compiler, emu, "power255") == 15
    assert value(compiler, emu, "sync") == 10
    assert value(compiler, emu, "flags") == 10
    assert value(compiler, emu, "baud") == 3
    assert value(compiler, emu, "error") == 0
    assert value(compiler, emu, "dim") == 7


def test_math_extensions(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        import "lib/math.nbl";
        char mapped;
        char root;
        char gcd;
        char lcm;
        nibble sign;
        char wrapped;
        char rounded;
        fn main() {
            mapped = math_map8(50, 0, 100, 0, 255);
            root = math_sqrt16(65025);
            gcd = math_gcd8(48, 18);
            lcm = (char)math_lcm8(12, 18);
            sign = math_sign8(0x80);
            wrapped = math_wrap8(17, 10);
            rounded = math_div_round8(7, 2);
        }
        """,
    )
    assert value(compiler, emu, "mapped") == 127
    assert value(compiler, emu, "root") == 255
    assert value(compiler, emu, "gcd") == 6
    assert value(compiler, emu, "lcm") == 36
    assert value(compiler, emu, "sign") == 15
    assert value(compiler, emu, "wrapped") == 7
    assert value(compiler, emu, "rounded") == 4


def test_trig_table(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        import "lib/trig.nbl";
        char s0;
        char s8;
        char s16;
        char s24;
        char c0;
        fn main() {
            s0 = sin_q4_4(0);
            s8 = sin_q4_4(8);
            s16 = sin_q4_4(16);
            s24 = sin_q4_4(24);
            c0 = cos_q4_4(0);
        }
        """,
    )
    assert value(compiler, emu, "s0") == 0x00
    assert value(compiler, emu, "s8") == 0x10
    assert value(compiler, emu, "s16") == 0x00
    assert value(compiler, emu, "s24") == 0xF0
    assert value(compiler, emu, "c0") == 0x10


def test_font_and_text_glyph(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        import "lib/font.nbl";
        nibble screen[32];
        nibble top;
        nibble gap;
        nibble dot;
        nibble tail;
        fn main() {
            clear_screen(&screen);
            text_draw_char(&screen, 0, 0, '!');
            top = pixel_get(&screen, 2, 0);
            gap = pixel_get(&screen, 2, 5);
            dot = pixel_get(&screen, 2, 6);
            tail = pixel_get(&screen, 2, 7);
        }
        """,
    )
    assert value(compiler, emu, "top") == 1
    assert value(compiler, emu, "gap") == 0
    assert value(compiler, emu, "dot") == 1
    assert value(compiler, emu, "tail") == 0


def test_display_shift_and_column(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        import "lib/display.nbl";
        nibble screen[32];
        nibble left;
        nibble right;
        fn main() {
            clear_screen(&screen);
            display_set_column(&screen, 7, 0xA5);
            left = pixel_get(&screen, 7, 0);
            right = pixel_get(&screen, 7, 1);
            display_shift_left(&screen);
        }
        """,
    )
    assert value(compiler, emu, "left") == 1
    assert value(compiler, emu, "right") == 0
    base = compiler.globals["screen"].address
    assert base is not None
    # After the shift, the previous x=7 column is at x=6.
    assert (emu.ram[base + 1] >> 1) & 1 == 1


def test_audio_tone_and_melody(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        import "lib/audio.nbl";
        nibble out0;
        fn main() {
            audio_init();
            audio_tone_raw(0, 6);
            audio_silence();
            out0 = peek(0x0A) & 1;
        }
        """,
        trace=True,
    )
    assert emu.ram[0xF1] == 1  # CLOCK_100K
    assert value(compiler, emu, "out0") == 0
    events = [
        e
        for e in (emu.io_trace or [])
        if e.kind == "bit" and e.address == 0x0A and e.bit == 0
    ]
    assert len(events) >= 6


def test_audio_note_table(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        import "lib/audio.nbl";
        nibble first;
        nibble last;
        fn main() {
            first = (nibble)audio_note_half_periods[0];
            last = (nibble)audio_note_half_periods[15];
        }
        """,
    )
    assert value(compiler, emu, "first") == 12
    assert value(compiler, emu, "last") == 5


def test_pdm_encoder(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        import "lib/pdm.nbl";
        nibble first;
        nibble second;
        nibble error;
        fn main() {
            pdm_init();
            pdm_encode(8);
            first = peek(0x0A);
            pdm_encode(8);
            second = peek(0x0A);
            error = pdm_error;
        }
        """,
    )
    assert emu.ram[0xF1] == 0  # CLOCK_250K
    assert value(compiler, emu, "first") == 1
    assert value(compiler, emu, "second") == 15
    assert value(compiler, emu, "error") == 0


def test_mem_byte_endian_and_search(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        import "lib/mem.nbl";
        char buf[8];
        char le_lo;
        char le_hi;
        char be_lo;
        char be_hi;
        char found;
        nibble count;
        char sum;
        fn main() {
            mem_fill8(&buf, 0, 8);
            mem_poke16_le(&buf, 0x1234);
            le_lo = (char)mem_peek16_le(&buf);
            le_hi = (char)(mem_peek16_le(&buf) >> 8);
            be_lo = (char)mem_peek16_be(&buf);
            be_hi = (char)(mem_peek16_be(&buf) >> 8);
            mem_poke16_be(&buf, 0xABCD);
            found = mem_search8(&buf, 2, 0xAB);
            count = mem_popcount8(0xF0);
            mem_fill8(&buf, 0x01, 4);
            sum = mem_sum8(&buf, 4);
        }
        """,
    )
    assert value(compiler, emu, "le_lo") == 0x34
    assert value(compiler, emu, "le_hi") == 0x12
    assert value(compiler, emu, "be_lo") == 0x12
    assert value(compiler, emu, "be_hi") == 0x34
    assert value(compiler, emu, "found") != 0
    assert value(compiler, emu, "count") == 4
    assert value(compiler, emu, "sum") == 4


def test_string_convert_search_and_trim(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        import "lib/string.nbl";
        char buf[16];
        char other[16];
        char trimmed;
        char value;
        nibble len;
        nibble eq;
        nibble contains;
        nibble cmp;
        fn main() {
            len = str_from_dec8(&buf, 123);
            value = str_to_dec8(&buf);
            str_reverse(&buf);
            str_copy_flash(&other, "hello world");
            contains = str_contains(&other, "world");
            cmp = str_compare(&buf, &buf);
            eq = str_eq_flash(&other, "hello world");
            str_upper(&other);
            str_copy_flash(&other, "  hi  ");
            trimmed = str_trim(&other);
            eq = str_eq_flash(trimmed, "hi");
        }
        """,
    )
    assert value(compiler, emu, "len") == 3
    assert value(compiler, emu, "value") == 123
    assert value(compiler, emu, "contains") == 1
    assert value(compiler, emu, "cmp") == 0
    assert value(compiler, emu, "eq") == 1


def test_power_sleep_halts_emulator(tmp_path: Path) -> None:
    _, emu = compile_source(
        tmp_path,
        """
        import "lib/power.nbl";
        fn main() {
            power_sleep();
        }
        """,
    )
    assert emu.sleeping is True
    assert emu.halted is True


def test_audio_rest_code_is_silent(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        import "lib/audio.nbl";
        nibble out;
        fn main() {
            audio_init();
            audio_silence();
            audio_note(NOTE_REST, 4);
            out = peek(0x0A) & 1;
        }
        """,
        trace=True,
    )
    assert value(compiler, emu, "out") == 0
    bit_events = [
        e
        for e in (emu.io_trace or [])
        if e.kind == "bit" and e.address == 0x0A and e.bit == 0
    ]
    assert len(bit_events) <= 2


def test_string_16_32_conversion(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        import "lib/string.nbl";
        char buf[11];
        char round[11];
        nibble ok_dec16;
        nibble ok_dec32;
        nibble ok_hex16;
        nibble ok_hex32;
        fn main() {
            str_from_dec16(&buf, 65535);
            str_from_dec16(&round, str_to_dec16(&buf));
            ok_dec16 = str_eq_flash(&round, "65535");
            str_from_dec32(&buf, 4294967295);
            str_from_dec32(&round, str_to_dec32(&buf));
            ok_dec32 = str_eq_flash(&round, "4294967295");
            str_from_hex16(&buf, 0xABCD);
            str_from_hex16(&round, str_to_hex16(&buf));
            ok_hex16 = str_eq_flash(&round, "ABCD");
            str_from_hex32(&buf, 0x12345678);
            str_from_hex32(&round, str_to_hex32(&buf));
            ok_hex32 = str_eq_flash(&round, "12345678");
        }
        """,
    )
    assert value(compiler, emu, "ok_dec16") == 1
    assert value(compiler, emu, "ok_dec32") == 1
    assert value(compiler, emu, "ok_hex16") == 1
    assert value(compiler, emu, "ok_hex32") == 1

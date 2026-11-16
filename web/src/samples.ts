export const HELLO_SOURCE = `import "lib/uart.nbl";
const char msg[] = "Hello, Supercon!\\n";

fn main() {
    uart_route(1);
    uart_init(3);
    uart_puts(msg);
    while (1) {
    }
}
`;

export const INLINE_ASM_SOURCE = `nibble a;
nibble b;

fn main() {
    a = 3;

    asm {
        MOV R0, [\${a}]
        ADD R0, 4
        MOV [\${b}], R0
    }

    while (1) { }
}
`;

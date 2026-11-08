# Inline assembly

BadgeC supports raw assembly blocks inside functions:

```c
fn main() {
    nibble x = 3;
    nibble y;

    asm {
        ; y = x + 2
        MOV R0, [${x}]
        ADD R0, 2
        MOV [${y}], R0
    }
}
```

The block is emitted at the current statement position. It may clobber
`R0`–`R9` and the flags; the compiler does not keep live values in registers
across statements.

## Placeholders

Inline asm uses the same `${...}` resolver as imported `.asm` modules:

| Placeholder | Expands to |
|---|---|
| `${name}` | RAM address of a visible local/parameter/global, scalar `const` value, or flash label for a `const` array |
| `${name+1}` / `${name-1}` | RAM address plus/minus a constant |
| `${&name}` | Address of a RAM variable or flash label |
| `${function.param}` | A specific function's parameter address |
| `${CONST << 2}` | A normal BadgeC constant expression |

Names resolve against the current lexical scope first, then globals. Locals
must be declared before the `asm` block. Comments are not substituted.

A `char` parameter or variable at `${p}` occupies two nibbles: `${p}` is low
and `${p+1}` is high. A `word` occupies four nibbles, and so on.

## Labels and calls

- Local labels must start with `.`:

```c
asm {
    MOV R1, 3
.loop:
    DEC R1
    SKIP Z, 1
    JR .loop
}
```

Each block gets a synthetic global label, so multiple blocks can use the same
local label names without colliding.

- `GOSUB __bc_*` calls a compiler runtime routine and updates the linker and
  stack report.
- `GOSUB fn_*` / `GOTO fn_*` call BadgeC or extern assembly functions and
  update the call graph.
- `GOTO .local` is a local branch.

`GOSUB` to a local label is not supported, because it makes the hardware
stack depth harder to model statically.

## Restrictions

- `RET` is rejected. Let the surrounding BadgeC function return normally.
- Global labels are rejected; use `.local` labels.
- Raw `MOV JSR`, `MOV PCL`, `MOV PCM`, and `MOV PCH` are rejected; use
  `GOSUB`/`GOTO`.
- `ORG`, `BYTE`, and `ASCII` are rejected. Use `NIBBLE` data in imported
  assembly modules instead.
- `EXR 0` and `EXR` with more than ten registers are rejected because they
  touch compiler/runtime state.

## Optimization

Inline asm is always treated as an opaque region by the optimizer. Redundant
moves and `GOTO` sequences are preserved exactly. The words are still counted
for size reporting and for branch relaxation outside the block.

## Results

An `asm` block does not produce an expression value. Store results into
variables:

```c
asm {
    ...
    MOV [${result}], R0
}
```

Globals referenced only from inline asm are kept alive during
dead-declaration elimination. Functions called with `GOSUB fn_*` or
`GOTO fn_*` are kept and included in the stack-depth calculation.

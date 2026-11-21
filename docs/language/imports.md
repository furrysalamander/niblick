# Imports

## Niblick modules

```c
import "lib/uart.nbl";
import "lib/string.nbl";
```

An import merges the declarations of another Niblick source file into the
program. Each file is parsed once. Import cycles are rejected.

Resolution order for a relative import:

1. The importing file's directory.
2. The repository root.
3. `share/niblick` under `sys.prefix` and `site.USER_BASE`.
4. Search paths supplied by the API.
5. `NIBLICK_PATH` entries, separated by the platform path separator.

An absolute import path is used as written.

## Merge behavior

- Global variables, functions, and extern declarations are merged.
- Imported declarations share one global namespace.
- Duplicate global or function names are rejected.
- Struct declarations share the program-wide namespace. A struct declared in an
  imported file is visible to the importer.

## Dead declarations

After inlining, the compiler removes declarations that are unreachable from
`main` or from a retained global initializer.

- Unreachable functions are removed.
- Unreferenced globals are removed when their initializer has no calls.
- Unreferenced `const` flash tables are removed.
- Functions and globals referenced by imported assembly placeholders or
  `fn_*` calls are retained.
- An imported assembly `fn_*` section whose extern function is unreachable is
  stripped, and its parameter slots are not allocated.

An unused module therefore contributes no code or RAM unless its declarations
are reachable.

## Assembly modules

```c
import "lib/drivers/asm/w5500.asm";

extern fn uint16_t w5500_tx_pointer();
```

A `.asm` import reads the file as assembly text. It is not parsed as Niblick.
Each entry point requires an `extern fn` declaration. See {doc}`asm-modules`.

## Implicit modules

The loader adds `lib/wide.nbl` when the program uses 64-bit arithmetic. It adds
`lib/float16.nbl` and `lib/float32.nbl` when the program uses the corresponding
float type. These modules are not part of the user import surface.

## Errors

Import failures report the importing file and the attempted paths.

```text
main.nbl: cannot find import 'lib/missing.nbl' (tried main.nbl/../lib/missing.nbl, ...)
```

Import cycles report the full chain.

## Related

- {doc}`../standard-library/index` for module layout.
- {doc}`../internals/compiler` for the loader pass.

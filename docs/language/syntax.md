# Syntax

## Lexical elements

| Element | Form |
|---|---|
| Identifier | ASCII letter or `_`, then ASCII letters, digits, or `_` |
| Integer literal | Decimal, `0x` hex, `0b` binary, `0o` octal; `_` may separate digits |
| Float literal | `1.5`, `1.`, `.5`, `1e3`, `1.5e-3` |
| String literal | Double quotes; escapes listed in {doc}`types` |
| Character literal | Single quotes; one byte |
| Line comment | `//` to end of line |
| Block comment | `/* ... */`; does not nest |

Integer literal with leading zeroes are not allowed. Integer and float
literals have no suffixes.

## Program

```ebnf
program      = { top_level } EOF ;
top_level    = import | struct_decl | global_decl | function | extern_fn ;
import       = "import" string ";" ;
struct_decl  = "struct" ident "{" { type ident [ "[" number "]" ] ";" } "}" ";" ;
global_decl  = [ "const" ] type ident [ array_suffix ] [ "=" initializer ] ";" ;
function     = "fn" type ident "(" [ params ] ")" block ;
extern_fn    = "extern" "fn" type ident "(" [ params ] ")" ";" ;
params       = param { "," param } ;
param        = type ident ;
array_suffix = "[" [ const_expr ] "]" ;
initializer  = expr | "{" [ initializer { "," initializer } ] "}" | string ;
```

Global declarations and functions may appear in any order.

## Types

```ebnf
type = "nibble" | "u4" | "i4" | "char" | "u8" | "byte" | "uint8_t"
     | "i8" | "int8_t" | "uint16_t" | "u16" | "i16" | "int16_t"
     | "short" | "int" | "uint32_t" | "u32" | "i32" | "int32_t" | "long"
     | "uint64_t" | "u64" | "i64" | "int64_t"
     | "bool" | "half" | "f16" | "_Float16"
     | "float" | "f32" | "_Float32"
     | "flashptr" | "void" | struct_name ;

struct_name = ident ;
```

The complete alias table is in {doc}`types`.

## Statements

```ebnf
block        = "{" { statement } "}" ;
statement    = block
             | if_stmt
             | while_stmt
             | for_stmt
             | return_stmt
             | break_stmt
             | continue_stmt
             | const_decl
             | local_decl
             | asm_block
             | assignment_stmt
             | expr_stmt ;

if_stmt      = "if" "(" expr ")" statement [ "else" statement ] ;
while_stmt   = "while" "(" expr ")" statement ;
for_stmt     = "for" "(" [ for_init ] ";" [ expr ] ";" [ for_update ] ")" statement ;
for_init     = local_decl | assignment_stmt ;
for_update   = assignment ;
assignment_stmt = assignment ";" ;
return_stmt  = "return" [ expr ] ";" ;
break_stmt   = "break" ";" ;
continue_stmt= "continue" ";" ;
const_decl   = "const" type ident [ array_suffix ] "=" initializer ";" ;
local_decl   = type ident [ array_suffix ] [ "=" initializer ] ";" ;
asm_block    = "asm" "{" raw_text "}" ;
expr_stmt    = expr ";" ;
assignment   = lvalue ( "=" | compound_op ) expr ;
lvalue       = ident | ident "[" expr "]" | lvalue "." ident ;
compound_op  = "+=" | "-=" | "*=" | "/=" | "%=" | "&=" | "|=" | "^=" | "<<=" | ">>=" ;
```

`if` and loop bodies may be a single statement without braces.

## Expressions

```ebnf
expr         = conditional ;
conditional  = binary [ "?" expr ":" conditional ] ;
binary       = unary { binary_op binary } ;
unary        = [ "+" | "-" | "~" | "!" | "&" ] unary
             | [ "++" | "--" ] unary
             | cast
             | postfix ;
cast         = "(" type ")" unary ;
postfix      = primary { "[" expr "]" | "." ident | "(" [ args ] ")" | "++" | "--" } ;
primary      = integer | float | string | char | ident | "true" | "false"
             | "(" expr ")" ;
args         = expr { "," expr } ;
```

`++` and `--` are valid only as statements. See {doc}`expressions` for
precedence, evaluation, and lvalue rules.

## Imports and external assembly

```ebnf
import    = "import" string ";" ;
extern_fn = "extern" "fn" type ident "(" [ params ] ")" ";" ;
```

`.nbl` imports are merged with the source file. `.asm` imports link assembly modules
and require `extern fn` declarations for their entry points. See {doc}`imports`,
{doc}`inline-asm`, and {doc}`asm-modules`.

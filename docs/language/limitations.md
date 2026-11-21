# Limitations

| Constraint | Effect |
|---|---|
| General pointers and pointer arithmetic | Rejected. `&array` yields a nibble address or `flashptr`. |
| Non-tail recursion | Maximum four non-tail user call levels. Tail-call cycles are allowed. |
| Dynamic allocation | Not available. All storage is static RAM. |
| Bounds checking | Not performed. An out-of-range index accesses another data address. |
| Local initialization | Locals are not zeroed. Frame reuse can expose values from another function. |
| Code memory | Read-only at runtime. |
| `double` | Not available. Use `half` or `float`. |
| Array fields | Scalar elements only. Arrays of structs inside a struct are rejected. |
| Local `const` | Local `const` arrays and local `const` structs are rejected. |

See {doc}`types`, {doc}`structs`, and {doc}`semantics`.

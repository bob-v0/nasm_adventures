# Level 135 — Called from C

*Now C calls you. Your functions have to fit C's expectations exactly: types, sizes,
signs and side effects.*

## Lesson: reading a prototype as registers

```c
int64_t dot(const int64_t *a, const int64_t *b, size_t n);
//  rax         rdi                rsi              rdx
int cmp_desc(const void *x, const void *y);
//  eax         rdi              rsi
size_t count_char(const char *s, int c);
//  rax                rdi        esi
```

- `int` is 32 bits: it arrives in `esi`, and you return it in `eax` (the upper half of
  rax is ignored).
- Pointers and `size_t` are 64 bits. `const` is a promise you keep: don't write
  through those pointers.
- C strings end with a 0 byte; `char` is a byte.

The game's `harness.c` (in your level folder) reads test data, calls your functions,
and prints the results. It's compiled and linked with your object by gcc, and runs
natively. Use `global` for each function.

## Lesson: comparators

`qsort` sorts anything: you give it a **comparator** that receives *pointers* to two
elements and returns a negative int if the first should come first, 0 if equal,
positive otherwise. The tempting `return *y - *x;` is a classic bug. The subtraction
overflows for large values of opposite sign, and the sort quietly produces garbage.
Compare instead.

## Gate

Implement, with `global` names:

| Function | Returns |
|---|---|
| `dot(a, b, n)` | Σ a[i]·b[i] (mod 2⁶⁴) |
| `cmp_desc(x, y)` | a comparator that makes `qsort` sort int64_t values in **descending** order |
| `count_char(s, c)` | the number of bytes in the C string s equal to (char) c |

Constraint: at most 50 instructions. Debug with gdb in {{terminal}}: `gdb ./solution`,
then `break dot` and `run < input.txt`.

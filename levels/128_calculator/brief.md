# Level 128 — Calculator ★

*The last gate of Arc IV: a program that understands arithmetic, built from functions
that call each other recursively.*

## The language

A **grammar** describes which inputs are valid. Read `:=` as "is made of", `{ ... }` as
"repeated zero or more times" and `|` as "or":

```
expr   := term   { ('+' | '-') term }
term   := factor { ('*' | '/') factor }
factor := number | '(' expr ')' | '-' factor
```

- numbers are decimal, at most 2⁶³ − 1; spaces may appear between any two tokens
- arithmetic is signed 64-bit and wraps around like `add`/`imul` (so 2⁶³ − 1 + 1 gives
  −2⁶³); `/` truncates toward zero like `idiv`
- `+ -` bind looser than `* /`, and both associate left: `8 - 2 - 1` = 5

## Lesson: recursive descent

**Recursive descent** turns each rule of the grammar into a function that consumes its
part of the input and returns its value:

```
expr():   v = term();   while next is + or -: consume it; v = v ± term();   return v
term():   v = factor(); while next is * or /: consume it; v = v */ factor(); return v
factor(): if '-': consume; return -factor()
          if '(': consume; v = expr(); expect ')'; return v
          else: parse a number
```

For `2 * (3 + 4)`: expr calls term; term calls factor, which reads 2; term sees `*`
and calls factor again; that factor sees `(` and calls expr, which computes 3 + 4 = 7;
term returns 2 · 7 = 14.

The call stack does the bookkeeping: an expression nested ten parentheses deep is ten
`expr` frames waiting for their inner result. Real compilers parse this way (GCC and
Clang both use hand-written recursive-descent parsers).

## Gate ★

Read one line from stdin (up to 255 bytes), evaluate it, print the result in signed
decimal with a newline, and exit with status 0. If the line isn't a valid expression,
a number is too big, or there's a division by zero (or −2⁶³ / −1, which `idiv` can't
represent), print `error` and a newline and exit with status 1.

Constraints: at most 150 instructions; must use `call`. You have `print_uint` in your
library, but you'll need negatives too.

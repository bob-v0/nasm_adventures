# Level 156 — Loops

*Arc III. Your programs stop running in a straight line and start going round in
circles, on purpose.*

## Lesson: the shape of a loop

You built loops from jumps in the Bignum level. Every loop has the same four parts:

```
    xor ecx, ecx            ; init:  i = 0
.top:
    cmp rcx, rsi            ; test:  while i < n
    jae .done
    ...                     ; body
    inc rcx                 ; step:  i++
    jmp .top
.done:
```

Testing **before** the body matters: if n = 0 the body must not run even once. A
"do-while" loop (test at the bottom) is shorter and often faster, but needs a guard
for the empty case:

```
    test rsi, rsi
    jz .done                ; guard: skip everything if n = 0
.top:
    ...
    dec rsi
    jnz .top                ; dec sets ZF: no cmp needed
.done:
```

## Lesson: the `loop` instruction

`loop .top` decrements rcx and jumps if it isn't zero, and `jrcxz` jumps if rcx is
zero. It looks perfect, but on most modern Intel CPUs `loop` is *slower* than
`dec rcx` + `jnz`, so compilers never emit it. Know it when you read old code.

## Gate

The game provides `arr`: up to 64 unsigned qwords. On entry `rsi` = n (0–64) and
`rdx` = a threshold t. Considering only `arr[0 .. n)`:

| Register | Must hold |
|---|---|
| `rax` | the sum of the elements (mod 2⁶⁴) |
| `rbx` | the largest element (unsigned), or 0 if n = 0 |
| `rcx` | how many elements are greater than t (unsigned) |

`rsi` and `rdx` must be unchanged. Constraint: at most 30 instructions.

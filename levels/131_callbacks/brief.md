# Level 131 — Callbacks

*Code that takes other code as an argument: `qsort`'s comparator, event handlers,
`map` and `filter`.*

## Lesson: function pointers

A function's name is just the address of its first instruction. So a register or a
variable can hold it (a **function pointer**), and you can call through it:

```
    lea rax, [some_function]
    call rax                ; indirect call: call whatever rax points to
    call [table + rcx*8]    ; or through memory, like a jump table
```

A **callback** is a function you hand to other code so that it can call you back.
That's how C function pointers, C++ virtual methods and event handlers work
underneath.

The function you call through a pointer is **unknown code**. It follows the ABI and
nothing more, so it may destroy every scratch register. Anything your loop needs across
the call (the function pointer itself, the array, the counters) must live in
callee-saved registers.

## Lesson: higher-order functions

A **higher-order function** takes a function as an argument. The three classics, on
the array `[1, 2, 3, 4]`:

| call | result |
|---|---|
| `map` with "add 3" | `[4, 5, 6, 7]` |
| `filter` with "is odd" | `[1, 3]` |
| `reduce` with "sum", starting from 0 | `10` |

## Gate

Implement three higher-order functions over arrays of qwords (`global` each):

| Function | Does |
|---|---|
| `map(arr, n, fn)` | arr[i] = fn(arr[i]) for every i |
| `filter(arr, n, pred) → count` | keeps, in order and in place at the front of arr, the elements for which pred(x) ≠ 0; returns how many |
| `reduce(arr, n, fn, init) → acc` | acc = init, then acc = fn(acc, arr[i]) for every i |

The game's `ring_pipeline` runs one of two pipelines over its `data` array, using your
three functions with its callbacks:

- add 3 → keep odd numbers → sum
- square → keep numbers > 10 → maximum

Its callbacks destroy every scratch register and check that the stack is aligned at
each call. Constraints: at most 90 instructions; must use `call`.

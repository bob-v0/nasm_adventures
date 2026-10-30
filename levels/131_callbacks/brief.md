# Level 131 — Callbacks

*Code that takes other code as an argument: `qsort`'s comparator, event handlers,
`map` and `filter`.*

## Lesson: function pointers

A function's name is an address, so a register or variable can hold it, and you can
call through it:

```
    lea rax, [some_function]
    call rax                ; indirect call
    call [table + rcx*8]    ; or through memory, like a jump table
```

That's how C function pointers, C++ virtual methods and callbacks work underneath.
The function you call is **unknown code**: it follows the ABI and nothing more, so it
may destroy every scratch register. Anything your loop needs across the call (the
function pointer itself, the array, the counters) lives in callee-saved registers.

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

# Level 138 — Stack Frames

*How does a debugger know who called whom? It follows a chain that every function
leaves on the stack.*

## Lesson: frame pointers

A function's **frame** is its own piece of the stack: its return address, the
registers it saved and its local variables. The traditional prologue gives each frame
a fixed reference point, the **frame pointer** `rbp`:

```
f:
    push rbp            ; save the caller's frame pointer
    mov rbp, rsp        ; rbp = this frame
    sub rsp, 32         ; local variables at [rbp - 8], [rbp - 16], ...
    ...
    leave               ; = mov rsp, rbp / pop rbp
    ret
```

Inside f, two slots sit at fixed places next to rbp:

- `[rbp]` holds the **caller's** rbp (pushed by the prologue)
- `[rbp + 8]` holds f's **return address** (pushed by `call`)

Each caller did the same, so every saved rbp points at the previous frame's saved rbp.
The frames form a **linked list** through the stack: the *frame chain*.

![The frame chain: each saved rbp points at the next frame's saved rbp, and the return address sits just above it](frame-chain.svg)

Debuggers (`bt` in gdb), profilers and crash reporters walk this chain to show the call
stack. `enter 32, 0` is an old one-instruction prologue; it's slow, but `leave` is
still common.

Compilers often skip the frame pointer for speed (`-fomit-frame-pointer`) and record
how to unwind in separate tables instead (`.eh_frame`). The chain is the simple,
classic version.

## Gate

Write `backtrace(buf, max)`: write return addresses into `buf` (an array of qwords),
innermost first, and return how many you wrote:

1. entry 0: **your own** return address
2. then, following the rbp chain from your caller's frame: each frame's return address
   `[rbp + 8]`, moving on with `rbp = [rbp]`
3. stop when the rbp you'd follow is **0**, or when you've written `max` entries

The game's `ring_run` builds a chain of 1–11 nested frames and calls your function from
the innermost one. You must not change rbp (it's callee-saved). Constraint: at most 30
instructions. Declare it with `global backtrace`.

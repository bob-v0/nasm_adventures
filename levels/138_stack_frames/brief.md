# Level 138 — Stack Frames

*How does a debugger know who called whom? It follows a chain that every function
leaves on the stack.*

## Lesson: frame pointers

A traditional function prologue builds a **frame**:

```
f:
    push rbp            ; save the caller's frame pointer
    mov rbp, rsp        ; rbp = this frame
    sub rsp, 32         ; local variables at [rbp - 8], [rbp - 16], ...
    ...
    leave               ; = mov rsp, rbp / pop rbp
    ret
```

Inside f, `[rbp]` holds the caller's rbp and `[rbp + 8]` holds f's return address. Since
each caller did the same, the saved rbps form a **linked list** through the stack: the
frame chain. Debuggers (`bt` in gdb), profilers and crash reporters walk it to show the
call stack. `enter 32, 0` is an old one-instruction prologue; it's slow, but `leave` is
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

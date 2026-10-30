# Level 132 — Bug: Dangling Frame ◆◆

*The pointer is valid. The memory it points to belongs to someone else now.*

## Symptoms

`format_pair` returns a pointer to the text "a,b". Code that prints the result right
away works. The report, which formats two pairs and then does some other work before
printing them, gets both lines wrong, and sometimes pure garbage.

## Background: lifetime

Memory a function reserves on the stack (`sub rsp, 40`) is its **frame**, and the frame
lives exactly as long as the call. After `ret`, rsp is above it, and the next call
anyone makes reuses the same bytes for its own return address, saved registers and
locals.

So a pointer into a callee's frame becomes **dangling** the moment the callee returns.
It still holds an address, the bytes may even still look right for a while, and then
the next call overwrites them. In C this is returning the address of a local
variable; compilers warn about the direct case, but not when it's hidden behind
pointers.

The usual fixes: the **caller provides the buffer** (`snprintf`, `strftime`), the
callee allocates memory that outlives it (the heap, Arc V), or a static buffer (with
its own problems: try calling such a function twice and keeping both results).

## Gate

Fix `format_pair` so its result stays valid after it returns, changing at most
**2 lines**. Its caller already passes a buffer it owns, in `rdx`.

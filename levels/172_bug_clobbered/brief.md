# Level 172 — Bug: Clobbered by the Kernel ◆

*The program asks the kernel for help three times. After the first, it no longer
knows where it is.*

## Symptoms

The program should print three log lines and exit with status 3. Instead it prints
the first line, then nothing, and exits with a status that changes when you change
unrelated code.

## What to look for

Every `syscall` hands control to the kernel and back. You learned in level 176 that
some registers do not survive the trip. This program assumes they do. Step over a
`syscall` in `ring debug` and compare `regs` before and after.

Tip: `s` steps over the whole `syscall`, because the kernel's work happens in one
step. `back` takes you to just before it again.

## Gate

Make the program print all three lines and exit with 3, for any line text. Fix it
**only by changing which registers hold the program's state**:

- at most **12 changed lines** (comments and spacing don't count)
- no extra instructions: at most 25, the same as the original

Afterwards, ask yourself why this bug is easy to make and hard to see: the program
is correct right up to the first `syscall`.

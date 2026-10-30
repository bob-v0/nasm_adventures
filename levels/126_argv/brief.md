# Level 126 — argv, envp, auxv

*Before your first instruction runs, the kernel has already left you a lot of
information on the stack.*

## Lesson: the initial stack

When Linux starts a program, rsp points at a block the kernel built:

```
rsp →  argc                     how many arguments (including the program name)
       argv[0]  → "./solution"  pointers to C strings
       argv[1]  → "hello"
       ...
       0                        end of argv
       envp[0]  → "HOME=/home/ada"
       ...
       0                        end of envp
       auxv: (type, value) pairs, e.g. (6, 4096) = AT_PAGESZ
       (0, 0)                   end of auxv
       ... the strings themselves, near the top of the stack
```

C's `main(argc, argv, envp)` gets exactly these, passed in registers by the C
runtime's `_start`. The **auxiliary vector** is how the kernel tells programs (and the
dynamic linker) things like the page size, where the program headers are and where
16 random bytes are (`AT_RANDOM`, used to seed stack protectors).

## Gate

Print, each followed by a newline:

1. every argument after the program name, in order
2. the value of the `HOME` environment variable, or `(no HOME)` if it isn't set.
   It must be exactly `HOME`: `HOMEBREW` doesn't count.
3. the page size from the auxiliary vector (`AT_PAGESZ` = 6), in decimal

Then exit with status argc − 1. Constraint: at most 90 instructions.

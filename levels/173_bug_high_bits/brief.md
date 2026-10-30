# Level 173 — Bug: Garbage in the High Bits ◆

*A program that worked yesterday prints half a line today. Nobody changed it. The
data it reads did change.*

## Bug levels

From here on, some levels hand you a **broken program** instead of an empty file.
Your job:

1. **Find** the bug. The symptoms are below; the cause is for you to discover.
2. **Fix** it within the **change budget**: at most N lines may differ from the
   original (comments, spacing and blank lines don't count). Rewriting the whole
   program doesn't count as a fix.

Bug levels have tiers: ◆ easy, ◆◆ medium, ◆◆◆ hard, ◆◆◆◆ very hard. The harder
ones come once you have the tools to see them: race conditions, reentrancy,
memory ordering, lifetimes.

## How to hunt

- Reproduce first: `ring test` shows which tests fail and how.
- Stop just before the suspicious instruction and look at **every** register it
  reads. With a `syscall`, that means rax, rdi, rsi, rdx.
- Walk backwards (`back` in `ring debug`) from the bad value to the instruction
  that produced it.
- Ask "what did this register hold *before*?", not just "what did I put in it?"

## Symptoms

The program should print

```
user: alice
############
```

and exit with the low byte of the record id. Instead it prints `user: ` with no
name, and then a badge that runs on for thousands of bytes (64 `#` followed by
zero bytes; pipe it through `od -c` to see them). Records with small ids sometimes
print the name correctly, which makes the bug harder to notice. Run it under
`strace -e trace=write ./solution` too: the kernel tells you exactly which lengths
it was given.

## Gate

Fix the program so it prints the name (exactly `name_len` bytes) and a badge of
exactly `badge_w` `#` characters, for any record. Change at most **2 lines**.

The lesson from level 181 applies here.

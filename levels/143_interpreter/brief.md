# Level 143 — The Interpreter ★

*The last gate of Arc III asks you to build a machine inside the machine.*

## The language

An **interpreter** runs a program written in another language, one command at a
time. The language here is `Brainf***` (BF for short): a complete programming
language with only eight commands. A BF program works on a **tape** of byte cells
(all 0 at the start) and a **data pointer** that points at one of them:

| Command | Meaning |
|---|---|
| `>` / `<` | move the data pointer right / left |
| `+` / `-` | add / subtract 1 from the current cell (bytes wrap: 0 − 1 = 255) |
| `.` | append the current cell to the output |
| `,` | read the next input byte into the current cell (0 when the input is used up) |
| `[` | if the current cell is 0, jump forward to just after the matching `]` |
| `]` | if the current cell is not 0, jump back to just after the matching `[` |

Any other character is a comment. `[` … `]` is a while loop, and brackets nest. The
tests' programs always have matching brackets and never move left of cell 0.

For example, `++[>+++<-]>.` sets cell 0 to 2, then loops twice, each time adding 3
to cell 1 and taking 1 from cell 0. It outputs one byte: 6.

```
after ++          tape: [2] 0      (brackets mark the data pointer)
first loop        tape: [1] 3
second loop       tape: [0] 6      cell 0 is 0: the loop ends
after >.          tape:  0 [6]     output: one byte, 6
```

## How to approach it

You have everything you need: a dispatch loop (level 150), string scanning (level
152), counters, poisoned registers to initialise (level 144). Plan the state first:
which register holds the instruction index, the data pointer, the input position, the
output length. Write and test one command at a time; the debugger's step-back is your
friend for bracket bugs.

## Gate ★

The game provides:

- `program`: NUL-terminated source, up to 511 characters
- `input`: the input bytes, with `rdx` = their count
- `tape`: 4096 cells, **filled with garbage by the tests**, so clear it first
- `output`: 512 bytes for the output (also full of garbage)

Run the program. Write its output to `output` and its length to `rax`. Registers start
poisoned. Constraints: at most 120 instructions; each test gets 600 000 executed
instructions ("hello world" needs a few thousand).

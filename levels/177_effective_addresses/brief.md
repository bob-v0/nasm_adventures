# Level 177 — The Address Machine

*The gate is a grid of 64 sealed boxes. A row and a column name the one you need.*

## Lesson: effective addresses

The address inside square brackets can be more than a label. The CPU can compute it
from up to four parts. The result is called the **effective address**:

```
[ base + index * scale + displacement ]
```

- **base**: any register
- **index**: any register except rsp
- **scale**: 1, 2, 4 or 8 (the sizes of byte/word/dword/qword elements)
- **displacement**: a constant, which can be a label

Any part can be left out. The CPU computes the address with dedicated hardware as
part of the instruction, so it costs nothing extra.

```
mov rax, [table + rcx*8]        ; table[rcx], 8-byte elements
mov al,  [rsi + rdx]            ; byte rsi[rdx]
mov rax, [rbx + rcx*8 + 16]     ; field at +16 of element rcx
```

The first line is how you index an array: element number rcx of 8-byte elements
starts rcx × 8 bytes after the start of `table`.

## Lesson: 2D arrays

Memory is one-dimensional, so a grid has to be laid out as one long line. The usual
way is **row by row** ("row-major"): all of row 0, then all of row 1, and so on.
In a grid with 8 columns of 8-byte values, each row takes 64 bytes, and element
[row][col] sits at:

```
grid + (row * 8 + col) * 8
```

![An 8-column grid of qwords stored row by row: row 1, column 3 is at byte offset 88, and the element below it at 152](grid-row-major.svg)

For example, [1][3] is at `grid + (1*8 + 3)*8 = grid + 88`, and the element directly
below it, [2][3], is one row (64 bytes) further on, at `grid + 152`.

## Lesson: `lea`

`lea` (Load Effective Address) computes the address expression and keeps the
**address itself**, without reading memory:

```
lea rbx, [grid + rcx*8]      ; rbx = address of grid[rcx]
lea rax, [rdi + rdi*2]       ; rax = rdi * 3. Plain arithmetic, no memory involved!
```

Because `lea` can add a register to a scaled copy of itself, compilers use it all
the time as a fast "multiply by 2, 3, 4, 5, 8 or 9", often with an add thrown in.

## Gate

The game provides `grid`: 8 rows × 8 columns of qwords. On entry `rdi` = row (0–6) and
`rsi` = column (0–7). (The row stops at 6 because `rcx` below asks for the element in
the next row, and row 7 has none.) When your code finishes:

| Register | Must hold |
|---|---|
| `rax` | grid[row][col] |
| `rbx` | the address of grid[row][col] |
| `rcx` | grid[row + 1][col], the element directly below |
| `r8`  | row × 5 + 3, using a single `lea` |

`rdi` and `rsi` must be unchanged. Constraints: at most 7 instructions; must use `lea`;
no `add`, `sub`, `mul`, `imul`, `shl`, `inc`, `dec`. Stretch goal: 5 instructions.

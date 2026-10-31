# Level 177 — The Address Machine

*The gate is a grid of 64 sealed boxes. A row and a column name the one you need.*

## Lesson: effective addresses

A memory operand can be more than a label. The general form is:

```
[ base + index * scale + displacement ]
```

- **base**: any register
- **index**: any register except rsp
- **scale**: 1, 2, 4 or 8 (the sizes of byte/word/dword/qword elements)
- **displacement**: a constant, which can be a label

Any part can be left out. The CPU computes this address with dedicated hardware as
part of the instruction, so it costs nothing extra.

```
mov rax, [table + rcx*8]        ; table[rcx], 8-byte elements
mov al,  [rsi + rdx]            ; byte rsi[rdx]
mov rax, [rbx + rcx*8 + 16]     ; field at +16 of element rcx
```

## Lesson: 2D arrays

Memory is one-dimensional. A grid is stored **row by row**: element [row][col] of a
grid with 8 columns of 8-byte values sits at:

```
grid + (row * 8 + col) * 8
```

## Lesson: `lea`

`lea` (Load Effective Address) computes the address expression and keeps the
**address**, without reading memory:

```
lea rbx, [grid + rcx*8]      ; rbx = address of grid[rcx]
lea rax, [rdi + rdi*2]       ; rax = rdi * 3. Plain arithmetic, no memory involved!
```

Compilers use `lea` as a fast "add and multiply by 2, 3, 4, 5, 8 or 9" all the time.

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

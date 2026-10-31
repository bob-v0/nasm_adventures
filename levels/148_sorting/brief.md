# Level 148 — Sorting

*Order from chaos, one element at a time.*

## Lesson: insertion sort

Insertion sort is how most people sort a hand of playing cards. The left part of the
array is always sorted. Take the next element and slide it left until it sits in the
right place:

```
for i in 1 .. n-1:
    x = arr[i]
    j = i
    while j > 0 and arr[j-1] > x:
        arr[j] = arr[j-1]        # shift larger elements right
        j = j - 1
    arr[j] = x
```

Sorting `4 2 5 1` (the bar separates the sorted part from the rest):

```
4 | 2 5 1        start: one element is always sorted
2 4 | 5 1        x = 2: 4 shifts right, 2 goes in front
2 4 5 | 1        x = 5: already in place, nothing moves
1 2 4 5          x = 1: 5, 4 and 2 shift right, 1 goes first
```

It takes O(n²) steps in the worst case (reversed input), meaning the work grows with
the square of n. But it is very fast on small or nearly sorted arrays, and real-world
sorts (introsort, pdqsort, timsort) switch to insertion sort for short runs. It is
also **stable**: equal elements keep their order, because the inner loop stops at
`>` and not `≥`.

Two classic mistakes: comparing with the wrong signedness (these are **signed**
numbers), and reading `arr[j-1]` when j = 0.

## Gate

The game provides `arr`: 200 slots, of which the first n are signed qwords to sort. On
entry `rsi` = n (0–200). Sort `arr[0 .. n)` ascending, in place. Slots from n onwards
must stay untouched.

`rsi` must be unchanged. Constraints: at most 30 instructions; the worst case (200
elements in reverse) must finish within 400 000 executed instructions.

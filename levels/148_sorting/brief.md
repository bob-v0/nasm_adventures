# Level 148 — Sorting

*Order from chaos, one element at a time.*

## Lesson: insertion sort

Insertion sort is how most people sort playing cards. The left part of the array is
always sorted; take the next element and slide it left into place:

```
for i in 1 .. n-1:
    x = arr[i]
    j = i
    while j > 0 and arr[j-1] > x:
        arr[j] = arr[j-1]        # shift larger elements right
        j = j - 1
    arr[j] = x
```

It is O(n²) in the worst case (reversed input), but very fast on small or nearly
sorted arrays. Real-world sorts (introsort, pdqsort, timsort) switch to insertion sort
for short runs. It is also **stable**: equal elements keep their order, because the
inner loop stops at `>` and not `≥`.

Two classic mistakes: comparing with the wrong signedness (these are **signed**
numbers), and reading `arr[j-1]` when j = 0.

## Gate

The game provides `arr`: 200 slots, of which the first n are signed qwords to sort. On
entry `rsi` = n (0–200). Sort `arr[0 .. n)` ascending, in place. Slots from n onwards
must stay untouched.

`rsi` must be unchanged. Constraints: at most 30 instructions; the worst case (200
elements in reverse) must finish within 400 000 executed instructions.

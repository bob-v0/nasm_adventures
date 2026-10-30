# Level 149 — Searching

*Find one key among a thousand in ten steps.*

## Lesson: binary search

In a **sorted** array, compare the key with the middle element and throw away half
the array. 1024 elements take 10 comparisons, a million take 20.

Binary search is famous for being easy to describe and hard to get exactly right. Jon
Bentley found that most professional programmers' versions were buggy. The cure is an
**invariant**: a statement that is true before and after every iteration.

```
answer is in [lo, hi)                  lo = 0, hi = n
while lo < hi:
    mid = lo + (hi - lo) / 2
    if arr[mid] < key:  lo = mid + 1   answer is above mid
    else:               hi = mid       answer is mid or below
return lo
```

This version returns the **lower bound**: the first index whose element is ≥ key, or n
if there is none. It works with duplicates and an empty array, with no special cases.

`lo + (hi - lo) / 2` instead of `(lo + hi) / 2` avoids overflow when indexes are
huge, a bug that sat in Java's standard library for nine years. With indexes below
1024 either works here, but form the habit.

## Gate

The game provides `arr`: up to 1024 unsigned qwords, sorted ascending. On entry `rdi` =
key, `rsi` = n. Set `rax` to the lower bound of key in `arr[0 .. n)`.

`rdi` and `rsi` must be unchanged. Constraints: at most 24 instructions, and at most
**400 executed instructions** per test. A linear scan runs out of budget.

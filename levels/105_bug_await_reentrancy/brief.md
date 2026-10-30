# Level 105 — Bug: Reentrancy at Await Points ◆◆◆

*"It's single-threaded, so there are no races." There are: every `await` is a place
where other tasks run.*

## Symptoms

A bank with four accounts runs one task per transfer request. Each transfer checks that
the source account has enough money, records the transfer in the (slow) audit log, then
moves the money. Run one at a time, it's flawless. Run together, *sometimes* the bank's
total grows, or an account goes below zero. Only some task orders do it.

## Background: await points are interleaving points

Threads can be interrupted at any instruction. Tasks are only suspended at an
**await**, which feels safer, and it is, between awaits. But at each await anything
can happen: every other ready task may run, read and write shared state, and finish.
When the task resumes, every value it read *before* the await may be **stale**.

`transfer` reads the balance into r13, awaits the audit log, then writes
`r13 - amount`. Two transfers from the same account can both read 1000, both pass the
check, both await, and each write its own idea of the new balance. The second write
erases the first, so 700 is paid out but only 600 is subtracted. This is **reentrancy
at an await point**: the function is entered again (for another request) while one
call of it is suspended in the middle. The real-world versions are JavaScript, Python
and Rust async code: a balance or a cache or a "seen already" flag checked, then used
after an `await`.

## The rule

An **invariant** must hold at every await point, and **no decision may rely on state
read before an await**. Either finish the check-and-update with no await inside it, or
check again after the await.

## How the game tests it

The task runtime asks the game which ready task runs next. Each test runs the bank
under the plain order and under 60 shuffled **schedules**, numbered, and checks the
books every time: the total is conserved, no account is negative, and the balances
match the transfers that were accepted. A failing report names the schedule.

## Gate

1. Add a witness: a schedule under which the **original** program breaks:
   `;! witness schedule = N`.
2. Fix it, changing at most **6 lines**.

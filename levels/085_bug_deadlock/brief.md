# Level 85 — Bug: Deadlock ◆◆

*Three threads, three locks, and nobody moves ever again.*

## Symptoms

A bank gives each of its 3 accounts its own lock (level 87's mutex), so transfers
between different accounts can run in parallel. Three threads move money around a
circle: 0 → 1, 1 → 2, 2 → 0. A transfer locks the account it takes from, then the one it
gives to. The program is supposed to print `total 300`. Usually it prints nothing at
all, and the game reports that every thread sleeps on a futex nobody will wake.

## Background: deadlock

Thread 0 holds lock 0 and waits for lock 1. Thread 1 holds 1 and waits for 2. Thread 2
holds 2 and waits for 0. Each waits for the next one around the circle: a **cycle in the
wait-for graph**. No thread will ever release anything.

A deadlock needs all four **Coffman conditions** (1971):

1. **mutual exclusion**: a lock has one holder at a time;
2. **hold and wait**: a thread holds one lock while waiting for another;
3. **no preemption**: nobody can take a lock away from its holder;
4. **circular wait**: a cycle of such waits.

Break any one and deadlock is impossible. The practical one to break is the fourth.

## Background: lock ordering

Give all locks a **global order**, and make every thread take its locks in that order.
Then a cycle can't form: a thread only ever waits for a lock *later* in the order than
everything it holds, and you can't go around a circle while always moving forward.
Here: the lower-numbered account first, whichever way the money goes. (When there's no
natural number: lock by address. Linux documents its lock order, and checks it at run
time with `lockdep`.)

Other remedies: one big lock (simple, no parallelism), `trylock` and back off (risks
livelock: level 84), or a design where nobody needs two locks at once.

## Gate

1. Add a witness: a schedule that deadlocks the original: `;! witness schedule = N`.
2. Fix it, changing at most **10 lines**. Every schedule must finish with `total 300`.

# Level 107 — Tasks & Await

*Your event loop works, but the logic for one client is scattered across "what to do
when this fd is ready" handlers. With a stack per client you can write it as one
straight line of code again, and still never block.*

## Lesson: callbacks vs tasks

In level 109 a client's life ("read, echo, read, echo, close") is spread across visits of
the event loop. Any state that must survive between visits (a half-read line, a
position in a protocol) has to live in a per-client struct, and the code becomes a
**state machine**: a big "what was I doing last time?" switch. Real protocols make that
painful.

A **task** keeps its state where ordinary code keeps it: in registers, local variables
and the call stack, because each task **has its own stack**. You built the key piece in
level 129: `co_switch` saves one context and resumes another. The trick:

- **await**: when a task would block (no data yet), it tells epoll "wake *me* when this fd
  is readable" (the event's `data` is the **task**, not the fd) and switches back to the
  event loop;
- the **event loop** keeps a **run queue** of ready tasks. It runs them one by one until
  each awaits or ends. With none ready, it calls `epoll_wait`, and every task whose fd is
  ready joins the run queue.

![A task's life: spawned into the run queue, run by the loop, waiting in epoll after await, back in the run queue when its fd is ready](task-states.svg)

That's all `async`/`await` is in Rust, Python, C# or JavaScript. Those compilers turn
each async function into the state machine for you instead of giving it a stack
("stackless" coroutines), but the event loop underneath is this one.

## Lesson: one-shot interest

A task waits for one event at a time. `EPOLLONESHOT` (`1 << 30`) makes epoll report a
descriptor **once**, then ignore it until you re-arm it with `EPOLL_CTL_MOD` (3). So the
next `await_readable` on the same fd is a MOD, and the first one is an ADD (MOD answers
−ENOENT for an fd epoll doesn't know yet).

## Lesson: starting a task

A new task has never been suspended, so there's no saved context to resume: you make
one up. Write the address of a trampoline at the top of the new stack and set the saved
`rsp` to it. `co_switch` ends with `ret`, which "returns" into the trampoline. The
trampoline calls `fn(arg)`; when that returns, the task is over: free its slot and
switch to the event loop for the last time.

## Gate

The starter contains the server as two **tasks**, `acceptor` and `client`: straight-line
code that calls `await_readable(fd)` wherever it would have to wait. Don't change them.
Write the runtime: `spawn(fn, arg)`, `await_readable(fd)` and the event loop `run`. The
starter sets out the task table, stacks and run-queue variables; `co_switch` is
provided. The tests are level 109's: many clients, data in pieces, half-closed
connections. Constraint: at most 170 instructions.

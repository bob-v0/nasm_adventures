"""Level 40: a box-pushing puzzle in a boot sector. The game's own simulation of the
rules gives the expected screen for each sequence of keys."""

MAP = [
    "##########",
    "#  .#    #",
    "# $ # $  #",
    "#   $  # #",
    "## ##  # #",
    "#  .  @. #",
    "##########",
]
DIRS = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}


def play(keys):
    grid = [list(r) for r in MAP]
    (py, px), = [(y, x) for y, r in enumerate(grid) for x, c in enumerate(r) if c in "@+"]
    moves = 0
    for k in keys:
        if not any(c == "$" for r in grid for c in r):
            break                                   # won: keys after that do nothing
        dy, dx = DIRS[k]
        ty, tx = py + dy, px + dx
        t = grid[ty][tx]
        if t == "#":
            continue
        if t in "$*":
            by, bx = ty + dy, tx + dx
            b = grid[by][bx]
            if b not in " .":
                continue
            grid[by][bx] = "*" if b == "." else "$"
            grid[ty][tx] = "." if t == "*" else " "
            t = grid[ty][tx]
        grid[py][px] = "." if grid[py][px] == "+" else " "
        grid[ty][tx] = "+" if t == "." else "@"
        py, px = ty, tx
        moves += 1
    won = not any(c == "$" for r in grid for c in r)
    return ["".join(r).rstrip() for r in grid], moves, won


def solve():
    """Breadth-first search over (player, boxes): the shortest solution in moves."""
    from collections import deque
    start = play([])[0]
    walls = {(y, x) for y, r in enumerate(MAP) for x, c in enumerate(r) if c == "#"}
    goals = {(y, x) for y, r in enumerate(MAP) for x, c in enumerate(r) if c in ".*+"}
    boxes = frozenset((y, x) for y, r in enumerate(MAP) for x, c in enumerate(r) if c in "$*")
    (p,) = [(y, x) for y, r in enumerate(MAP) for x, c in enumerate(r) if c in "@+"]
    seen = {(p, boxes): None}
    q = deque([(p, boxes)])
    while q:
        p, b = q.popleft()
        if b <= goals:
            path = []
            s = (p, b)
            while seen[s] is not None:
                s, k = seen[s]
                path.append(k)
            return path[::-1]
        for k, (dy, dx) in DIRS.items():
            t = (p[0] + dy, p[1] + dx)
            if t in walls:
                continue
            nb = b
            if t in b:
                beyond = (t[0] + dy, t[1] + dx)
                if beyond in walls or beyond in b:
                    continue
                nb = (b - {t}) | {beyond}
            s = (t, nb)
            if s not in seen:
                seen[s] = ((p, b), k)
                q.append(s)
    return None


def screen_for(keys):
    rows, moves, won = play(keys)
    status = f"You win in {moves} moves!" if won else f"Moves: {moves}"
    return rows, status, won


def case(name, keys, hidden=False):
    rows, status, won = screen_for(keys)
    t = {"name": name, "hidden": hidden, "inject": {"keys": keys, "key_delay": 1.0},
         "expect": {"check": True, "rows": rows, "status": status, "max_size": 512,
                    "until": "halt" if won else "time", "timeout": 6 if won else 2.5}}
    return t


def check(test, run, regs, screen, serial):
    e = test.expect
    out = []
    for y, want in enumerate(e["rows"]):
        if screen[y] != want:
            out.append(f"row {y}: expected {want!r}, got {screen[y]!r}")
            break
    if screen[24].strip() != e["status"]:
        out.append(f"row 24: expected {e['status']!r}, got {screen[24].strip()!r}")
    return out


def fixed_tests(ctx):
    sol = solve()
    return [case("the start", []), case("walking into a wall", ["right", "right", "down"]),
            case("pushing a box", ["up", "left", "up", "left"]),
            case("the shortest solution", sol)]


def generate(rng, count, ctx):
    sol = solve()
    out = [case("pushing a box into a wall", ["left", "left", "left", "up", "up", "up"], True),
           case("keys after winning", sol + ["left", "left"], True)]
    for i in range(count):
        out.append(case(f"random keys {i}", [rng.choice(list(DIRS)) for _ in range(30)], True))
    return out


def audit(build):
    n = build.elf.stat().st_size
    return [("fits in the boot sector (512 bytes)", n <= 512, f"{n} bytes")]

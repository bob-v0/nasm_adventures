"""Level 17: records in frames of their own, shown through one window page that is
remapped for each. Without invalidating the old translation, the window keeps showing
the previous record."""

import functools

TITLES = ["the boot log", "the memory map", "the frame allocator's state", "page faults so far",
          "the IDT", "the TSS", "the GDT", "CPU features", "the command line", "the modules",
          "timer ticks", "the end of the list"]


@functools.lru_cache(maxsize=None)
def records() -> bytes:
    out = b""
    for n, t in enumerate(TITLES):
        page = f"record {n}: {t}".encode() + b"\0"
        out += page.ljust(4096, b"\0")
    return out


def case(name, order, hidden=False):
    want = "".join(f"record {n}: {TITLES[n]}\r\n" for n in order) + "done\r\n"
    return {"name": name, "hidden": hidden,
            "inject": {"modules": [records().hex()], "cmdline": "show=" + ",".join(map(str, order))},
            "expect": {"serial": want, "timeout": 10}}


def fixed_tests(ctx):
    return [case("one record", [3]), case("the same one twice", [5, 5]),
            case("two records", [0, 1])]


def generate(rng, count, ctx):
    out = []
    for i in range(count):
        order = [rng.randrange(len(TITLES)) for _ in range(rng.randint(3, 9))]
        out.append(case(f"random {i}", order, True))
    return out + [case("all of them", list(range(len(TITLES))), True)]


def witness_test(w, ctx):
    order = w.get("show")
    if set(w) != {"show"} or not isinstance(order, str):
        raise ValueError('the witness is the list of records to show: `;! witness show = "0,1"`')
    try:
        nums = [int(x) for x in order.split(",")]
    except ValueError:
        raise ValueError('the witness: record numbers separated by commas, `;! witness show = "0,1"`')
    if not nums or any(not 0 <= n < len(TITLES) for n in nums):
        raise ValueError(f"records are numbered 0 to {len(TITLES) - 1}")
    return case("witness", nums)

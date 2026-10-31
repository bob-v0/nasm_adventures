"""Brief figures in the web UI's dark theme.

The figures in levels/NNN/figures/ are drawn for a light background, which is how they
look on GitHub. The web UI is dark, so the server sends them through `dark()`: every
colour's lightness is mirrored (in OKLab, where lightness is perceptual) between the
panel's background and the text colour, keeping its hue and saturation. White paper
becomes the dark panel, black ink becomes light text, pale fills become deep tints, and
a coloured line stays the same colour, made light enough to read on a dark ground."""

from __future__ import annotations

import functools
import re

PAPER = "#1b2129"     # what white becomes: the UI's --panel-2
INK = "#d7dde5"       # what black becomes: the UI's --text

_COLOUR = re.compile(r"""((?:fill|stroke|stop-color|flood-color|lighting-color|color)\s*[=:]\s*["']?)"""
                     r"(#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b|white\b|black\b)")


def _srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(c: float) -> float:
    c = min(max(c, 0.0), 1.0)
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def _oklab(hex_: str) -> tuple[float, float, float]:
    r, g, b = (_srgb_to_linear(int(hex_[i:i + 2], 16) / 255) for i in (1, 3, 5))
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def _hex(L: float, a: float, b: float) -> str:
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    rgb = (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
           -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
           -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)
    return "#" + "".join(f"{round(_linear_to_srgb(c) * 255):02x}" for c in rgb)


@functools.lru_cache(maxsize=None)
def dark_colour(colour: str) -> str:
    c = colour.lower()
    c = {"white": "#ffffff", "black": "#000000"}.get(c, c)
    if len(c) == 4:
        c = "#" + "".join(ch * 2 for ch in c[1:])
    L, a, b = _oklab(c)
    (lo, pa, pb), (hi, ia, ib) = _oklab(PAPER), _oklab(INK)
    chroma = (a * a + b * b) ** 0.5
    L2 = lo + (1 - L) ** 0.75 * (hi - lo)      # (a curve: dark ink becomes bright text)
    if chroma > 0.08:                  # a real colour (a line, a highlight): keep it bright
        L2 = max(L2, 0.68)
    elif chroma > 0.02:                # a tint: a deep version, a little more saturated
        a, b = a * 1.3, b * 1.3
    else:                              # a grey: the UI's greys, paper to ink
        a, b = pa + (ia - pa) * (1 - L), pb + (ib - pb) * (1 - L)
    return _hex(L2, a, b)


def dark(svg: str) -> str:
    """The figure's dark-theme version."""
    out = _COLOUR.sub(lambda m: m.group(1) + dark_colour(m.group(2)), svg)
    # anything without a colour of its own is black by default: make it the ink
    out = re.sub(r"<svg\b(?![^>]*\sfill=)", f'<svg fill="{INK}"', out, count=1)
    return out

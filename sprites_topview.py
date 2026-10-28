"""Motos desenhadas para 24–32 px: massa escura, direção clara e circuitos seletivos.

+x é a frente. A posição lógica continua no nariz; prévias usam centered_origin.
O corpo tem oito direções em cache. Os arcos da Orbital reutilizam linhas do Canvas.
"""

from collections import OrderedDict
from dataclasses import dataclass
from functools import lru_cache
import math
import tkinter as tk

import theme as T

UNIT = 28
ORBITAL_PERIOD = 10.0
LINE_MATERIALS = frozenset(("edge", "rim", "spine", "lamp", "visor", "support", "ring"))
STRUCTURE_MATERIALS = frozenset(("shell", "fender", "wheel", "fin"))


def oval(cx, cy, rx, ry, count=32):
    return [
        (
            cx + math.cos(i * math.tau / count) * rx,
            cy + math.sin(i * math.tau / count) * ry,
        )
        for i in range(count)
    ]


def symmetric(half):
    return half + [(x, -y) for x, y in reversed(half) if y]


@dataclass(frozen=True)
class Cycle:
    name: str
    hull: tuple
    trail_color: str
    length: float = 1.0
    width: float = 1.0

    def tint(self, selected=None):
        return selected or self.trail_color


CYCLES = (
    Cycle(
        "CLASSICA",
        tuple(
            symmetric(
                [
                    (-0.19, 0),
                    (-0.28, -0.095),
                    (-0.49, -0.13),
                    (-0.66, -0.185),
                    (-0.80, -0.15),
                    (-0.88, -0.075),
                    (-0.86, 0),
                ]
            )
        ),
        T.CYAN,
        1.08,
        0.37,
    ),
    Cycle(
        "INTERCEPTOR",
        tuple(
            symmetric(
                [
                    (0.01, 0),
                    (-0.13, -0.12),
                    (-0.29, -0.15),
                    (-0.45, -0.10),
                    (-0.72, -0.27),
                    (-0.94, -0.25),
                    (-0.80, -0.06),
                    (-0.90, 0),
                ]
            )
        ),
        T.ORANGE,
        1.03,
        0.54,
    ),
    Cycle(
        "TITAN",
        tuple(
            symmetric(
                [
                    (0.10, 0),
                    (0.06, -0.105),
                    (-0.16, -0.23),
                    (-0.66, -0.28),
                    (-0.91, -0.225),
                    (-0.99, -0.11),
                    (-0.97, 0),
                ]
            )
        ),
        T.CYAN,
        1.12,
        0.63,
    ),
    Cycle(
        "FALCÃO",
        tuple(
            symmetric(
                [
                    (0.035, 0),
                    (-0.23, -0.10),
                    (-0.40, -0.13),
                    (-0.78, -0.33),
                    (-0.98, -0.32),
                    (-0.81, -0.09),
                    (-0.96, 0),
                ]
            )
        ),
        T.GREEN,
        1.08,
        0.66,
    ),
    Cycle(
        "LANÇA",
        tuple(
            symmetric(
                [(0.14, 0), (-0.36, -0.09), (-0.72, -0.067), (-0.99, -0.05), (-1.10, 0)]
            )
        ),
        T.CORE,
        1.25,
        0.28,
    ),
    Cycle(
        "ORBITAL",
        tuple(
            symmetric(
                [
                    (0.01, 0),
                    (-0.19, -0.065),
                    (-0.35, -0.10),
                    (-0.61, -0.13),
                    (-0.79, -0.08),
                    (-0.88, 0),
                ]
            )
        ),
        T.PURPLE,
        1.08,
        0.66,
    ),
)


def orbital_arcs(elapsed=0.0):
    phase = elapsed * math.tau / ORBITAL_PERIOD
    return [
        [
            (
                -0.46
                + math.cos(phase + i * math.tau / 3 + j * math.radians(80) / 20) * 0.54,
                math.sin(phase + i * math.tau / 3 + j * math.radians(80) / 20) * 0.33,
            )
            for j in range(21)
        ]
        for i in range(3)
    ]


def wheel(x, y, rx, ry):
    result = [(oval(x, y, rx, ry), "wheel")]
    for start in (-math.pi / 2 - 0.65, math.pi / 2 - 0.65):
        result.append(
            (
                [
                    (
                        x + math.cos(start + i * 1.3 / 16) * rx,
                        y + math.sin(start + i * 1.3 / 16) * ry,
                    )
                    for i in range(17)
                ],
                "rim",
            )
        )
    return result


@lru_cache(maxsize=12)
def normalized_layers(model=0, include_ring=True):
    model %= len(CYCLES)
    hull = CYCLES[model].hull
    layers = []
    if model == 2:
        for x in (-0.79, -0.24):
            for y in (-0.24, 0.24):
                layers += wheel(x, y, 0.14, 0.075)
    else:
        rear, front = {
            0: ((-0.87, 0.17, 0.13), (-0.12, 0.11, 0.069)),
            1: ((-0.84, 0.17, 0.10), (-0.14, 0.11, 0.064)),
            3: ((-0.85, 0.17, 0.10), (-0.13, 0.105, 0.06)),
            4: ((-0.93, 0.14, 0.044), (-0.30, 0.105, 0.034)),
            5: ((-0.78, 0.13, 0.105), (-0.13, 0.10, 0.06)),
        }[model]
        for x, rx, ry in (rear, front):
            layers += wheel(x, 0, rx, ry)
    if model == 5:
        for angle in (0, 2.2, 4.1):
            layers.append(
                (
                    [
                        (-0.46 + math.cos(angle) * 0.13, math.sin(angle) * 0.08),
                        (-0.46 + math.cos(angle) * 0.52, math.sin(angle) * 0.31),
                    ],
                    "support",
                )
            )
    layers.append((list(hull), "shell"))
    if model == 0:
        layers.append(
            (
                symmetric([(0.02, 0), (-0.055, -0.042), (-0.22, -0.078), (-0.30, 0)]),
                "fender",
            )
        )
        for s in (-1, 1):
            layers.extend(
                [
                    (
                        [
                            (-0.83, s * 0.085),
                            (-0.66, s * 0.172),
                            (-0.46, s * 0.115),
                            (-0.27, s * 0.082),
                            (-0.06, s * 0.04),
                        ],
                        "edge",
                    ),
                    (
                        [(-0.78, s * 0.10), (-0.64, s * 0.15), (-0.55, s * 0.115)],
                        "accent",
                    ),
                ]
            )
    elif model == 1:
        for s in (-1, 1):
            layers.extend(
                [
                    (
                        [
                            (-0.93, s * 0.238),
                            (-0.73, s * 0.253),
                            (-0.45, s * 0.09),
                            (-0.28, s * 0.139),
                            (-0.10, s * 0.08),
                        ],
                        "edge",
                    ),
                    (
                        [
                            (-0.90, s * 0.22),
                            (-0.73, s * 0.23),
                            (-0.60, s * 0.15),
                            (-0.81, s * 0.17),
                        ],
                        "accent",
                    ),
                ]
            )
    elif model == 2:
        # Cunha larga, pneus embutidos e cabine em gota; sem placa retangular central.
        for s in (-1, 1):
            layers.extend(
                [
                    (
                        [
                            (-0.93, s * 0.12),
                            (-0.83, s * 0.205),
                            (-0.19, s * 0.204),
                            (0.025, s * 0.085),
                        ],
                        "edge",
                    ),
                    (
                        [
                            (-0.87, s * 0.185),
                            (-0.64, s * 0.225),
                            (-0.18, s * 0.18),
                            (-0.06, s * 0.105),
                            (-0.30, s * 0.145),
                        ],
                        "fender",
                    ),
                    (
                        [
                            (-0.83, s * 0.18),
                            (-0.60, s * 0.20),
                            (-0.21, s * 0.158),
                            (-0.04, s * 0.075),
                        ],
                        "spine",
                    ),
                    (
                        [
                            (-0.20, s * 0.17),
                            (-0.07, s * 0.10),
                            (-0.15, s * 0.11),
                            (-0.33, s * 0.16),
                        ],
                        "accent",
                    ),
                ]
            )
        layers.append(
            (
                symmetric(
                    [
                        (-0.19, 0),
                        (-0.32, -0.084),
                        (-0.56, -0.117),
                        (-0.72, -0.069),
                        (-0.77, 0),
                    ]
                ),
                "canopy",
            )
        )
        layers.append(([(-0.34, -0.073), (-0.25, 0), (-0.34, 0.073)], "visor"))
    elif model == 3:
        for s in (-1, 1):
            layers.extend(
                [
                    (
                        [
                            (-0.96, s * 0.31),
                            (-0.78, s * 0.315),
                            (-0.39, s * 0.119),
                            (-0.15, s * 0.075),
                        ],
                        "edge",
                    ),
                    (
                        [
                            (-0.92, s * 0.282),
                            (-0.77, s * 0.29),
                            (-0.49, s * 0.15),
                            (-0.73, s * 0.21),
                        ],
                        "accent",
                    ),
                ]
            )
    elif model == 4:
        layers.append(
            (
                symmetric([(-0.87, 0), (-1.10, -0.14), (-1.055, -0.03), (-1.11, 0)]),
                "fin",
            )
        )
        for s in (-1, 1):
            layers.extend(
                [
                    (
                        [
                            (-1.07, s * 0.116),
                            (-0.86, s * 0.047),
                            (-0.37, s * 0.075),
                            (0.14, 0),
                        ],
                        "edge",
                    ),
                    ([(-0.35, s * 0.064), (0.105, 0), (-0.14, s * 0.025)], "accent"),
                ]
            )
        layers.append(([(-0.42, 0), (0.14, 0)], "spine"))
    else:
        for s in (-1, 1):
            layers.extend(
                [
                    (
                        [
                            (-0.83, s * 0.06),
                            (-0.61, s * 0.117),
                            (-0.35, s * 0.09),
                            (-0.10, s * 0.043),
                        ],
                        "edge",
                    ),
                    (
                        [(-0.74, s * 0.08), (-0.60, s * 0.105), (-0.48, s * 0.073)],
                        "accent",
                    ),
                ]
            )
    if model != 2:
        # Um capacete com viseira: sem segundo círculo que pareça um olho.
        layers.extend(
            [
                (
                    symmetric(
                        [(-0.34, 0), (-0.45, -0.065), (-0.66, -0.058), (-0.73, 0)]
                    ),
                    "suit",
                ),
                (oval(-0.39, 0, 0.087, 0.062, 20), "helmet"),
                ([(-0.68, 0), (-0.51, 0)], "spine"),
                ([(-0.355, -0.043), (-0.322, 0), (-0.355, 0.043)], "visor"),
            ]
        )
    tail = {0: -1.025, 1: -0.99, 2: -0.975, 3: -0.99, 4: -1.09, 5: -0.895}[model]
    layers.append(
        (
            [
                (tail, -0.035),
                (tail + 0.025, -0.035),
                (tail + 0.025, 0.035),
                (tail, 0.035),
            ],
            "emitter",
        )
    )
    nose = {0: 0.012, 1: 0.012, 2: 0.075, 3: 0.025, 4: 0.14, 5: 0.014}[model]
    layers.append(
        (
            [
                (nose, -0.035 if model != 2 else -0.065),
                (nose, 0.035 if model != 2 else 0.065),
            ],
            "lamp",
        )
    )
    if model == 5 and include_ring:
        layers.extend((points, "ring") for points in orbital_arcs())
    return layers


@lru_cache(maxsize=12)
def top_layers(model=0, include_ring=True):
    return [
        ([(x * UNIT, y * UNIT) for x, y in points], material)
        for points, material in normalized_layers(model, include_ring)
    ]


@lru_cache(maxsize=6)
def model_bounds(model):
    points = [point for shape, material in normalized_layers(model) for point in shape]
    if model == 5:
        points.extend([(-1.0, -0.33), (0.08, 0.33)])
    return (
        min(x for x, y in points),
        min(y for x, y in points),
        max(x for x, y in points),
        max(y for x, y in points),
    )


def centered_origin(model, x, y, d=(1, 0), scale=1.0):
    a, b, c, e = model_bounds(model)
    cx, cy = (a + c) * UNIT * scale / 2, (b + e) * UNIT * scale / 2
    return x - (cx * d[0] - cy * d[1]), y - (cx * d[1] + cy * d[0])


def material_style(material, color, scale=1.0):
    """Mesmo material na imagem e na alternativa vetorial, na cor do piloto."""
    if material in LINE_MATERIALS:
        tint = T.blend(color, T.BIKE_BODY, 0.25) if material == "rim" else color
        if material == "support":
            tint = T.blend(color, T.BIKE_BODY, 0.62)
        width = max(0.8, scale * 0.72)
        core = 0.28
        if material == "rim":
            width = max(0.7, scale * 0.60)
            core = 0.12
        if material == "spine":
            width = max(0.9, scale * 0.82)
            core = 0.40
        if material == "ring":
            width = max(0.65, scale * 0.48)
            core = 0.20
        if material == "support":
            width = max(0.7, scale * 0.60)
            core = 0.05
        if material == "visor":
            width = max(0.8, scale * 0.65)
            core = 0.55
        if material == "lamp":
            width = max(1.1, scale * 0.95)
            core = 0.96
        return tint, width, core
    return (
        {
            "shell": T.BIKE_BODY,
            "fender": T.BIKE_ARMOR,
            "fin": T.BIKE_BODY,
            "wheel": T.RUBBER,
            "suit": T.BIKE_BODY,
            "helmet": T.blend(T.BIKE_BODY, color, 0.07),
            "canopy": T.blend(T.BIKE_BODY, color, 0.055),
            "emitter": T.blend(color, T.BIKE_BODY, 0.86),
            "accent": T.blend(T.BIKE_BODY, color, 0.82),
        }[material],
        None,
        None,
    )


def render_top(model, color, scale=1.0, direction=0, elapsed=0.0, include_ring=True):
    extent = math.ceil(40 * scale)
    art = T.RasterArt((extent * 2, extent * 2), supersample=4 if scale < 2 else 2)
    angle = direction * math.tau / 8
    ca, sa = math.cos(angle), math.sin(angle)
    layers = list(normalized_layers(model, False))
    if model == 5 and include_ring:
        layers.extend((points, "ring") for points in orbital_arcs(elapsed))
    for points, material in layers:
        pts = [
            (
                extent + (x * ca - y * sa) * UNIT * scale,
                extent + (x * sa + y * ca) * UNIT * scale,
            )
            for x, y in points
        ]
        tint, width, core = material_style(material, color, scale)
        if width is not None:
            art.line(pts, tint, width, core_mix=core)
        else:
            art.polygon(pts, tint)
    return art.finish(radius=max(0.8, scale * 0.48))


class BikeItems(list):
    """Corpo e arcos são ocultados/excluídos juntos pela arena e seus efeitos."""


def _direction(d):
    return round(math.atan2(d[1], d[0]) * 8 / math.tau) % 8


def _photo(cv, model, color, scale, direction):
    cache = getattr(cv, "_cycle_sprites", None)
    if cache is None:
        cache = cv._cycle_sprites = OrderedDict()
    key = (model, color, round(scale, 3), direction)
    if key not in cache:
        cache[key] = T.ImageTk.PhotoImage(
            render_top(*key[:3], direction, include_ring=model != 5), master=cv
        )
        if len(cache) > 192:
            cache.popitem(last=False)
    cache.move_to_end(key)
    return cache[key]


def draw_bike(cv, x, y, d, color, model=0, scale=1.0, tags=(), elapsed=0.0):
    model %= len(CYCLES)
    items = BikeItems()
    items.color, items.photo = color, None
    items.raster = T.Image is not None and isinstance(cv, tk.Canvas)
    items.rings = []
    if items.raster:
        for direction in (0, 2, 4, 6):
            _photo(cv, model, color, scale, direction)
        items.photo = _photo(cv, model, color, scale, _direction(d))
        items.append(cv.create_image(x, y, image=items.photo, tags=tags))
    else:
        for shape, material in top_layers(model, False):
            pts = bike_points(shape, x, y, d, scale)
            tint, width, core = material_style(material, color, scale)
            if width is not None:
                items.append(
                    cv.create_line(
                        *pts, fill=T.blend(tint, T.CORE, core), width=width, tags=tags
                    )
                )
            else:
                items.append(cv.create_polygon(*pts, fill=tint, outline="", tags=tags))
    if model == 5:
        for arc in orbital_arcs(elapsed):
            group = []
            for tint, weight in T.glow_layers(color, max(0.45, scale * 0.43)):
                item = cv.create_line(
                    *bike_points(
                        [(a * UNIT, b * UNIT) for a, b in arc], x, y, d, scale
                    ),
                    fill=tint,
                    width=weight,
                    tags=tags
                )
                items.append(item)
                group.append(item)
            items.rings.append(group)
    return items


def bike_points(shape, x, y, d, scale=1.0):
    dx, dy = d
    return [
        v
        for sx, sy in shape
        for v in (x + (sx * dx - sy * dy) * scale, y + (sx * dy + sy * dx) * scale)
    ]


def move_bike(cv, items, model, x, y, d, scale=1.0, elapsed=0.0):
    if getattr(items, "raster", False):
        direction = _direction(d)
        photo = _photo(cv, model, items.color, scale, direction)
        if photo is not items.photo:
            items.photo = photo
            cv.itemconfigure(items[0], image=photo)
        cv.coords(items[0], x, y)
        angle = direction * math.tau / 8
        ring_direction = (math.cos(angle), math.sin(angle))
    else:
        for item, (shape, _) in zip(items, top_layers(model, False)):
            cv.coords(item, *bike_points(shape, x, y, d, scale))
        ring_direction = d
    for group, arc in zip(
        getattr(items, "rings", ()), orbital_arcs(elapsed) if model == 5 else ()
    ):
        coords = bike_points(
            [(a * UNIT, b * UNIT) for a, b in arc], x, y, ring_direction, scale
        )
        for item, (_, weight) in zip(
            group, T.glow_layers(items.color, max(0.45, scale * 0.43))
        ):
            cv.coords(item, *coords)
            cv.itemconfigure(item, width=weight)

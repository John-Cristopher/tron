"""Um único cenário e câmera para a montagem da Grade e a revelação do logo."""

from dataclasses import dataclass
from functools import cached_property
import math
import random

import theme as T

LOGO_ORIGIN = (0.0, -18.0, 190.0)
LOGO_SCALE = 2.3
GRID_START = 35.0
LOOK_START = 43.0
LOGO_TIME = 46.0


def smooth(value):
    value = max(0.0, min(1.0, value))
    return value * value * (3 - 2 * value)


@dataclass(frozen=True)
class View:
    width: float
    height: float
    x: float
    y: float
    z: float
    pitch: float
    roll: float = 0.0

    @cached_property
    def basis(self):
        return (
            math.cos(self.pitch),
            math.sin(self.pitch),
            math.cos(self.roll),
            math.sin(self.roll),
        )

    @cached_property
    def focal(self):
        return min(self.width, self.height * 1.72) * 1.04

    def transform(self, point):
        x, y, z = point[0] - self.x, point[1] - self.y, point[2] - self.z
        ca, sa, cr, sr = self.basis
        y, z = y * ca + z * sa, -y * sa + z * ca
        return x * cr - y * sr, x * sr + y * cr, z

    def project(self, point):
        x, y, z = point
        focal = self.focal
        return self.width * 0.5 + focal * x / z, self.height * 0.48 + focal * y / z

    @cached_property
    def planes(self):
        return (
            (0.0, 0.0, 1.0, -0.28),
            (1.0, 0.0, self.width * 0.5 / self.focal, 0.0),
            (-1.0, 0.0, self.width * 0.5 / self.focal, 0.0),
            (0.0, 1.0, self.height * 0.48 / self.focal, 0.0),
            (0.0, -1.0, self.height * 0.52 / self.focal, 0.0),
        )

    def clip_face(self, points):
        # Recortar antes de projetar evita triângulos falsos ao inclinar a câmera.
        for nx, ny, nz, bias in self.planes:
            if not points:
                break
            result = []
            previous = points[-1]
            da = nx * previous[0] + ny * previous[1] + nz * previous[2] + bias
            for current in points:
                db = nx * current[0] + ny * current[1] + nz * current[2] + bias
                if (da >= 0) != (db >= 0):
                    ratio = da / (da - db)
                    result.append(
                        tuple(
                            previous[i] + (current[i] - previous[i]) * ratio
                            for i in range(3)
                        )
                    )
                if db >= 0:
                    result.append(current)
                previous, da = current, db
            points = result
        return points

    def clip_segment(self, a, b):
        for nx, ny, nz, bias in self.planes:
            da = nx * a[0] + ny * a[1] + nz * a[2] + bias
            db = nx * b[0] + ny * b[1] + nz * b[2] + bias
            if da < 0 and db < 0:
                return None
            if (da >= 0) != (db >= 0):
                ratio = da / (da - db)
                point = tuple(a[i] + (b[i] - a[i]) * ratio for i in range(3))
                if da < 0:
                    a = point
                else:
                    b = point
        return a, b


def world_camera(t, width, height):
    if t < LOOK_START:
        z = 115 * smooth((t - 38) / 5)
        y, pitch, x = -1.6, 0.0, 0.0
    elif t < LOGO_TIME:
        progress = smooth((t - LOOK_START) / (LOGO_TIME - LOOK_START))
        z, y, x = 115 + 31 * progress, -1.6, 0.0
        pitch = math.atan2(16.4, 44) * progress
    elif t < 50.0:
        progress = smooth((t - LOGO_TIME) / 4.0)
        z, y, x = 146 + 4 * progress, -1.6 - 1.4 * progress, 0.0
        pitch = (1 - progress) * math.atan2(16.4, 44) + progress * math.atan2(15, 40)
    else:
        progress = max(0.0, min(1.0, (t - 50.0) / 11.5)) ** 2
        z = 150 + 46 * progress
        y = -3 - (z - 150) * 15 / 40
        x, pitch = 1.03 * LOGO_SCALE * progress, math.atan2(15, 40)
    # Deriva contínua e pequena, amortecida antes de atravessar o portal.
    drift = smooth((t - 38) / 3) * (1 - smooth((t - 55) / 5))
    x += math.sin(t * .63) * .13 * drift
    y += math.sin(t * .91) * .055 * drift
    roll = -0.035 * math.sin(math.pi * max(0.0, min(1.0, (t - LOOK_START) / 5.5)))
    roll += math.sin(t * .47) * .003 * drift
    return View(width, height, x, y, z, pitch, roll)


@dataclass(frozen=True)
class Block:
    x: float
    z: float
    width: float
    depth: float
    height: float
    delay: float
    duration: float
    distant: bool = False
    base: float = 0.0

    def bounds(self):
        return (
            self.x - self.width / 2,
            self.x + self.width / 2,
            self.z,
            self.z + self.depth,
        )


def world_blocks():
    """Células reservadas impedem a interseção entre os volumes."""
    rng = random.Random(71)
    blocks = []
    for side in (-1, 1):
        for row in range(6):
            for column, x, z, width, depth, height in (
                (0, side * 15, 26 + row * 26, rng.uniform(8, 10.5), 14,
                 rng.uniform(8, 19) if row % 3 else 25),
                (1, side * 34, 36 + row * 26, rng.uniform(12, 16), 13,
                 rng.uniform(18, 38) if row % 3 else 52),
            ):
                delay = 34.0 + row * .34 + column * .2
                stepped = (row + column) % 2 == 0
                base_height = height * .68 if stepped else height
                blocks.append(Block(x, z, width, depth, base_height, delay, 3.0))
                if stepped:
                    blocks.append(Block(x, z + depth * .18, width * .58,
                        depth * .64, height - base_height, delay + .7, 2.4,
                        base=-base_height))
    # Maciços retangulares no horizonte: três profundidades com espaços entre blocos.
    for layer in range(3):
        for column in range(-5, 6):
            blocks.append(
                Block(
                    column * 48,
                    310 + layer * 90,
                    rng.uniform(30, 43),
                    64,
                    rng.uniform(25, 90),
                    34.0 + layer * 0.5,
                    4.2,
                    True,
                )
            )
    # Pórtico já pertence à paisagem; o logo acende no seu vão aos 46 s.
    for x in (-15.6, 15.6):
        blocks.append(Block(x, 190, 1.2, 4, 24, 37.5, 4.5))
    blocks.append(Block(0, 190, 30, 4, 0.9, 37.5, 4.5, base=-23.1))
    return blocks


class IntroWorld:
    def __init__(self, canvas, width, height):
        self.cv, self.w, self.h = canvas, width, height
        self.visible = False
        self.blocks = world_blocks()
        self.view = world_camera(35, width, height)
        self.items = []
        self.styles = {}
        self.sky = []
        for i in range(14):
            item = canvas.create_rectangle(
                0,
                height * i / 14,
                width,
                height * (i + 1) / 14 + 1,
                fill=T.blend(T.BACKGROUND, T.SKY_HORIZON, (i / 13) ** 2 * 0.35),
                outline="",
                state="hidden",
                tags=("intro", "intro_world"),
            )
            self.sky.append(item)
            self.items.append(item)
        self.ground = self._polygon()
        self.rows = [self._line() for _ in range(70)]
        self.columns = [self._line() for _ in range(53)]
        self.faces = [[self._polygon() for _ in range(6)] for block in self.blocks]
        self.reflections = [[self._polygon() for _ in range(0 if block.distant else 2)] for block in self.blocks]
        self.lights = [[self._line() for _ in range(0 if block.distant else 22)] for block in self.blocks]
        self.reflected_lights = [self._line() for _ in self.blocks]
        self.data = [[self._line() for _ in range(3)] for _ in range(12)]
        self.cycles = [[self._line() for _ in range(3)] for _ in range(2)]
        self.recognizer = self._polygon()
        self.recognizer_lamp = self._line()
        self.beam = [self._line() for _ in range(3)]
        self.last_depths = []
        self.visible_faces = set()

    def _polygon(self):
        item = self.cv.create_polygon(
            0,
            0,
            0,
            0,
            0,
            0,
            fill=T.BACKGROUND,
            outline="",
            state="hidden",
            tags=("intro", "intro_world"),
        )
        self.items.append(item)
        self.styles[item] = {"state": "hidden"}
        return item

    def _line(self):
        item = self.cv.create_line(
            0,
            0,
            0,
            0,
            fill=T.GRID,
            width=1,
            state="hidden",
            tags=("intro", "intro_world"),
        )
        self.items.append(item)
        self.styles[item] = {"state": "hidden"}
        return item

    def _style(self, item, **options):
        previous = self.styles.setdefault(item, {})
        changed = {key: value for key, value in options.items() if previous.get(key) != value}
        if changed:
            self.cv.itemconfigure(item, **changed)
            previous.update(changed)

    def hide(self):
        if self.visible:
            for item in self.items:
                self._style(item, state="hidden")
            self.visible = False

    def _face(self, item, points, fill, edge=""):
        return self._camera_face(
            item, [self.view.transform(point) for point in points], fill, edge
        )

    def _camera_face(self, item, points, fill, edge=""):
        clipped = self.view.clip_face(points)
        if len(clipped) < 3:
            self._style(item, state="hidden")
            return False
        coords = [v for point in clipped for v in self.view.project(point)]
        self.cv.coords(item, *coords)
        self._style(item, state="normal", fill=fill, outline=edge, width=1)
        return True

    def _segment(self, item, a, b, color, width=1):
        a, b = self.view.transform(a), self.view.transform(b)
        segment = self.view.clip_segment(a, b)
        if segment is None:
            self._style(item, state="hidden")
            return
        a, b = segment
        self.cv.coords(item, *self.view.project(a), *self.view.project(b))
        self._style(item, state="normal", fill=color, width=width)

    def _glow(self, items, a, b, strength, width=1, color=T.CYAN):
        if strength <= .005:
            for item in items:
                self._style(item, state="hidden")
            return
        for item, (tint, weight) in zip(items, T.glow_layers(color, width)):
            self._segment(item, a, b, T.blend(T.BACKGROUND, tint, strength), weight)

    def _building_lights(self, index, block, growth, t):
        items = self.lights[index]
        if not items:
            return
        x0, x1, z0, z1 = block.bounds()
        top, bottom = block.base - block.height * growth, block.base
        if self.view.z >= z0 or growth <= 0:
            for item in items:
                self._style(item, state="hidden")
            return
        distance = max(1, z0 - self.view.z)
        strength = growth * math.exp(-distance / 270)
        width = max(.65, min(2, 70 / distance))
        # Só o teto e uma quina recebem luz forte; as outras arestas ficam apagadas.
        self._glow(items[:3], (x0, top, z0), (x1, top, z0), strength, width)
        self._glow(items[3:6], (x0, top, z0), (x0, bottom, z0), strength * .65, width)
        phase = (t * .35 + index * .173) % 1
        start = top + (bottom - top) * phase
        end = min(bottom, start + (bottom - top) * .20)
        self._glow(items[6:9], (x0, start, z0), (x0, end, z0), strength, width * 1.3, T.CORE)
        for j, item in enumerate(items[9:12]):
            y = top + (bottom - top) * (.25 + j * .24)
            self._segment(item, (x0, y, z0), (x1, y, z0),
                          T.blend(T.BACKGROUND, T.CYAN, strength * .22))
        # Janelas em pequenos segmentos, sem textura calculada por quadro.
        for j, item in enumerate(items[12:21]):
            row, col = divmod(j, 3)
            y = top + (bottom - top) * (.17 + row * .27)
            x = x0 + (x1 - x0) * (.16 + col * .27)
            tint = T.CYAN if (index + j) % 5 else T.AMBER
            self._segment(item, (x, y, z0), (x + (x1 - x0) * .07, y, z0),
                          T.blend(T.BACKGROUND, tint, strength * .38))
        x = (x0 + x1) / 2
        self._segment(items[21], (x, top, z0 + .5),
            (x, top - min(4, block.height * .16) * growth, z0 + .5),
            T.blend(T.BACKGROUND, T.CORE, strength * .5))
        for item in items:
            self.cv.tag_raise(item)

    def _life(self, t):
        for i, items in enumerate(self.data):
            z = 70 + i * 29
            x = (-1 if i % 2 else 1) * (8 + i % 3 * 2)
            y = -((t * 4 + i * 3.7) % 24)
            strength = smooth((t - 37) / 3) * math.exp(-max(0, z - self.view.z) / 220) * .45
            self._glow(items, (x, y, z), (x, y - 1.7, z), strength, .7)
        for i, items in enumerate(self.cycles):
            x = ((t * (3 + i) + i * 19) % 70) - 35
            z = 155 + i * 35
            strength = smooth((t - 39) / 3) * .65
            self._glow(items, (x - 6, -.12, z), (x, -.12, z), strength,
                       1, T.ORANGE if i else T.CYAN)
        x, y, z = math.sin(t * .035) * 70, -60, 340
        shape = [(-10, 9), (-10, -2), (-7, -5), (7, -5), (10, -2),
                 (10, 9), (6, 9), (6, 0), (-6, 0), (-6, 9)]
        self._face(self.recognizer, [(x + a, y + b, z) for a, b in shape],
                   T.BACKGROUND, T.blend(T.GRID, T.SKY_HORIZON, .4))
        self._segment(self.recognizer_lamp, (x - 4, y - 2, z - .1),
            (x + 4, y - 2, z - .1), T.blend(T.BACKGROUND, T.ORANGE, .3))

    def render(self, t):
        self.view = world_camera(t, self.w, self.h)
        if not self.visible:
            for item in self.sky:
                self._style(item, state="normal")
            self.visible = True
        assembly = smooth((t - 35) / 7)
        self._face(
            self.ground,
            [(-300, 0, 0), (300, 0, 0), (300, 0, 580), (-300, 0, 580)],
            T.BACKGROUND,
        )
        # Reflexos são geometria espelhada no plano y=0, a 15% da luz.
        # O recorte da câmera impede que subam para o céu ao levantar o olhar.
        for index, (block, items) in enumerate(zip(self.blocks, self.reflections)):
            growth = smooth((t - block.delay) / block.duration)
            x0, x1, z0, z1 = block.bounds()
            top, base = -(block.base - block.height * growth), -block.base
            strength = growth * math.exp(-max(0, z0 - self.view.z) / 270) * .15
            if growth <= 0 or block.distant or self.view.z >= z0:
                for item in [*items, self.reflected_lights[index]]:
                    self._style(item, state="hidden")
                continue
            self._face(items[0], [(x0, base, z0), (x1, base, z0),
                (x1, top, z0), (x0, top, z0)],
                T.blend(T.BACKGROUND, T.ARMOR, strength))
            self._face(items[1], [(x0, top, z0), (x1, top, z0),
                (x1, top, z1), (x0, top, z1)],
                T.blend(T.BACKGROUND, T.SKY_HORIZON, strength))
            self._segment(self.reflected_lights[index], (x0, top, z0), (x1, top, z0),
                          T.blend(T.BACKGROUND, T.CYAN, strength))
        # A montagem avança do horizonte até a câmera e abre as linhas lateralmente.
        for i, item in enumerate(self.rows):
            z = (i + 1) * 8
            growth = smooth((t - (35 + 6 * (1 - i / 69))) / 1.3)
            if growth <= 0:
                self._style(item, state="hidden")
                continue
            span = 280 * growth
            color = T.blend(
                T.BACKGROUND, T.CYAN, growth * (0.04 + 0.16 * (1 - z / 570))
            )
            self._segment(item, (-span, 0, z), (span, 0, z), color)
        for i, item in enumerate(self.columns):
            x = (i - 26) * 8
            near = 560 * (1 - assembly)
            if assembly <= 0:
                self._style(item, state="hidden")
            else:
                self._segment(
                    item,
                    (x, 0, near),
                    (x, 0, 560),
                    T.blend(T.BACKGROUND, T.CYAN, 0.13 * assembly),
                )
        height = 70 * smooth((t - 39) / 5)
        for item, (color, width) in zip(self.beam, T.glow_layers(T.CYAN, 1.4)):
            if height > 0:
                self._segment(
                    item,
                    (0, 0, 500),
                    (0, -height, 500),
                    T.blend(T.BACKGROUND, color, 0.6),
                    width,
                )
                self.cv.tag_raise(item)

        # Superfícies voltadas à câmera, com recorte real no plano próximo.
        visible = []
        for index, (block, items) in enumerate(zip(self.blocks, self.faces)):
            growth = smooth((t - block.delay) / block.duration)
            if growth <= 0:
                for item in self.lights[index]:
                    self._style(item, state="hidden")
                continue
            x0, x1, z0, z1 = block.bounds()
            y1, y0 = block.base, block.base - block.height * growth
            definitions = (
                (
                    [(x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0)],
                    self.view.z < z0,
                    0.75,
                ),
                (
                    [(x1, y1, z1), (x0, y1, z1), (x0, y0, z1), (x1, y0, z1)],
                    self.view.z > z1,
                    0.55,
                ),
                (
                    [(x0, y1, z1), (x0, y1, z0), (x0, y0, z0), (x0, y0, z1)],
                    self.view.x < x0,
                    0.48,
                ),
                (
                    [(x1, y1, z0), (x1, y1, z1), (x1, y0, z1), (x1, y0, z0)],
                    self.view.x > x1,
                    0.62,
                ),
                (
                    [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)],
                    self.view.y < y0,
                    0.9,
                ),
                (
                    [(x0, y1, z1), (x1, y1, z1), (x1, y1, z0), (x0, y1, z0)],
                    self.view.y > y1,
                    0.4,
                ),
            )
            fog = min(0.9, max(0.0, (z0 - self.view.z) / 650))
            material = T.MOUNTAIN_FAR if block.distant else T.BIKE_ARMOR
            edge = T.blend(
                T.BACKGROUND, T.CYAN, (0.04 if block.distant else 0.10) * (1 - fog)
            )
            for item, (points, facing, shade) in zip(items, definitions):
                if facing:
                    camera_points = [self.view.transform(p) for p in points]
                    depth = sum(p[2] for p in camera_points) / 4
                    color = T.blend(T.blend(T.BACKGROUND, material, shade),
                                    T.blend(T.BACKGROUND, T.SKY_HORIZON, .30), fog)
                    visible.append((depth, item, camera_points, color, edge, index))
        visible.sort(key=lambda entry: entry[0], reverse=True)
        self.last_depths = [entry[0] for entry in visible]
        current = set()
        last_face = {entry[5]: i for i, entry in enumerate(visible)}
        for position, (depth, item, points, color, edge, index) in enumerate(visible):
            if self._camera_face(item, points, color, edge):
                current.add(item)
                self.cv.tag_raise(item)
            # Cada prédio recebe luz antes dos objetos mais próximos, sem raio X.
            if position == last_face[index]:
                block = self.blocks[index]
                growth = smooth((t - block.delay) / block.duration)
                self._building_lights(index, block, growth, t)
        for item in self.visible_faces - current:
            self._style(item, state="hidden")
        self.visible_faces = current
        self._life(t)
        return self.view

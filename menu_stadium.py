"""Arquibancada em perspectiva, plateia estática e uma pequena ola animada."""

from dataclasses import dataclass
import math
import random
import tkinter as tk

import backdrop
import theme as T


def crowd_row(p0, p1, n, occupancy=0.92, rng=None):
    """Lugares uniformes na tela; o tamanho acompanha o espaço disponível."""
    if n <= 0:
        return []
    rng = rng if rng is not None else random.Random(11)
    seat_w = math.dist(p0, p1) / n
    return [
        (
            p0[0] + (p1[0] - p0[0]) * (i + 0.5) / n,
            p0[1] + (p1[1] - p0[1]) * (i + 0.5) / n,
            seat_w * 0.90,
            i,
        )
        for i in range(n)
        if i % 12 not in (0, 11) and rng.random() < occupancy
    ]


@dataclass(frozen=True)
class Spectator:
    x: float
    y: float
    size: float
    color: str
    pose: int
    phase: float
    animated: bool
    row: int = 0


class StadiumScene:
    def __init__(self, canvas, project, width, height):
        self.cv, self.project, self.w, self.h = canvas, project, width, height
        front = .88 if height<680 else .91
        self.bounds = (width * 0.27, width * 0.73, height * 0.35, height * front)
        self.rows = 6
        self.rise, self.wall = height * 0.028, height * 0.045
        self.dx, self.dy = width * 0.021, height * 0.028
        self.people = self._people()
        self.active = []
        self.offsets = {}
        self.photo = None
        self.crowd_photos = []
        self.row_visibility = {}

    def _row_geometry(self):
        left, right, back, front = self.bounds
        for k in reversed(range(self.rows)):
            height = self.wall + k * self.rise
            yield self.project(left - k * self.dx, back - (k + 0.5) * self.dy, height)[
                :2
            ], self.project(right + k * self.dx, back - (k + 0.5) * self.dy, height)[
                :2
            ], 48
        for side, sign in ((left, -1), (right, 1)):
            for k in reversed(range(self.rows)):
                x = side + sign * (k + 0.5) * self.dx
                height = self.wall + k * self.rise
                yield self.project(x, back, height)[:2], self.project(x, front, height)[
                    :2
                ], 36

    def _people(self):
        rng = random.Random(71)
        people = []
        animated = 0
        for row, (p0, p1, n) in enumerate(self._row_geometry()):
            for x, y, size, index in crowd_row(p0, p1, n, rng=rng):
                color = rng.choices((T.CYAN, T.CORE, T.ORANGE), (0.72, 0.20, 0.08))[0]
                active = size >= 4 and rng.random() < 0.15 and animated < 64
                animated += active
                people.append(
                    Spectator(
                        x,
                        y,
                        size,
                        T.blend(color, T.BACKGROUND, rng.uniform(0.12, 0.48)),
                        rng.randrange(4),
                        row * 0.65 + index * 0.4,
                        active,
                        row,
                    )
                )
        return sorted(people, key=lambda p: p.y)

    def _polygon(self, cv, points, fill, outline=""):
        coords = [v for point in points for v in self.project(*point)[:2]]
        return cv.create_polygon(*coords, fill=fill, outline=outline, tags="bg")

    def _line(self, cv, points, fill=T.GRID_BRIGHT, width=1):
        coords = [v for point in points for v in self.project(*point)[:2]]
        return cv.create_line(*coords, fill=fill, width=width, tags="bg")

    def _structure(self, cv):
        left, right, back, front = self.bounds
        top = self.wall + (self.rows - 1) * self.rise
        self._polygon(
            cv,
            [(left, back, 0), (right, back, 0), (right, front, 0), (left, front, 0)],
            T.ASPHALT[0],
            T.GRID_BRIGHT,
        )
        for i in range(1, 13):
            x = left + (right - left) * i / 13
            self._line(cv, [(x, back, 0), (x, front, 0)], T.GRID)
        for i in range(1, 10):
            y = back + (front - back) * i / 10
            self._line(cv, [(left, y, 0), (right, y, 0)], T.GRID)
        # Parede de fundo, painéis verticais e faixa superior de luz.
        xa, xb = left - self.rows * self.dx, right + self.rows * self.dx
        yy = back - self.rows * self.dy
        self._polygon(
            cv,
            [
                (xa, yy, top),
                (xb, yy, top),
                (xb, yy, top + self.h * 0.08),
                (xa, yy, top + self.h * 0.08),
            ],
            T.ARMOR,
            T.GRID_BRIGHT,
        )
        self._line(
            cv, [(xa, yy, top + self.h * 0.08), (xb, yy, top + self.h * 0.08)], T.CYAN
        )
        for i in range(17):
            x = xa + (xb - xa) * i / 16
            self._line(cv, [(x, yy, top), (x, yy, top + self.h * 0.073)])
        # Cada degrau possui assento, espelho frontal e iluminação própria.
        for k in reversed(range(self.rows)):
            hi = self.wall + k * self.rise
            lo = self.wall + (k - 1) * self.rise if k else 0
            yin, yout = back - k * self.dy, back - (k + 1) * self.dy
            a, b = left - k * self.dx, right + k * self.dx
            self._polygon(
                cv,
                [
                    (a - self.dx, yout, hi),
                    (b + self.dx, yout, hi),
                    (b, yin, hi),
                    (a, yin, hi),
                ],
                T.ARMOR,
            )
            self._polygon(
                cv, [(a, yin, lo), (b, yin, lo), (b, yin, hi), (a, yin, hi)], T.SHELL
            )
            self._line(
                cv, [(a, yin, hi), (b, yin, hi)], T.CYAN if k == 0 else T.GRID_BRIGHT
            )
        for side, sign in ((left, -1), (right, 1)):
            for k in reversed(range(self.rows)):
                xin, xout = side + sign * k * self.dx, side + sign * (k + 1) * self.dx
                hi = self.wall + k * self.rise
                lo = self.wall + (k - 1) * self.rise if k else 0
                self._polygon(
                    cv,
                    [
                        (xout, back, hi),
                        (xout, front, hi),
                        (xin, front, hi),
                        (xin, back, hi),
                    ],
                    T.ARMOR,
                )
                self._polygon(
                    cv,
                    [
                        (xin, back, lo),
                        (xin, front, lo),
                        (xin, front, hi),
                        (xin, back, hi),
                    ],
                    T.SHELL,
                )
                self._line(
                    cv,
                    [(xin, back, hi), (xin, front, hi)],
                    T.CYAN if k == 0 else T.GRID_BRIGHT,
                )
                # Corredores de escada a cada doze lugares, com três pequenos passos.
                for aisle in (0, 12, 24, 36):
                    y = back + (front - back) * aisle / 36
                    for step in range(3):
                        xx = xin + (xout - xin) * step / 3
                        self._line(
                            cv,
                            [
                                (xx, y, lo + (hi - lo) * step / 3),
                                (xx, y + self.h * 0.006, lo + (hi - lo) * step / 3),
                            ],
                            T.MUTED,
                        )
            # Corrimão no topo e postes de apoio.
            outer = side + sign * self.rows * self.dx
            self._line(cv, [(outer, back, top + 18), (outer, front, top + 18)], T.MUTED)
            for i in range(9):
                y = back + (front - back) * i / 8
                self._line(cv, [(outer, y, top), (outer, y, top + 18)])
            # Perfil do corte frontal deixa visível a profundidade dos degraus.
            profile = [(side, front, 0)]
            for k in range(self.rows):
                hh = self.wall + k * self.rise
                profile += [
                    (side + sign * k * self.dx, front, hh),
                    (side + sign * (k + 1) * self.dx, front, hh),
                ]
            profile.append((outer, front, 0))
            self._polygon(cv, profile, T.SHELL, T.GRID_BRIGHT)
        # Proteção de vidro da arena, sem uma parede opaca sobre a disputa.
        for i in range(13):
            x = left + (right - left) * i / 12
            self._line(cv, [(x, front, 0), (x, front, self.wall)], T.GRID_BRIGHT)
        self._line(cv, [(left, front, self.wall), (right, front, self.wall)], T.CYAN)
        self._line(cv, [(left, front, 0), (right, front, 0)], T.GRID_BRIGHT)
        # Torres de refletores nas extremidades do fundo.
        for x in (xa, xb):
            foot = self.project(x, yy, top)
            head = self.project(x, yy, top + self.h * 0.18)
            cv.create_line(
                foot[0], foot[1], head[0], head[1], fill=T.METAL, width=3, tags="bg"
            )
            for i in (-1, 0, 1):
                xx = head[0] + i * self.w * 0.008
                cv.create_rectangle(
                    xx - 3,
                    head[1] - 2,
                    xx + 3,
                    head[1] + 2,
                    fill=T.CORE,
                    outline="",
                    tags="bg",
                )

    @staticmethod
    def person(cv, person, tags="bg"):
        x, y, s = person.x, person.y, person.size
        # Assento e corpo são escuros; só os circuitos emitem luz.
        if s < 4:
            cv.create_rectangle(
                x - max(.5,s*.18),
                y - max(1,s*.65),
                x + max(.5,s*.18),
                y - s*.35,
                fill=T.blend(person.color,T.BACKGROUND,.45),
                outline="",
                tags=tags,
            )
            return
        cv.create_polygon(
            x - s * 0.34,
            y - s * 0.20,
            x - s * 0.28,
            y - s * 1.08,
            x,
            y - s * 1.23,
            x + s * 0.28,
            y - s * 1.08,
            x + s * 0.34,
            y - s * 0.2,
            fill=T.SUIT_HIGHLIGHT,
            outline="",
            tags=tags,
        )
        cv.create_oval(
            x - s * 0.17,
            y - s * 1.65,
            x + s * 0.17,
            y - s * 1.28,
            fill=T.METAL,
            outline="",
            tags=tags,
        )
        cv.create_line(
            x - s * 0.20,
            y - s * 1.02,
            x,
            y - s * 0.88,
            x + s * 0.20,
            y - s * 1.02,
            fill=person.color,
            width=max(1, s * 0.055),
            tags=tags,
        )
        if person.pose in (1, 2, 3):
            raised = person.pose in (2, 3)
            cv.create_line(
                x - s * 0.23,
                y - s * 0.99,
                x - s * 0.43,
                y - s * (1.60 if raised else 0.65),
                fill=T.METAL,
                width=max(1, s * 0.10),
                tags=tags,
            )
        if person.pose in (0, 2, 3):
            cv.create_line(
                x + s * 0.23,
                y - s * 0.99,
                x + s * 0.43,
                y - s * (1.52 if person.pose == 3 else 0.62),
                fill=T.METAL,
                width=max(1, s * 0.10),
                tags=tags,
            )

    def _paint(self, cv, omit_active=False, population=True):
        self._structure(cv)
        for person in self.people:
            x, y, s = person.x, person.y, person.size
            cv.create_rectangle(
                x - s * 0.37,
                y - s * 0.25,
                x + s * 0.37,
                y + s * 0.12,
                fill=T.GLASS,
                outline="",
                tags="bg",
            )
            if population and not (omit_active and person.animated):
                self.person(cv, person, ("bg", f"crowd_row_{person.row % self.rows}"))

    def draw(self, live=True, crowd=True, under=None):
        """`under`: PilCanvas já pintado com o resto do fundo; o estádio é pintado por cima."""
        cv = self.cv
        if live and backdrop.AVAILABLE and isinstance(cv, tk.Canvas):
            if under is not None:
                self._paint(under, True, False)
                base = under.img
            else:
                base = backdrop.snapshot(
                    lambda pc: self._paint(pc, True, False), self.w, self.h, None, scale=1.0
                )
            self.photo = backdrop.to_photo(cv, base)
            cv.create_image(
                0, 0, image=self.photo, anchor="nw", tags=("bg", "stadium_static")
            )
            if crowd:
                for row in range(self.rows):
                    def paint(pc, row=row):
                        for person in self.people:
                            if not person.animated and person.row % self.rows == row:
                                self.person(pc, person)
                    image = backdrop.snapshot(paint, self.w, self.h, None, scale=1.0)
                    box = image.getbbox()
                    if box:
                        photo = backdrop.to_photo(cv, image.crop(box))
                        self.crowd_photos.append(photo)
                        cv.create_image(box[0],box[1],image=photo,anchor="nw",
                                        tags=("bg",f"crowd_row_{row}"))
        else:
            self._paint(cv, omit_active=live, population=crowd)
        if live and crowd:
            for i, person in enumerate(p for p in self.people if p.animated):
                tag = f"crowd_active_{i}"
                self.person(cv, person, ("bg", tag, f"crowd_row_{person.row % self.rows}"))
                self.active.append((tag, person))
                self.offsets[tag] = 0.0

    def reveal(self, age):
        """Acende seis ondas da plateia; os bitmaps já estão prontos."""
        for row in range(self.rows):
            visible = age >= row * .16
            if self.row_visibility.get(row) != visible:
                self.cv.itemconfig(f"crowd_row_{row}",state="normal" if visible else "hidden")
                self.row_visibility[row] = visible

    def animate(self, time):
        for tag, person in self.active:
            wave = max(0.0, math.sin(time * 3 - person.phase) - 0.25)
            offset = -wave * min(7, person.size * 0.30)
            self.cv.move(tag, 0, offset - self.offsets[tag])
            self.offsets[tag] = offset

"""Disputa de demonstração: passo fixo, motos visíveis e rastros que colidem."""

from collections import deque
from dataclasses import dataclass, field
import math
import random

from chase_mode import CanvasPool
from sprites_topview import draw_bike, move_bike
import theme as T

DIRECTIONS = ((1, 0), (0, 1), (-1, 0), (0, -1))


@dataclass
class DemoBike:
    cell: tuple
    direction: tuple
    model: int
    color: str
    alive: bool = True
    previous: tuple = None
    trail: list = field(default_factory=list)
    crashed_at: float = -10.0


class AttractSimulation:
    width, height = 34, 26
    step = 0.085

    def __init__(self):
        self.time = self.accumulator = 0.0
        self.round = 0
        self.restart_at = None
        self.reset()

    def reset(self):
        self.round += 1
        self.rng = random.Random(70 + self.round)
        starts = [
            ((3, 19), (1, 0), 0, T.CYAN),
            ((30, 8), (-1, 0), 1, T.ORANGE),
            ((17, 3), (0, 1), 3, T.CORE),
        ]
        self.bikes = []
        self.occupied = set()
        for cell, direction, model, color in starts:
            if self.round % 2 == 0:
                cell = (self.width - 1 - cell[0], self.height - 1 - cell[1])
                direction = (-direction[0], -direction[1])
            bike = DemoBike(cell, direction, model, color, previous=cell, trail=[cell])
            self.bikes.append(bike)
            self.occupied.add(cell)
        self.restart_at = None

    def free(self, cell):
        x, y = cell
        return (
            0 <= x < self.width and 0 <= y < self.height and cell not in self.occupied
        )

    def _area(self, start):
        seen = {start}
        queue = deque([start])
        while queue and len(seen) < 96:
            x, y = queue.popleft()
            for dx, dy in DIRECTIONS:
                cell = (x + dx, y + dy)
                if cell not in seen and self.free(cell):
                    seen.add(cell)
                    queue.append(cell)
        return len(seen)

    def choose(self, bike):
        candidates = []
        x, y = bike.cell
        for dx, dy in DIRECTIONS:
            if (dx, dy) == (-bike.direction[0], -bike.direction[1]):
                continue
            target = (x + dx, y + dy)
            if not self.free(target):
                continue
            ahead = 0
            for distance in range(1, 10):
                if not self.free((x + dx * distance, y + dy * distance)):
                    break
                ahead += 1
            rivals = [
                other for other in self.bikes if other is not bike and other.alive
            ]
            proximity = min(
                (
                    abs(target[0] - other.cell[0]) + abs(target[1] - other.cell[1])
                    for other in rivals
                ),
                default=0,
            )
            score = (
                self._area(target) * 0.18
                + min(ahead, 6)
                + 3 * ((dx, dy) == bike.direction)
                - proximity * 0.06
            )
            # Alterna fuga e interceptação; a previsão dá curvas longas e tentativas de corte.
            if rivals and int(self.time / 2.4 + bike.model) % 3:
                rival = rivals[bike.model % len(rivals)]
                tx = rival.cell[0] + rival.direction[0] * 5
                ty = rival.cell[1] + rival.direction[1] * 5
                before = abs(x - tx) + abs(y - ty)
                after = abs(target[0] - tx) + abs(target[1] - ty)
                score += (before - after) * 3.2
            candidates.append((score + self.rng.random() * 0.12, (dx, dy)))
        return max(candidates)[1] if candidates else bike.direction

    def advance(self, elapsed):
        self.accumulator += max(0.0, min(0.25, elapsed))
        while self.accumulator + 1e-10 >= self.step:
            self.accumulator -= self.step
            self.time += self.step
            if self.restart_at is not None:
                if self.time >= self.restart_at:
                    self.reset()
                continue
            plans = []
            for bike in self.bikes:
                if not bike.alive:
                    continue
                direction = self.choose(bike)
                target = (bike.cell[0] + direction[0], bike.cell[1] + direction[1])
                plans.append((bike, direction, target))
            for bike, direction, target in plans:
                bike.previous = bike.cell
                bike.direction = direction
                if not self.free(target) or sum(p[2] == target for p in plans) > 1:
                    bike.alive = False
                    bike.crashed_at = self.time
            for bike, _, target in plans:
                if bike.alive:
                    bike.cell = target
                    bike.trail.append(target)
                    self.occupied.add(target)
            if sum(bike.alive for bike in self.bikes) <= 1:
                self.restart_at = self.time + 1.7


def corners(points):
    if len(points) < 3:
        return points
    result = [points[0]]
    for a, b, c in zip(points, points[1:], points[2:]):
        if (b[0] - a[0], b[1] - a[1]) != (c[0] - b[0], c[1] - b[1]):
            result.append(b)
    return result + [points[-1]]


class MenuRace:
    def __init__(self, canvas, project, bounds, width, height):
        self.cv, self.project, self.bounds = canvas, project, bounds
        self.w, self.h = width, height
        self.sim = AttractSimulation()
        self.pool = CanvasPool(canvas)
        self.items = [
            draw_bike(
                canvas,
                0,
                0,
                (1, 0),
                bike.color,
                bike.model,
                0.7,
                tags=("bg", "menu_race"),
            )
            for bike in self.sim.bikes
        ]
        self.tags = ("bg", "menu_race")
        self.render()

    def world(self, cell):
        left, right, back, front = self.bounds
        return (
            left + 24 + (right - left - 48) * (cell[0] + 0.5) / self.sim.width,
            back + 20 + (front - back - 40) * (cell[1] + 0.5) / self.sim.height,
        )

    def advance(self, elapsed):
        self.sim.advance(elapsed)
        self.render()

    def render(self):
        p = self.pool
        p.begin()
        segments = []
        heads = []
        alpha = min(1.0, max(0.0, self.sim.accumulator / self.sim.step))
        if self.sim.restart_at is not None:
            alpha = 1.0
        for bike, items in zip(self.sim.bikes, self.items):
            hx = bike.previous[0] + (bike.cell[0] - bike.previous[0]) * alpha
            hy = bike.previous[1] + (bike.cell[1] - bike.previous[1]) * alpha
            path = corners(bike.trail[-180:])
            if path:
                path = path[:-1] + [(hx, hy)]
            for a, b in zip(path, path[1:]):
                wa, wb = self.world(a), self.world(b)
                segments.append(((wa[1] + wb[1]) / 2, wa, wb, bike.color))
            wx, wy = self.world((hx, hy))
            heads.append((wy, wx, bike, items))
        for _, a, b, color in sorted(segments, key=lambda s: s[0]):
            low_a, low_b = self.project(*a), self.project(*b)
            high_a, high_b = self.project(*a, self.h * 0.022), self.project(
                *b, self.h * 0.022
            )
            p.polygon(
                (*low_a[:2], *low_b[:2], *high_b[:2], *high_a[:2]),
                fill=T.blend(color, T.BACKGROUND, 0.87),
                tags=self.tags,
            )
            T.neon_line(
                p,
                (*high_a[:2], *high_b[:2]),
                color,
                max(0.5, 1.8 / low_b[2]),
                tags=self.tags,
            )
            p.line(
                (*low_a[:2], *low_b[:2]),
                fill=T.blend(color, T.BACKGROUND, 0.55),
                width=1,
                tags=self.tags,
            )
        for wy, wx, bike, items in sorted(heads, key=lambda head: head[0]):
            x, y, z = self.project(wx, wy, self.h * 0.006)
            if bike.alive:
                dx, dy = bike.direction
                ahead = self.project(wx + dx * 5, wy + dy * 5, self.h * 0.006)
                length = math.hypot(ahead[0] - x, ahead[1] - y) or 1
                direction = ((ahead[0] - x) / length, (ahead[1] - y) / length)
                for item in items:
                    self.cv.itemconfigure(item, state="normal")
                size = round(max(0.65, 3.4 / z) * 10) / 10
                move_bike(
                    self.cv,
                    items,
                    bike.model,
                    x,
                    y,
                    direction,
                    size,
                    elapsed=self.sim.time + self.sim.accumulator,
                )
            else:
                for item in items:
                    self.cv.itemconfigure(item, state="hidden")
                age = self.sim.time - bike.crashed_at
                if age < 0.65:
                    flare = max(0, 1 - age / 0.18)
                    if flare:
                        radius = (6 + age * 140) / z
                        p.polygon(
                            tuple(
                                v
                                for i in range(16)
                                for v in (
                                    x + math.cos(i * math.tau / 16) * radius,
                                    y + math.sin(i * math.tau / 16) * radius * 0.65,
                                )
                            ),
                            fill=T.blend(T.BACKGROUND, T.CORE, flare),
                            tags=self.tags,
                        )
                    for i in range(12):
                        angle = i * math.tau / 12
                        radius = (4 + age * 90) / z
                        px, py = (
                            x + math.cos(angle) * radius,
                            y + math.sin(angle) * radius,
                        )
                        p.rect(
                            (px - 2, py - 2, px + 2, py + 2),
                            fill=T.blend(bike.color, T.BACKGROUND, age / 0.65),
                            tags=self.tags,
                        )
        p.end()
        for _, _, bike, items in heads:
            if bike.alive:
                for item in items:
                    self.cv.tag_raise(item)

    def restore_visibility(self):
        # Desfazer o desfoque restaura a tag bg inteira; reoculta itens do pool inativos.
        self.pool.hidden.clear()

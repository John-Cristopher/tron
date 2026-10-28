"""Estádio do menu e a imagem usada como destino do portal da introdução."""

from functools import lru_cache
import math
import random
import tkinter as tk

import backdrop
from menu_stadium import StadiumScene
from menu_race import MenuRace, AttractSimulation, corners
from sprites_topview import render_top
import theme as T
import ui


def title_boxes(w, h):
    width = min(320, w * 0.27)
    height = 56 if h >= 700 else 48
    x = max(24, w * 0.06)
    y = h * 0.31
    return [
        (x, y + i * (height + 8), x + width, y + i * (height + 8) + height)
        for i in range(4)
    ]


def brand_box(w, h):
    return (w * 0.09, h * 0.045, w * 0.72, h * 0.205)


class MenuScene:
    def __init__(self, canvas, width, height, live=True, crowd=True):
        self.cv, self.w, self.h = canvas, width, height
        self.photo = None
        self.live = live
        self.crowd = crowd
        self.draw()

    def project(self, x, y, h=0):
        z = 1 + 5 * (1 - y / self.h)
        return (
            self.w * 0.58 + (x - self.w * 0.5) * 2.05 / z,
            self.h * 0.36 + (self.h * 0.64 - h) / z,
            z,
        )

    def _line(self, cv, points, fill, width=1):
        cv.create_line(
            *[v for p in points for v in self.project(*p)[:2]],
            fill=fill,
            width=width,
            tags="bg"
        )

    def block(self, cv, x0, x1, y0, y1, height, seed):
        def poly(points, fill, edge=T.GRID):
            cv.create_polygon(
                *[v for p in points for v in self.project(*p)[:2]],
                fill=fill,
                outline=edge,
                tags="bg"
            )

        for side in (x0, x1):
            poly(
                [(side, y0, 0), (side, y1, 0), (side, y1, height), (side, y0, height)],
                T.SHELL,
            )
        poly(
            [(x0, y0, height), (x1, y0, height), (x1, y1, height), (x0, y1, height)],
            T.ARMOR,
        )
        poly(
            [(x0, y1, 0), (x1, y1, 0), (x1, y1, height), (x0, y1, height)],
            T.SUIT_HIGHLIGHT,
        )
        for x in (x0, x1):
            self._line(
                cv,
                [(x, y1, 0), (x, y1, height)],
                T.blend(T.CYAN, T.BACKGROUND, 0.58),
                2,
            )
        self._line(cv, [(x0, y1, height), (x1, y1, height)], T.GRID_BRIGHT, 2)
        rng = random.Random(seed)
        for row in range(8):
            bottom = height * (row + 0.12) / 8
            top = height * (row + 0.42) / 8
            for column in range(4):
                if rng.random() < 0.28:
                    continue
                a = x0 + (x1 - x0) * (column + 0.18) / 4
                b = x0 + (x1 - x0) * (column + 0.68) / 4
                poly(
                    [(a, y1, bottom), (b, y1, bottom), (b, y1, top), (a, y1, top)],
                    T.blend(T.CYAN, T.BACKGROUND, rng.uniform(0.65, 0.9)),
                    "",
                )

    def draw(self):
        w, h = self.w, self.h
        # Fundo estático vira uma imagem só: ~1000 itens vetoriais custavam ~8 ms por frame no Tk
        bake = self.live and backdrop.AVAILABLE and isinstance(self.cv, tk.Canvas)
        cv = backdrop.PilCanvas(w, h, 1, T.BACKGROUND) if bake else self.cv
        for i in range(16):
            cv.create_rectangle(
                0,
                i * h * 0.5 / 16,
                w,
                (i + 1) * h * 0.5 / 16 + 1,
                fill=T.blend(T.BACKGROUND, T.SKY_HORIZON, (i / 15) ** 2 * 0.55),
                outline="",
                tags="bg",
            )
        cv.create_rectangle(0, h * 0.48, w, h, fill=T.BACKGROUND, outline="", tags="bg")
        # Um único trecho do feixe começa abaixo do logo; não há segmento solto no topo.
        self.beam = []
        for color, width in T.glow_layers(T.CYAN, 2):
            self.beam.append(
                cv.create_line(
                    w * 0.58,
                    h * 0.27,
                    w * 0.58,
                    h * 0.50,
                    fill=color,
                    width=width,
                    tags="bg",
                )
            )
        for i in range(-20, 21):
            self._line(
                cv, [(w * 0.5 + i * w / 14, 0), (w * 0.5 + i * w / 14, h)], T.GRID
            )
        for i in range(22):
            yy = i * h / 21
            sy = self.project(0, yy)[1]
            cv.create_line(
                0, sy, w, sy, fill=T.blend(T.GRID, T.GRID_BRIGHT, i / 42), tags="bg"
            )
        rng = random.Random(27)
        buildings = []
        for side in (-1, 1):
            for i in range(6):
                y = h * (0.06 + i * 0.12)
                z = self.project(0, y)[2]
                x = w * 0.5 + side * w * (0.42 if side < 0 else 0.32) * z / 2.05
                width = w * rng.uniform(0.035, 0.055) * z / 2.05
                buildings.append(
                    (
                        x - width / 2,
                        x + width / 2,
                        y,
                        y + h * 0.04,
                        rng.uniform(0.14, 0.32) * h * z,
                        i + (side + 1) * 30,
                    )
                )
        for block in sorted(buildings, key=lambda p: p[2]):
            self.block(cv, *block)
        self.stadium = StadiumScene(self.cv, self.project, w, h)
        self.stadium.draw(self.live, self.crowd, under=cv if bake else None)
        cv = self.cv
        if self.live:
            self.race = MenuRace(cv, self.project, self.stadium.bounds, w, h)
            for _ in range(240):
                self.race.sim.advance(1 / 60)
            self.race.render()
        else:
            self.paint_race(cv)

    def paint_race(self, cv):
        sim = AttractSimulation()
        for _ in range(240):
            sim.advance(1 / 60)
        left, right, back, front = self.stadium.bounds

        def world(cell):
            return (
                left + 24 + (right - left - 48) * (cell[0] + 0.5) / sim.width,
                back + 20 + (front - back - 40) * (cell[1] + 0.5) / sim.height,
            )

        for bike in sim.bikes:
            for a, b in zip(corners(bike.trail), corners(bike.trail)[1:]):
                a, b = world(a), world(b)
                self._line(
                    cv,
                    [(a[0], a[1], self.h * 0.022), (b[0], b[1], self.h * 0.022)],
                    bike.color,
                    2,
                )
            wx, wy = world(bike.previous)
            x, y, z = self.project(wx, wy, self.h * 0.006)
            dx, dy = bike.direction
            ahead = self.project(wx + dx * 5, wy + dy * 5, self.h * 0.006)
            direction = round(math.atan2(ahead[1] - y, ahead[0] - x) * 8 / math.tau) % 8
            size = round(max(0.65, 3.4 / z) * 10) / 10
            image = render_top(bike.model, bike.color, size * cv.scale, direction)
            cv.img.paste(
                image,
                (
                    round(x * cv.scale - image.width / 2),
                    round(y * cv.scale - image.height / 2),
                ),
                image,
            )


@lru_cache(maxsize=6)
def menu_snapshot(width, height, interface=True):
    if not backdrop.AVAILABLE:
        return None
    canvas = backdrop.PilCanvas(width, height, 1, T.BACKGROUND)
    MenuScene(canvas, width, height, live=False, crowd=interface)
    if not interface:
        return canvas.img.convert("RGBA")
    ui.TubeLogo(canvas, brand_box(width, height))
    canvas.create_line(
        width * 0.2, height * 0.225, width * 0.61, height * 0.225, fill=T.GRID_BRIGHT
    )
    ui.text(
        canvas,
        width * 0.405,
        height * 0.255,
        "LIGHT CYCLE ULTIMATE",
        14,
        T.CORE,
        "center",
        "title",
    )
    ui.IdentityDisc(canvas, width * 0.90, height * 0.13, min(54, height * 0.065))
    labels = ("ARENA CLÁSSICA", "PERSEGUIÇÃO", "OPÇÕES", "SAIR")
    for i, (box, label) in enumerate(zip(title_boxes(width, height), labels)):
        ui.Button(canvas, str(i), box, label, size=16, selected=i == 0)
        if i == 0:
            ui.corners(canvas, (box[0] - 4, box[1] - 4, box[2] + 4, box[3] + 4))
    ui.text(
        canvas,
        width * 0.62,
        height * 0.43,
        "ARENA AO VIVO  /  3 PILOTOS",
        12,
        T.MUTED,
        "center",
    )
    ui.text(
        canvas,
        width / 2,
        height - 76,
        "i  Configure uma partida na arena.",
        14,
        T.CORE,
        "center",
    )
    ui.keycaps(
        canvas,
        width / 2,
        height - 32,
        [("↑ ↓", "escolher"), ("ENTER", "confirmar"), ("ESC", "sair")],
        12,
    )
    ui.text(canvas, width - 24, height - 8, "v" + T.VERSION, 10, T.MUTED, "se")
    return canvas.img.convert("RGBA")

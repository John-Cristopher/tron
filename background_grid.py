"""Cenário estático em camadas; só coordenadas e partículas mudam por quadro."""

import math
import random
import tkinter as tk

import theme as T


class GridBackground:
    def __init__(self, canvas, width, height):
        self.w, self.h = width, height
        self.images = []
        self.vignette = None
        if T.Image is not None and isinstance(canvas, tk.Canvas):
            self._prerender(canvas)

    def _prerender(self, canvas):
        w, h = self.w, self.h
        horizon = round(h * 0.4)
        sky = T.Image.new("RGB", (w, horizon + 55), T.BACKGROUND)
        draw = T.ImageDraw.Draw(sky)
        for y in range(sky.height):
            t = min(1, y / max(1, horizon))
            draw.line((0, y, w, y), fill=T.blend(T.BACKGROUND, T.SKY_HORIZON, t * t))
        self.sky = T.ImageTk.PhotoImage(sky, master=canvas)
        for layer, color in enumerate((T.MOUNTAIN_FAR, T.MOUNTAIN_NEAR)):
            tile = T.Image.new("RGBA", (w, horizon + 55))
            draw = T.ImageDraw.Draw(tile)
            count = 20
            peaks = [
                horizon
                - h
                * (
                    0.025
                    + (math.sin(i * 7.17 + layer * 2) * 0.5 + 0.5)
                    * (0.13 if layer == 0 else 0.085)
                )
                for i in range(count)
            ]
            peaks.append(peaks[0])
            points = [(i * w / count, y) for i, y in enumerate(peaks)]
            draw.polygon([(0, horizon + 55)] + points + [(w, horizon + 55)], fill=color)
            # Facetas apagadas dão volume sem competir com a pista.
            for i in range(0, count, 3):
                x, y = points[i]
                draw.polygon(
                    [
                        (x, y),
                        (x + w * 0.035, horizon + 35),
                        (x - w * 0.025, horizon + 35),
                    ],
                    fill=T.blend(color, T.GRID, 0.22),
                )
            self.images.append(self._repeat(tile, canvas))
        # Três skylines com silhuetas escalonadas, antenas e janelas pré-renderizadas.
        rng = random.Random(2718)
        for layer in range(3):
            tile = T.Image.new("RGBA", (w, horizon + 55))
            draw = T.ImageDraw.Draw(tile)
            count = 28 - layer * 5
            for i in range(count):
                x = round(i * w / count)
                bw = max(5, round(w * rng.uniform(.008, .025)))
                top = horizon - round(h * rng.uniform(.018, .065 + layer * .025))
                color = T.blend(T.MOUNTAIN_FAR, T.TOWER, .25 + layer * .25)
                step = max(3, bw // 4)
                shape = [(x, horizon + 12), (x, top + step), (x + step, top + step),
                         (x + step, top), (x + bw - step, top), (x + bw - step, top + step),
                         (x + bw, top + step), (x + bw, horizon + 12)]
                draw.polygon(shape, fill=color)
                draw.line((x, top + step, x, horizon + 8), fill=T.GRID_BRIGHT)
                if i % 3 == 0:
                    draw.line((x + bw // 2, top, x + bw // 2, top - 8), fill=T.MUTED)
                for yy in range(top + step + 5, horizon, 7):
                    for xx in range(x + 3, x + bw - 2, 5):
                        if rng.random() < .35:
                            draw.point((xx, yy), fill=T.blend(T.GRID_BRIGHT, T.CYAN, .12 + .08 * layer))
            self.images.append(self._repeat(tile, canvas))
        # Vinheta em baixa resolução ampliada uma vez; centro totalmente livre.
        mask = T.Image.new("RGBA", (128, 72))
        pixels = mask.load()
        for y in range(72):
            for x in range(128):
                radius = ((x - 63.5) / 67) ** 2 + ((y - 35.5) / 40) ** 2
                pixels[x, y] = (
                    *T.rgb(T.BACKGROUND),
                    round(min(135, max(0, (radius - 0.45) * 100))),
                )
        self.vignette = T.ImageTk.PhotoImage(
            mask.resize((w, h), T.RESAMPLE.BILINEAR), master=canvas
        )

    def _repeat(self, tile, canvas):
        wide = T.Image.new("RGBA", (tile.width * 2, tile.height))
        wide.paste(tile, (0, 0))
        wide.paste(tile, (tile.width, 0))
        return T.ImageTk.PhotoImage(wide, master=canvas)

    def draw(self, p, sim):
        w, h = self.w, self.h
        horizon = h * 0.4
        p.rect((0, 0, w, h), fill=T.BACKGROUND)
        heading = sim.road.heading(sim.player.s)
        if self.images:
            p.image(0, 0, image=self.sky, anchor="nw")
            for photo, speed in zip(self.images, (0.18, 0.42, 0.12, 0.24, 0.38)):
                shift = (heading * w * speed * 4 + sim.player.x * speed * 18) % w
                p.image(-shift, 0, image=photo, anchor="nw")
        else:
            for i in range(12):
                p.rect(
                    (0, i * horizon / 12, w, (i + 1) * horizon / 12 + 1),
                    fill=T.blend(T.BACKGROUND, T.SKY_HORIZON, i / 11),
                )
            for layer, color in enumerate((T.MOUNTAIN_FAR, T.MOUNTAIN_NEAR)):
                points = [-w, horizon + 40]
                for i in range(-2, 24):
                    points += [
                        i * w / 20 - heading * w * (layer + 1) * 0.3,
                        horizon - h * (0.03 + 0.08 * abs(math.sin(i * 7.17 + layer))),
                    ]
                p.polygon(points + [2 * w, horizon + 40], fill=color)
        # Recognizer distante, em silhueta; a grade fica no RoadRenderer.
        rx = ((sim.time * w * .006 + w * .22) % (w * 1.3)) - w * .15
        ry = h * .19 + math.sin(sim.time * .06) * h * .012
        span = w * .027
        coords = (rx - span, ry + span, rx - span, ry - span * .35,
                  rx - span * .75, ry - span * .65, rx + span * .75, ry - span * .65,
                  rx + span, ry - span * .35, rx + span, ry + span,
                  rx + span * .62, ry + span, rx + span * .62, ry,
                  rx - span * .62, ry, rx - span * .62, ry + span)
        p.polygon(coords, fill=T.SHELL, outline=T.GRID_BRIGHT, width=1)
        p.line((rx - span * .4, ry - span * .26, rx + span * .4, ry - span * .26),
               fill=T.blend(T.ORANGE, T.GRID, .7), width=1)
        # Deterministas: pausar também congela as partículas e o parallax.
        for i in range(32):
            x = ((i * 0.6180339) % 1 * w - heading * w * 0.08) % w
            y = horizon + 35 - (i * 37 + sim.time * (5 + i % 5)) % (horizon + 30)
            length = 1 + i % 3
            p.rect((x, y, x + 1, y + length), fill=T.GRID_BRIGHT if i % 4 else T.MUTED)

    def finish(self, p):
        if self.vignette:
            p.image(0, 0, image=self.vignette, anchor="nw")

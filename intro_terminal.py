"""CLI âmbar e digitalização progressiva, dirigidos pelo relógio da introdução."""

import math
import tkinter as tk
from tkinter import font as tkfont

import theme as T

REZ_START = 34.0
REZ_END = 36.8
AMBER = "#E7B679"
PANEL = "#080807"


class Terminal:
    def __init__(self, canvas, width, height):
        self.cv, self.w, self.h = canvas, width, height
        self.items, self.styles = [], {}
        self.visible = True
        self.left, self.right = width * .055, width * .945
        self.top, self.bottom = height * .09, height * .86
        self.text_y = self.top + max(58, height * .095)
        self.size = max(10, min(22, round(height / 34),
                        int((self.right-self.left-48)/(54*.8))))
        self.line_height = self.size * 1.6
        if isinstance(canvas, tk.Canvas):
            self.line_height = tkfont.Font(root=canvas, font=(T.FONT, self.size)).metrics("linespace")
        self.panel = self._create("rectangle", self.left, self.top, self.right, self.bottom,
                                  fill=PANEL, outline=T.blend(T.BACKGROUND, AMBER, .3))
        self.header = self._text(self.left + 22, self.top + 23, "ENCOM / ARCHIVE 1982", 11)
        self.status = self._text(self.left + 22, self.bottom - 21,
                                  "ENCOM OS  //  FLYNN ARCHIVE", 10)
        self.prompt = self._text(self.right - 22, self.bottom - 21, "LINK / STANDBY", 10, "e")
        self.glow = self._text(self.left + 25, self.text_y + 1, "", self.size, "nw")
        self.term = self._text(self.left + 24, self.text_y, "", self.size, "nw")
        self.scanlines = []
        for y in range(round(self.top + 40), round(self.bottom - 40), 4):
            self.scanlines.append((self._create("line", self.left + 2, y, self.right - 2, y,
                                               fill=T.blend(PANEL, T.BACKGROUND, .25), width=1), y))
        self.beam = [self._create("line", 0, 0, 0, 0, fill=color, width=weight, state="hidden")
                     for color, weight in T.glow_layers(T.CYAN, 2)]
        self.cubes = [self._create("polygon", 0, 0, 0, 0, 0, 0,
                     fill=T.BACKGROUND, outline=T.CYAN, state="hidden") for _ in range(96)]
        self.rez_visible = False

    def _create(self, kind, *coords, **options):
        item = getattr(self.cv, "create_" + kind)(*coords, tags="intro", **options)
        self.items.append(item)
        self.styles[item] = dict(options)
        return item

    def _text(self, x, y, value, size, anchor="w"):
        return self._create("text", x, y, text=value, fill=AMBER,
                            font=(T.FONT, size), anchor=anchor)

    def _style(self, item, **options):
        previous = self.styles[item]
        changed = {key: value for key, value in options.items() if previous.get(key) != value}
        if changed:
            self.cv.itemconfigure(item, **changed)
            previous.update(changed)

    def hide(self):
        if self.visible:
            for item in self.items:
                self._style(item, state="hidden")
            self.visible = False

    def render(self, t, text, targets=()):
        progress = max(0, min(1, (t - REZ_START) / (REZ_END - REZ_START)))
        if progress >= 1:
            self.hide()
            return
        self.visible = True
        scan_y = self.top + (self.bottom - self.top) * progress
        tint = T.blend(AMBER, T.CYAN, min(1, progress * 5))
        flicker = .96 + .04 * math.sin(t * 18) ** 2
        self.cv.coords(self.panel, self.left, scan_y, self.right, self.bottom)
        self._style(self.panel, state="normal", outline=T.blend(T.BACKGROUND, tint, .3))
        cursor = "\u2588" if int(t * 2) % 2 == 0 else " "
        lines = ("> " + text.replace("\n", "\n> ") + cursor).splitlines()
        first = max(0, math.ceil((scan_y - self.text_y) / self.line_height)) if progress else 0
        shown = "\n".join(lines[first:])
        for item, offset, gain in ((self.glow, 1, .22), (self.term, 0, flicker)):
            self.cv.coords(item, self.left + 24 + offset,
                           self.text_y + first * self.line_height + offset)
            self._style(item, state="normal" if shown else "hidden", text=shown,
                        fill=T.blend(PANEL, tint, gain))
        for item, y in ((self.header, self.top + 23), (self.status, self.bottom - 21),
                        (self.prompt, self.bottom - 21)):
            self._style(item, state="normal" if y > scan_y + 10 else "hidden",
                        fill=T.blend(PANEL, tint, .63))
        self._style(self.prompt, text="DIGITIZING / GRID" if progress else "LINK / STANDBY")
        for item, y in self.scanlines:
            self._style(item, state="normal" if y > scan_y else "hidden")
        # stipple é lento no Windows: linhas sólidas sob o texto dão o mesmo tom
        for item in self.items[:1] + [item for item, _ in self.scanlines] + self.items[1:6]:
            self.cv.tag_raise(item)
        if progress > 0:
            self.rez_visible = True
            for item, (color, weight) in zip(self.beam, T.glow_layers(T.CYAN, 2)):
                self.cv.coords(item, self.left - 12, scan_y, self.right + 12, scan_y)
                self._style(item, state="normal", fill=color, width=weight)
                self.cv.tag_raise(item)
            for i, item in enumerate(self.cubes):
                phase = (i * .6180339) % 1
                age = t - REZ_START - phase * (REZ_END - REZ_START) * .82
                life = 1.1 - .6 * phase
                if not 0 <= age < life:
                    self._style(item, state="hidden")
                    continue
                q = age / life
                source_x = self.left + 30 + ((i * .381966) % 1) * (self.right - self.left - 60)
                source_y = self.top + phase * (self.bottom - self.top)
                dest = targets[i % len(targets)] if targets else (self.w * (.2 + phase * .6), self.h * .5)
                k = q * q * (3 - 2 * q)
                x = source_x + (dest[0] - source_x) * k
                y = source_y + (dest[1] - source_y) * k - math.sin(q * math.pi) * self.h * .09
                size = (2 + i % 4) * (1 - q * .7)
                pts = (x, y - size, x + size, y - size * .4,
                       x + size, y + size * .5, x, y + size,
                       x - size, y + size * .5, x - size, y - size * .4)
                edge = T.blend(T.blend(AMBER, T.CYAN, min(1, q * 3)), T.BACKGROUND, q * .6)
                self.cv.coords(item, *pts)
                self._style(item, state="normal", outline=edge,
                            fill=T.blend(T.BACKGROUND, edge, .12))
                self.cv.tag_raise(item)
        elif self.rez_visible:
            for item in self.beam + self.cubes:
                self._style(item, state="hidden")
            self.rez_visible = False

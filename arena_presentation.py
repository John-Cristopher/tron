"""Moldura, vazio e placar da arena compartilham um único retângulo."""

import math

from sprites_topview import draw_bike
from ui import Button, fitted
import theme as T


class ArenaChrome:
    def __init__(self, canvas, width, height, pause):
        self.cv, self.w, self.h = canvas, width, height
        self.scale = min(width / 1920, height / 1080)
        self.margin = max(16, round(35 * self.scale))
        self.hud_height = max(82, round(100 * self.scale))
        self.initial_rect = (self.margin, self.hud_height + 12,
                             width - self.margin, height - self.margin)
        self.rect = self.initial_rect
        self.masks = [canvas.create_rectangle(0, 0, 0, 0, fill=T.BACKGROUND,
                      outline="", tags="arena_void") for _ in range(4)]
        self.vignette = [canvas.create_rectangle(0, 0, 0, 0, fill=T.BACKGROUND,
                         outline="", stipple="gray25", tags="arena_void") for _ in range(4)]
        self.danger = [canvas.create_rectangle(0, 0, 0, 0, fill=T.ORANGE,
                       outline="", stipple="gray25", state="hidden",
                       tags="arena_danger") for _ in range(4)]
        self.edges = [canvas.create_rectangle(*self.rect, fill="", outline=color,
                      width=weight, tags="arena_edge")
                      for color, weight in T.glow_layers(T.CYAN, 2)]
        self.corners = [canvas.create_line(0, 0, 0, 0, 0, 0, fill=T.CORE,
                        width=max(1, self.scale * 2), tags="arena_edge") for _ in range(4)]
        self.cards, self.names, self.scores, self.accents, self.pips = {}, {}, {}, {}, {}
        self.lives = {}
        self.icons = {}
        font = -max(12, round(18 * self.scale))
        self.font_size = font
        for pid in range(1, 5):
            self.cards[pid] = canvas.create_rectangle(0, 0, 0, 0, fill=T.PANEL,
                outline=T.GRID_BRIGHT, tags="hud")
            self.accents[pid] = canvas.create_rectangle(0, 0, 0, 0, outline="", tags="hud")
            self.names[pid] = canvas.create_text(0, 0, anchor="w", font=(T.FONT, font, "bold"), tags="hud")
            self.scores[pid] = canvas.create_text(0, 0, anchor="e", font=(T.FONT, font, "bold"), tags="hud")
            self.lives[pid] = canvas.create_text(0, 0, anchor="e", font=(T.FONT, font), tags="hud")
            self.pips[pid] = [canvas.create_oval(0, 0, 0, 0, width=1, tags="hud") for _ in range(10)]
        self.info = canvas.create_text(width / 2, 0, fill=T.CORE, font=(T.FONT, -max(11, round(15 * self.scale))), tags="hud")
        pause_width = max(100, 138 * self.scale)
        self.pause_button = Button(canvas, "arena_pause",
            (width - self.margin - pause_width, self.hud_height - 31,
             width - self.margin, self.hud_height - 5), "PAUSA / ESC", pause,
            tags="hud", size=max(8, round(11 * self.scale)))
        self.info_width = width - 2 * self.margin - 2 * pause_width - 20

    def update_rect(self, target, elapsed, clock, warning=False, snap=False):
        gain = 1 if snap else 1 - math.exp(-max(0, elapsed) * 28)
        self.rect = tuple(a + (b - a) * gain for a, b in zip(self.rect, target))
        x0, y0, x1, y1 = self.rect
        for item, coords in zip(self.masks, ((0, 0, self.w, y0),
                (0, y1, self.w, self.h), (0, y0, x0, y1), (x1, y0, self.w, y1))):
            self.cv.coords(item, *coords)
        rim = max(12, 22 * self.scale)
        for item, coords in zip(self.vignette, ((x0, y0, x1, y0 + rim),
                (x0, y1 - rim, x1, y1), (x0, y0, x0 + rim, y1),
                (x1 - rim, y0, x1, y1))):
            self.cv.coords(item, *coords)
        pulse = .65 + .25 * math.sin(clock * 3)
        for item, (color, _) in zip(self.edges, T.glow_layers(T.CYAN, 2)):
            self.cv.coords(item, *self.rect)
            self.cv.itemconfig(item, outline=T.blend(T.BACKGROUND, color, pulse))
        size = max(16, 40 * self.scale)
        for item, (x, y, dx, dy) in zip(self.corners,
                ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1))):
            self.cv.coords(item, x + dx * size, y, x, y, x, y + dy * size)
        band = 16
        for item, coords in zip(self.danger, ((x0, y0, x1, y0 + band),
                (x0, y1 - band, x1, y1), (x0, y0 + band, x0 + band, y1 - band),
                (x1 - band, y0 + band, x1, y1 - band))):
            self.cv.coords(item, *coords)
            self.cv.itemconfig(item, state="normal" if warning else "hidden",
                fill=T.blend(T.WARNING, T.ORANGE, .45 + .35 * abs(math.sin(clock * 7))))

    def raise_layers(self):
        for tag in ("arena_danger", "arena_void", "arena_edge", "hud", "pause_obj"):
            self.cv.tag_raise(tag)

    def pause_visible(self, visible):
        button = self.pause_button
        for item in [*button.lines, button.body, *(item for item, _ in button.text_items)]:
            self.cv.itemconfig(item, state="normal" if visible else "hidden")

    def hud(self, active, controller, riders, lives, info):
        cv, scale = self.cv, self.scale
        gap = max(6, 12 * scale)
        card_width = (self.w - self.margin * 2 - 3 * gap) / 4
        top, bottom = 6, self.hud_height - 38
        for index, pid in enumerate(range(1, 5)):
            x0 = self.margin + index * (card_width + gap)
            x1 = x0 + card_width
            present = pid in active
            alive = present and (pid not in riders or riders[pid].alive)
            tint = controller.colors[pid] if alive else T.MUTED
            state = "normal" if present else "hidden"
            for item in (self.cards[pid], self.names[pid], self.scores[pid], self.accents[pid]):
                cv.itemconfig(item, state=state)
            cv.coords(self.cards[pid], x0, top, x1, bottom)
            cv.itemconfig(self.cards[pid], outline=T.blend(tint, T.PANEL, .60))
            cv.coords(self.accents[pid], x0, top, x0 + max(3, scale * 4), bottom)
            cv.itemconfig(self.accents[pid], fill=tint)
            icon_x, icon_y = x0 + max(29, 38 * scale), (top + bottom) / 2
            key = (controller.models[pid], tint, present)
            old = self.icons.get(pid)
            if old is None or old[0] != key:
                if old:
                    for item in old[1]:
                        cv.delete(item)
                items = draw_bike(cv, icon_x, icon_y, (1, 0), tint,
                                 controller.models[pid], scale=max(.75, scale), tags="hud")
                for item in items:
                    cv.itemconfig(item, state=state)
                self.icons[pid] = (key, items)
            mode = controller.game_mode
            ai = mode == "training" and pid > controller.training_human_count
            name = "RINZLER" if mode == "rinzler" and pid == 2 else f"P{pid}" + (" / IA" if ai else "")
            if not alive:
                name += " / FORA"
            text_x = x0 + max(43, 55 * scale)
            cv.coords(self.names[pid], text_x, top + (bottom - top) * .30)
            team_mode = mode == "team2v2" or (mode == "training" and controller.training_teams)
            owner = (1 if pid in (1, 3) else 2) if team_mode else pid
            score, target = controller.scores[owner], controller.match_target
            label = f"{score}/{target}" if mode != "rinzler" else ("FUGA" if pid == 1 else "CAÇA")
            name_width = x1 - 8 - text_x - max(32, len(label) * abs(self.font_size) * .62) - 10
            cv.itemconfig(self.names[pid], text=fitted(cv, name, self.font_size, name_width, True), fill=tint)
            cv.coords(self.scores[pid], x1 - 8, top + (bottom - top) * .30)
            cv.itemconfig(self.scores[pid], text=label, fill=T.CORE if alive else T.MUTED)
            cv.coords(self.lives[pid], x1 - 8, top + (bottom - top) * .73)
            cv.itemconfig(self.lives[pid], text=f"{lives.get(pid, 2)}V", fill=tint,
                state=state if controller.modifiers["lives"] else "hidden")
            radius = max(2, min(4, 4 * scale))
            for i, item in enumerate(self.pips[pid]):
                x = text_x + i * (radius * 2 + 4)
                y = top + (bottom - top) * .73
                cv.coords(item, x, y - radius, x + radius * 2, y + radius)
                cv.itemconfig(item, state=state if i < min(target, 10) and mode != "rinzler" else "hidden",
                    fill=tint if i < score else T.PANEL, outline=tint if i < score else T.GRID_BRIGHT)
        cv.coords(self.info, self.w / 2 - max(20, 50 * scale), self.hud_height - 18)
        cv.itemconfig(self.info, text=fitted(cv, info, -max(11, round(15 * scale)), self.info_width))
        self.raise_layers()

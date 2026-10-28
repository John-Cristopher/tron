"""Componentes do Canvas e layout calculado a partir da área útil da janela."""

from dataclasses import dataclass
import math

import theme as T
from intro_logo import logo_geometry


@dataclass(frozen=True)
class Layout:
    width: int
    height: int

    @property
    def margin(self):
        return 32 if self.width >= 1000 else 24

    @property
    def header(self):
        return 80 if self.height >= 900 else 64

    @property
    def tabs(self):
        return (
            self.margin,
            self.header + 8,
            self.width - self.margin,
            self.header + 56,
        )

    @property
    def content(self):
        return (
            self.margin,
            self.header + 80,
            self.width - self.margin,
            self.height - 176,
        )

    @property
    def actions_y(self):
        return self.height - 128

    @property
    def help_y(self):
        return self.height - 78

    @property
    def keys_y(self):
        return self.height - 32


def text(
    cv, x, y, value, size=14, color=T.CORE, anchor="w", tags="ui", bold=False, **options
):
    return cv.create_text(
        x,
        y,
        text=value,
        fill=color,
        anchor=anchor,
        font=(T.FONT, size, "bold" if bold else "normal"),
        tags=tags,
        **options,
    )


def fitted(cv, value, size, width, bold=False):
    """Mantém o texto dentro do controle, incluindo a escala de DPI do Tk."""
    if not hasattr(cv, "tk"):
        return str(value)
    from tkinter import font

    measure = font.Font(
        root=cv, font=(T.FONT, size, "bold" if bold else "normal")
    ).measure
    value = str(value)
    if measure(value) <= width:
        return value
    while value and measure(value + "…") > width:
        value = value[:-1]
    return value + "…"


def panel(cv, box, fill=T.PANEL, edge=T.GRID_BRIGHT, tags="ui"):
    return cv.create_rectangle(*box, fill=fill, outline=edge, width=1, tags=tags)


def corners(cv, box, color=T.CYAN, tags="ui", size=12):
    a, b, c, d = box
    return [
        cv.create_line(
            x + dx * size, y, x, y, x, y + dy * size, fill=color, width=2, tags=tags
        )
        for x, y, dx, dy in ((a, b, 1, 1), (c, b, -1, 1), (a, d, 1, -1), (c, d, -1, -1))
    ]


class Component:
    def __init__(
        self,
        cv,
        key,
        box,
        label,
        command=None,
        focus=None,
        selected=False,
        tags="ui",
        size=14,
    ):
        self.cv, self.key, self.box, self.command = cv, key, box, command
        self.tag = "control_" + str(key)
        self.tags = (
            (tags, self.tag) if isinstance(tags, str) else tuple(tags) + (self.tag,)
        )
        self.lines = []
        for color, width in T.glow_layers(T.CYAN, 1):
            self.lines.append(
                cv.create_rectangle(
                    *box, fill="", outline=color, width=width, tags=self.tags
                )
            )
        self.body = panel(
            cv,
            box,
            T.blend(T.PANEL, T.ARMOR, 0.5) if selected else T.PANEL,
            tags=self.tags,
        )
        self.label = label
        self.size = size
        self.selected = selected
        self.visible = True
        self.text_items = []
        if hasattr(cv, "tag_bind"):
            cv.tag_bind(
                self.tag, "<Enter>", lambda event: focus(key) if focus else None
            )
            cv.tag_bind(self.tag, "<Button-1>", self.clicked)
        self.paint(selected)

    def invoke(self):
        if self.command:
            self.command()

    def clicked(self, event):
        self.invoke()

    def change(self, step):
        self.invoke()

    def set_visible(self, visible):
        if visible != self.visible:
            self.cv.itemconfigure(self.tag, state="normal" if visible else "hidden")
            self.visible = visible

    def paint(self, selected, t=0, alpha=1):
        selected = selected or getattr(self, "active", False)
        self.selected = selected
        gain = (0.72 + 0.18 * math.sin(t * 2.2)) if selected else 0.2
        for item, (color, width) in zip(self.lines, T.glow_layers(T.CYAN, 1)):
            self.cv.itemconfigure(
                item,
                outline=T.blend(T.BACKGROUND, color, gain * alpha),
                width=width if selected else 1,
            )
        self.cv.itemconfigure(
            self.body,
            outline=(
                T.CYAN
                if selected
                else (
                    T.blend(T.CYAN, T.GRID, 0.45)
                    if getattr(self, "value", False)
                    else T.GRID_BRIGHT
                )
            ),
            fill=T.blend(T.PANEL, T.ARMOR, 0.5) if selected else T.PANEL,
        )
        for item, color in self.text_items:
            self.cv.itemconfigure(item, fill=T.blend(T.BACKGROUND, color, alpha))


class Button(Component):
    def __init__(self, cv, key, box, label, command=None, **options):
        super().__init__(cv, key, box, label, command, **options)
        x0, y0, x1, y1 = box
        item = text(
            cv,
            (x0 + x1) / 2,
            (y0 + y1) / 2,
            label,
            self.size,
            anchor="center",
            tags=self.tags,
            bold=True,
        )
        self.text_items.append((item, T.CORE))


class Selector(Component):
    def __init__(self, cv, key, box, label, value, change, activate=None, **options):
        super().__init__(
            cv, key, box, label, activate or (lambda: change(1)), **options
        )
        self.adjust = change
        x0, y0, x1, y1 = box
        label_size = max(10, self.size - 2)
        self.text_items.append(
            (
                text(
                    cv,
                    (x0 + x1) / 2,
                    y0 + 12,
                    fitted(cv, label, label_size, x1 - x0 - 16),
                    label_size,
                    T.MUTED,
                    "center",
                    self.tags,
                ),
                T.MUTED,
            )
        )
        self.text_items.append(
            (
                text(
                    cv,
                    (x0 + x1) / 2,
                    y0 + (y1 - y0) * 0.65,
                    fitted(cv, value, self.size, x1 - x0 - 88, True),
                    self.size,
                    T.CORE,
                    "center",
                    self.tags,
                    True,
                ),
                T.CORE,
            )
        )
        for step, x in ((-1, x0 + 20), (1, x1 - 20)):
            tag = self.tag + str(step)
            item = text(
                cv,
                x,
                (y0 + y1) / 2,
                "◄" if step < 0 else "►",
                self.size,
                T.CYAN,
                "center",
                self.tags + (tag,),
            )
            self.text_items.append((item, T.CYAN))

    def clicked(self, event):
        if event.x < self.box[0] + 40:
            self.adjust(-1)
        elif event.x > self.box[2] - 40:
            self.adjust(1)
        else:
            self.invoke()

    def change(self, step):
        self.adjust(step)


class Toggle(Component):
    def __init__(self, cv, key, box, label, value, command, description="", **options):
        self.value = value
        super().__init__(cv, key, box, label, command, **options)
        x0, y0, x1, y1 = box
        compact = bool(description) and x1 - x0 < 300
        item = text(
            cv,
            x0 + 12,
            y0 + 18,
            fitted(cv, label, self.size, x1 - x0 - (24 if compact else 80), True),
            self.size,
            T.CORE,
            tags=self.tags,
            bold=True,
        )
        self.text_items.append((item, T.CORE))
        if description:
            desc_size = max(10, self.size - 2)
            item = text(
                cv,
                x0 + 12,
                y1 - 15,
                fitted(cv, description, desc_size, x1 - x0 - (88 if compact else 24)),
                desc_size,
                T.MUTED,
                tags=self.tags,
            )
            self.text_items.append((item, T.MUTED))
        cx, cy = x1 - 34, y1 - 16 if compact else y0 + 18
        cv.create_rectangle(
            cx - 20,
            cy - 9,
            cx + 20,
            cy + 9,
            fill=T.GRID if not value else T.blend(T.CYAN, T.BACKGROUND, 0.65),
            outline=T.CYAN if value else T.MUTED,
            tags=self.tags,
        )
        cv.create_oval(
            cx + (3 if value else -17),
            cy - 6,
            cx + (17 if value else -3),
            cy + 6,
            fill=T.CYAN if value else T.MUTED,
            outline="",
            tags=self.tags,
        )
        if value:
            cv.create_line(
                x0 + 1, y1 - 1, x1 - 1, y1 - 1, fill=T.CYAN, width=2, tags=self.tags
            )


class Tabs:
    def __init__(self, cv, box, steps, current, select, focus=None):
        self.controls = {}
        x0, y0, x1, y1 = box
        gap = 16
        width = (x1 - x0 - gap * (len(steps) - 1)) / len(steps)
        index = [key for key, label in steps].index(current)
        cv.create_line(
            x0,
            y0 + (y1 - y0) / 2,
            x1,
            y0 + (y1 - y0) / 2,
            fill=T.GRID_BRIGHT,
            width=2,
            tags="ui",
        )
        for i, (key, label) in enumerate(steps):
            left = x0 + i * (width + gap)
            title = ("✓" if i < index else f"{i+1:02d}") + "  " + label
            self.controls[("setup_step", key)] = Button(
                cv,
                ("setup_step", key),
                (left, y0, left + width, y1),
                title,
                lambda k=key: select(k),
                focus=focus,
                selected=i == index,
                size=14,
            )
            self.controls[("setup_step", key)].active = i == index


class Registry:
    def __init__(self):
        self.controls = {}

    def add(self, component):
        self.controls[component.key] = component
        return component

    @property
    def boxes(self):
        return {key: component.box for key, component in self.controls.items()}

    def paint(self, focus, t, alpha=1):
        for key, component in self.controls.items():
            component.paint(key == focus, t, alpha)


class TubeLogo:
    def __init__(self, cv, box, tags="title"):
        self.cv, self.items = cv, []
        _, contours = logo_geometry()
        x0, y0, x1, y1 = box
        scale = min((x1 - x0) / 11.12, (y1 - y0) / 2.76)
        for contour in contours:
            coords = [
                v
                for x, y in contour + contour[:1]
                for v in ((x0 + x1) / 2 + (x + 0.24) * scale, (y0 + y1) / 2 + y * scale)
            ]
            for color, width in T.glow_layers(T.CYAN, 1.5):
                item = cv.create_line(*coords, fill=color, width=width, tags=tags)
                self.items.append((item, color))

    def animate(self, t, alpha=1):
        flicker = 0.35 if t < 0.8 and int(t * 17) % 5 in (0, 2) else 1.0
        for item, color in self.items:
            self.cv.itemconfigure(item, fill=T.blend(T.BACKGROUND, color, flicker * alpha))


class IdentityDisc:
    def __init__(self, cv, x, y, r, tags="title"):
        self.cv, self.x, self.y, self.r = cv, x, y, r
        self.arcs = []
        cv.create_oval(
            x - r,
            y - r,
            x + r,
            y + r,
            fill=T.SUIT,
            outline=T.GRID_BRIGHT,
            width=2,
            tags=tags,
        )
        cv.create_oval(
            x - r * 0.72,
            y - r * 0.72,
            x + r * 0.72,
            y + r * 0.72,
            fill=T.PANEL,
            outline=T.CYAN,
            width=2,
            tags=tags,
        )
        for i in range(3):
            self.arcs.append(
                cv.create_line(*self.points(0, i), fill=T.CORE, width=2, tags=tags)
            )
        self.animate(0)

    def points(self, t, i):
        points = []
        for j in range(12):
            angle = t * 0.12 + i * math.tau / 3 + j * 0.035
            points.extend(
                (
                    self.x + math.cos(angle) * self.r * 0.9,
                    self.y + math.sin(angle) * self.r * 0.9,
                )
            )
        return points

    def animate(self, t):
        for i, item in enumerate(self.arcs):
            self.cv.coords(item, *self.points(t, i))


def keycaps(cv, cx, cy, groups, size=12, tags=("ui", "hint")):
    from tkinter import font

    measure = (
        (
            lambda value, bold=False: font.Font(
                root=cv, font=(T.FONT, size, "bold" if bold else "normal")
            ).measure(value)
        )
        if hasattr(cv, "tk")
        else lambda value, bold=False: len(value) * round(size * 1.333 * 0.6)
    )
    widths = [measure(key, True) + 20 + measure(label) + 32 for key, label in groups]
    x = cx - sum(widths) / 2
    for (key, label), width in zip(groups, widths):
        kw = measure(key, True) + 20
        panel(cv, (x, cy - 14, x + kw, cy + 14), T.PANEL, T.GRID_BRIGHT, tags)
        text(cv, x + kw / 2, cy, key, size, T.CORE, "center", tags, True)
        text(cv, x + kw + 8, cy, label, size, T.CORE, "w", tags)
        x += width

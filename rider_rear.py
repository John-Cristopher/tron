"""Piloto traseiro: geometria preenchida e cinco inclinações em cache."""

from collections import OrderedDict
import math
import tkinter as tk

from sprites_topview import oval
import theme as T

LEAN_FRAMES = (-1.0, -0.5, 0.0, 0.5, 1.0)


def lean_frame(value):
    return min(range(5), key=lambda i: abs(LEAN_FRAMES[i] - value))


def rear_geometry(polygon, line, color, model=0):
    """Massa escura em gota, pods laterais e luz apenas nos circuitos."""
    def shape(points, fill=T.BIKE_BODY, edge=None, width=.008):
        polygon(points, fill, edge, width)

    def ellipse(x, y, rx, ry, fill=T.BIKE_BODY, edge=None, width=.008):
        shape(oval(x, y, rx, ry, 32), fill, edge, width)

    ellipse(0, .012, .44, .055, T.RUBBER)
    wide = 1.15 if model == 2 else 1.0
    # Carenagem/roda: o miolo permanece quase preto, sem aro de raio X.
    body = [(-.07, 0), (-.18, -.05), (-.25, -.17), (-.28, -.34),
            (-.26, -.50), (-.20, -.64), (-.12, -.73), (0, -.77),
            (.12, -.73), (.20, -.64), (.26, -.50), (.28, -.34),
            (.25, -.17), (.18, -.05), (.07, 0)]
    shape([(x * wide, y) for x, y in body], T.RUBBER)
    for side in (-1, 1):
        shape([(side * .20, -.58), (side * .35, -.56), (side * .41, -.42),
               (side * .42, -.25), (side * .34, -.20), (side * .24, -.28)], T.BIKE_ARMOR)
        line([(side * .32, -.48), (side * .36, -.38), (side * .36, -.25)], color, .015)
        shape([(side * .31, -.53), (side * .40, -.53), (side * .40, -.48),
               (side * .31, -.48)], T.METAL)
    line([(0, -.68), (0, -.47), (0, -.22), (0, -.025)], color, .040)
    for side in (-1, 1):
        line([(side * .19, -.51), (side * .23, -.34), (side * .20, -.13)], color, .010)
        # Braços abertos e dobrados até as manoplas, preenchidos antes da luz.
        shape([(side * .14, -.83), (side * .28, -.78), (side * .39, -.60),
               (side * .37, -.49), (side * .31, -.50), (side * .28, -.63),
               (side * .12, -.71)], T.SUIT)
        line([(side * .15, -.80), (side * .25, -.74), (side * .34, -.59),
              (side * .34, -.52)], color, .011)
    shape([(-.20, -.81), (-.12, -.86), (.12, -.86), (.20, -.81),
           (.14, -.62), (.08, -.53), (-.08, -.53), (-.14, -.62)], T.SUIT)
    shape([(-.11, -.79), (0, -.83), (.11, -.79), (.07, -.61),
           (0, -.55), (-.07, -.61)], T.BIKE_ARMOR)
    line([(-.18, -.78), (0, -.82), (.18, -.78)], color, .013)
    for side in (-1, 1):
        line([(side * .13, -.74), (side * .10, -.63), (side * .06, -.57)], color, .008)
    ellipse(0, -.68, .056, .059, T.SUIT, color, .008)
    ellipse(0, -.68, .034, .037, T.BIKE_BODY)
    ellipse(0, -.94, .118, .126, T.BIKE_BODY)
    shape([(-.09, -1.00), (0, -1.05), (.09, -1.00), (.08, -.94),
           (0, -.97), (-.08, -.94)], T.BIKE_ARMOR)
    line([(-.10, -.93), (0, -.90), (.10, -.93)], color, .013)


def side_geometry(polygon, line, color):
    """Frame lateral da queda; duas rodas e piloto baixo sobre a carenagem."""
    for x in (-.36, .37):
        polygon(oval(x, -.13, .17, .17, 24), T.RUBBER, None, .01)
        line(oval(x, -.13, .125, .125, 24), color, .018)
    polygon([(-.48, -.18), (-.36, -.35), (.26, -.34), (.52, -.22),
             (.48, -.11), (-.40, -.09)], T.BIKE_BODY, None, .01)
    line([(-.43, -.19), (-.25, -.30), (.28, -.29), (.45, -.20)], color, .018)
    polygon([(-.22, -.31), (-.20, -.45), (.01, -.55), (.24, -.42),
             (.31, -.30), (.22, -.29), (.04, -.40), (-.05, -.27)], T.SUIT, None, .01)
    polygon(oval(.04, -.57, .10, .11, 24), T.BIKE_BODY, None, .01)
    line([(-.18, -.42), (.0, -.49), (.23, -.36)], color, .012)
    line([(-.02, -.61), (.10, -.57)], color, .012)


def render_rear(size, color, frame=2, model=0, view=0):
    width, height = math.ceil(size * 1.6), math.ceil(size * 1.25)
    art = T.RasterArt((width, height), supersample=4)
    origin = (width / 2, height - size * 0.08)
    angle = LEAN_FRAMES[frame] * 0.20
    ca, sa = math.cos(angle), math.sin(angle)

    def transform(points):
        points = [(x * .83 + (-y - .3) * .35, y) for x, y in points] if view == 1 else points
        return [(origin[0] + size * (x * ca - y * sa),
                 origin[1] + size * (x * sa + y * ca)) for x, y in points]

    def polygon(points, fill, edge, width):
        art.polygon(transform(points), fill, edge, max(0.65, size * width))

    def line(points, color, width):
        art.line(transform(points), color, max(0.65, size * width))

    if view == 2:
        side_geometry(polygon, line, color)
    else:
        rear_geometry(polygon, line, color, model)
    return art.finish(radius=max(1.5, size * 0.012))


class RearSprites:
    def __init__(self, canvas):
        self.canvas = canvas
        self.cache = OrderedDict()
        self.available = T.Image is not None and isinstance(canvas, tk.Canvas)

    def photo(self, size, color, frame, model, view=0):
        size = max(8, min(360, round(size / 4) * 4))
        key = (size, color, frame, model, view)
        if key not in self.cache:
            self.cache[key] = T.ImageTk.PhotoImage(
                render_rear(*key), master=self.canvas
            )
            if len(self.cache) > 128:
                self.cache.popitem(last=False)
        self.cache.move_to_end(key)
        return self.cache[key], size

    def warm(self, size, color, model):
        if self.available:
            for frame in range(5):
                self.photo(size, color, frame, model)

    def draw(self, painter, x, y, size, color, lean=0.0, model=0, view=0, phase=0):
        if size < 2:
            return
        if self.available:
            photo, size = self.photo(size, color, lean_frame(lean), model, view)
            # Mantém os sprites usados vivos mesmo quando o cache descarta entradas.
            painter.image(x, y + size * 0.08, image=photo, anchor="s")
        else:
            rear_bike(painter, x, y, size, color, lean, model, view)
        if size > 18 and not view and abs(lean) < .2:
            yy = y - size * (.09 + (phase % 1) * .34)
            painter.line((x, yy, x, yy - size * .045), fill=T.blend(color, T.CORE, .65), width=max(1, size * .018))


def rear_bike(painter, x, y, size, color, lean=0.0, model=0, view=0):
    """Desenho vetorial para execução sem Pillow."""
    angle = LEAN_FRAMES[lean_frame(lean)] * 0.20
    ca, sa = math.cos(angle), math.sin(angle)

    def transform(points):
        points = [(px * .83 + (-py - .3) * .35, py) for px, py in points] if view == 1 else points
        return [
            v
            for px, py in points
            for v in (x + size * (px * ca - py * sa), y + size * (px * sa + py * ca))
        ]

    def polygon(points, fill, edge, width):
        painter.polygon(
            transform(points),
            fill=fill,
            outline=edge or "",
            width=max(0.6, size * width),
        )

    def line(points, color, width):
        T.neon_line(painter, transform(points), color, max(0.6, size * width))

    if view == 2:
        side_geometry(polygon, line, color)
    else:
        rear_geometry(polygon, line, color, model)

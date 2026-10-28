"""Paleta e brilho compartilhados pelos renderizadores do jogo.

Pillow é opcional: o Canvas mantém uma versão vetorial sem desfoque.
"""

from functools import lru_cache

BACKGROUND = "#02060A"
CYAN = "#00E5FF"
CORE = "#E6FDFF"
ORANGE = "#FF6A00"
GRID = "#0B2A33"
GRID_BRIGHT = "#174954"
RED = "#FF315C"
GREEN = "#43FFB1"
PURPLE = "#A390FF"
AMBER = "#FFC266"
SHELL = "#09151E"
ARMOR = "#102330"
RUBBER = "#020509"
BIKE_BODY = "#03090E"
BIKE_ARMOR = "#0A1720"
SUIT = "#070F17"
SUIT_HIGHLIGHT = "#142B39"
GLASS = "#193C4A"
METAL = "#3E6270"
PANEL = "#06121C"
MUTED = "#80A5B4"
SKY_HORIZON = "#133442"
MOUNTAIN_FAR = "#102D3A"
MOUNTAIN_NEAR = "#071924"
TOWER = "#12333E"
ASPHALT = ("#09131E", "#0D1A26")
SHOULDER = ("#12333E", "#18505C")
WARNING = "#2A160F"
FONT = "Consolas"
VERSION = "0.4.0-dev"
SPACE = 8

PLAYER_PALETTE = (
    ("CIANO", CYAN),
    ("AZUL", "#0088FF"),
    ("TURQUESA", "#00FFDD"),
    ("GELO", CORE),
    ("VERMELHO", RED),
    ("CARMIM", "#FF2020"),
    ("ROSA", "#FF44AA"),
    ("MAGENTA", "#FF00FF"),
    ("VERDE", GREEN),
    ("LIMA", "#88FF00"),
    ("MENTA", "#00FFBB"),
    ("JADE", "#00CC77"),
    ("LARANJA", ORANGE),
    ("OURO", "#FFDD00"),
    ("FOGO", "#FF8844"),
    ("VIOLETA", PURPLE),
)

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageTk
except ImportError:
    Image = ImageDraw = ImageFilter = ImageTk = None

RESAMPLE = getattr(Image, "Resampling", Image)


def rgb(color):
    return tuple(int(color[i : i + 2], 16) for i in (1, 3, 5))


@lru_cache(maxsize=2048)
def blend(a, b, t):
    t = max(0.0, min(1.0, t))
    return "#%02x%02x%02x" % tuple(int(x + (y - x) * t) for x, y in zip(rgb(a), rgb(b)))


def glow_layers(color, width=2):
    """Halo escuro largo, linha colorida e núcleo quase branco (Canvas)."""
    return (
        (blend(color, BACKGROUND, 0.78), width * 4),
        (color, width * 1.6),
        (blend(color, CORE, 0.82), max(0.6, width * 0.45)),
    )


def neon_line(painter, coords, color=CYAN, width=2, **options):
    return [
        painter.line(coords, fill=tint, width=weight, **options)
        for tint, weight in glow_layers(color, width)
    ]


class RasterArt:
    """Desenha formas e acumula circuitos; o desfoque é calculado uma única vez."""

    def __init__(self, size, supersample=2):
        self.scale = supersample
        self.size = size
        large = tuple(int(v * supersample) for v in size)
        self.base = Image.new("RGBA", large)
        self.light = Image.new("RGBA", large)
        self.core = Image.new("RGBA", large)
        self.draw = ImageDraw.Draw(self.base)

    def points(self, points):
        return [(x * self.scale, y * self.scale) for x, y in points]

    def polygon(self, points, fill=SHELL, edge=None, width=1):
        pts = self.points(points)
        # Uma forma opaca também oculta circuitos das peças que estão atrás dela.
        # Compor todos os contornos por cima gerava um aspecto de raio X.
        ImageDraw.Draw(self.light).polygon(pts, fill=(0, 0, 0, 0))
        ImageDraw.Draw(self.core).polygon(pts, fill=(0, 0, 0, 0))
        self.draw.polygon(pts, fill=fill)
        if edge:
            self.line(points + [points[0]], edge, width)

    def line(self, points, color=CYAN, width=1, core_mix=0.82):
        pts = self.points(points)
        ImageDraw.Draw(self.light).line(
            pts, fill=color, width=max(1, round(width * self.scale)), joint="curve"
        )
        ImageDraw.Draw(self.core).line(
            pts,
            fill=blend(color, CORE, core_mix),
            width=max(1, round(width * self.scale * 0.35)),
            joint="curve",
        )

    def finish(self, radius=2):
        halo = self.light.filter(ImageFilter.GaussianBlur(radius * self.scale))
        halo.putalpha(halo.getchannel("A").point(lambda alpha: int(alpha * 0.65)))
        result = Image.alpha_composite(halo, self.base)
        result = Image.alpha_composite(result, self.light)
        result = Image.alpha_composite(result, self.core)
        return result.resize(self.size, RESAMPLE.LANCZOS)

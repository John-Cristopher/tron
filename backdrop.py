"""Fundo desfocado e escurecido dos menus de seleção (modo de jogo e configuração).

O Tkinter não faz blur nem transparência. Solução: a cena do estádio é desenhada uma vez, fora
da tela, com o Pillow (`PilCanvas` imita os métodos create_* do Canvas, então o próprio código de
desenho do menu é reaproveitado) e vira uma sequência de imagens cada vez mais desfocadas e
escuras. A transição só troca de imagem; nada é calculado a cada quadro.

Sem o Pillow, `AVAILABLE` é False e o menu apenas escurece os itens do canvas.
"""

import base64
import io
import tkinter as tk
import os
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

    AVAILABLE = True
    RESAMPLE = getattr(Image, "Resampling", Image).BILINEAR
except ImportError:
    AVAILABLE = False
try:
    from PIL import ImageTk
except ImportError:  # Pillow sem o módulo do Tk: to_photo() usa PNG
    ImageTk = None


class PilCanvas:
    """Imita o mínimo do tk.Canvas usado no desenho do fundo, pintando num Image do Pillow."""

    def __init__(self, width, height, scale, bg):
        self.scale = scale
        self.img = Image.new(
            "RGBA" if bg is None else "RGB",
            (max(1, round(width * scale)), max(1, round(height * scale))),
            bg,
        )
        self.draw = ImageDraw.Draw(self.img)
        self._last_id = 0

    def _new_id(self):
        self._last_id += 1
        return self._last_id

    def _xy(self, coords):
        return [float(c) * self.scale for c in coords]

    def _width(self, kw):
        return max(1, round(float(kw.get("width", 1)) * self.scale))

    @staticmethod
    def _color(value):
        return value or None  # "" (sem cor) vira None no Pillow

    def create_rectangle(self, x1, y1, x2, y2, **kw):
        x1, y1, x2, y2 = self._xy((x1, y1, x2, y2))
        self.draw.rectangle(
            [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)],
            fill=self._color(kw.get("fill")),
            outline=self._color(kw.get("outline")),
            width=self._width(kw),
        )
        return self._new_id()

    def create_oval(self, x1, y1, x2, y2, **kw):
        x1, y1, x2, y2 = self._xy((x1, y1, x2, y2))
        self.draw.ellipse(
            [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)],
            fill=self._color(kw.get("fill")),
            outline=self._color(kw.get("outline")),
            width=self._width(kw),
        )
        return self._new_id()

    def create_line(self, *coords, **kw):
        pts = self._xy(coords)
        if len(pts) >= 4:
            width = self._width(kw)
            self.draw.line(
                pts,
                fill=kw.get("fill") or "#000000",
                width=width,
                joint="curve" if width > 1 and len(pts) > 4 else None,
            )
        return self._new_id()

    def create_polygon(self, *coords, **kw):
        pts = self._xy(coords)
        if len(pts) >= 6:
            self.draw.polygon(
                pts,
                fill=self._color(kw.get("fill")),
                outline=self._color(kw.get("outline")),
            )
        return self._new_id()

    def create_text(self, x, y, **kw):
        family, size, *weight = kw.get("font", ("Consolas", 12))
        filename = "consolab.ttf" if "bold" in weight else "consola.ttf"
        try:
            font = ImageFont.truetype(
                str(Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / filename),
                max(8, round(size * 1.333 * self.scale)),
            )
        except OSError:
            font = ImageFont.load_default()
        value = str(kw.get("text", ""))
        bbox = self.draw.multiline_textbbox((0, 0), value, font=font)
        width, height = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x, y = x * self.scale, y * self.scale
        anchor = kw.get("anchor", "center")
        x -= (
            width
            if "e" in anchor and anchor != "center"
            else 0 if "w" in anchor else width / 2
        )
        y -= (
            0
            if "n" in anchor and anchor != "center"
            else height if "s" in anchor else height / 2
        )
        self.draw.multiline_text(
            (x - bbox[0], y - bbox[1]),
            value,
            font=font,
            fill=kw.get("fill"),
            align=kw.get("justify", "left"),
        )
        return self._new_id()

    def coords(self, *args):
        pass

    def itemconfigure(self, *args, **kwargs):
        pass

    itemconfig = itemconfigure

    def tag_bind(self, *args, **kwargs):
        pass


def snapshot(paint, width, height, bg, scale=0.5):
    """Roda `paint(canvas)` num PilCanvas e devolve a imagem. Meia resolução basta: o desfoque esconde o resto."""
    canvas = PilCanvas(width, height, scale, bg)
    paint(canvas)
    return canvas.img


def to_photo(canvas, img):
    """Imagem do Pillow -> PhotoImage do Tk (via ImageTk ou, se faltar, via PNG em base64)."""
    if ImageTk is not None:
        return ImageTk.PhotoImage(img, master=canvas)
    buf = io.BytesIO()
    img.save(buf, "PNG", compress_level=1)
    return tk.PhotoImage(
        master=canvas, data=base64.b64encode(buf.getvalue()).decode("ascii")
    )


class Backdrop:
    """Item de imagem do canvas com o fundo em vários graus de desfoque/escurecimento.

    `show(k)` aceita k de 0 (nítido) a 1 (desfoque e escurecimento finais). Os níveis são
    calculados uma única vez na criação; mostrar um nível é só redimensionar e trocar a imagem.
    """

    def __init__(self, canvas, width, height, base, radius, dim, steps=8):
        self.cv, self.size = canvas, (width, height)
        self.levels = self._build(base, radius, dim, steps)
        self.item = canvas.create_image(
            0, 0, anchor="nw", state="hidden", tags="backdrop"
        )
        self.photo = None  # o Tk só mantém a imagem enquanto houver referência
        self.shown = None  # índice do nível que está no canvas
        self.visible = False

    @staticmethod
    def _build(base, radius, dim, steps):
        levels = [base]
        for i in range(1, steps + 1):
            k = i / steps
            k = k * k * (3 - 2 * k)  # começo e fim suaves
            img = base
            if radius * k > 0.05:
                img = img.filter(ImageFilter.GaussianBlur(radius * k))
            if dim > 0:
                img = ImageEnhance.Brightness(img).enhance(1 - dim * k)
            levels.append(img)
        return levels

    def show(self, k):
        idx = round(max(0.0, min(1.0, k)) * (len(self.levels) - 1))
        if idx != self.shown:
            photo = to_photo(self.cv, self.levels[idx].resize(self.size, RESAMPLE))
            self.cv.itemconfig(self.item, image=photo)
            self.photo, self.shown = photo, idx  # a imagem anterior é liberada aqui
        if not self.visible:
            self.cv.itemconfig(self.item, state="normal")
            self.visible = True

    def hide(self):
        if self.visible:
            self.cv.itemconfig(self.item, state="hidden")
            self.visible = False

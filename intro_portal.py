"""O menu é visto através do O e assume a tela durante a travessia."""

import math
import tkinter as tk

import backdrop
import theme as T
from intro_world import LOGO_ORIGIN, LOGO_SCALE, smooth


def perspective_coefficients(destination, source):
    """Homografia inversa: coordenadas da tela -> imagem, sem dependência de NumPy."""
    matrix = []
    for (x, y), (u, v) in zip(destination, source):
        matrix.extend(
            (
                [x, y, 1, 0, 0, 0, -u * x, -u * y, u],
                [0, 0, 0, x, y, 1, -v * x, -v * y, v],
            )
        )
    for column in range(8):
        pivot = max(range(column, 8), key=lambda row: abs(matrix[row][column]))
        matrix[column], matrix[pivot] = matrix[pivot], matrix[column]
        divisor = matrix[column][column]
        if abs(divisor) < 1e-10:
            raise ValueError("Plano de portal degenerado")
        matrix[column] = [value / divisor for value in matrix[column]]
        for row in range(8):
            if row != column:
                factor = matrix[row][column]
                matrix[row] = [
                    a - factor * b for a, b in zip(matrix[row], matrix[column])
                ]
    return tuple(matrix[row][-1] for row in range(8))


class IntroPortal:
    def __init__(self, canvas, width, height):
        self.cv, self.w, self.h = canvas, width, height
        self.item = self.photo = self.source = None
        self.last = -1.0
        if not isinstance(canvas, tk.Canvas) or not backdrop.AVAILABLE:
            return
        from menu_scene import menu_snapshot

        self.source = menu_snapshot(width, height, interface=False)
        if self.source is None:
            return
        self.full_source = self.source
        self.ratio = min(1.0, 960 / width)
        self.size = (round(width * self.ratio), round(height * self.ratio))
        self.source = self.source.resize(self.size, backdrop.RESAMPLE).convert("RGB")
        self.photo = backdrop.to_photo(
            canvas, backdrop.Image.new("RGBA", (width, height))
        )
        self.item = canvas.create_image(
            0, 0, anchor="nw", image=self.photo, state="hidden", tags="intro"
        )

    def render(self, t, view):
        if self.item is None or t < 49.5:
            return
        if 0 <= t - self.last < 1 / 30:
            return
        self.last = t
        frame = self.frame(t, view)
        if hasattr(self.photo, "paste"):
            self.photo.paste(frame)
        else:
            self.photo = backdrop.to_photo(self.cv, frame)
            self.cv.itemconfigure(self.item, image=self.photo)
        self.cv.itemconfigure(self.item, state="normal")
        self.cv.tag_raise(self.item)

    def frame(self, t, view):
        Image, Draw = backdrop.Image, backdrop.ImageDraw
        r = self.ratio
        w, h = self.size
        full = ((0, 0), (w, 0), (w, h), (0, h))
        if view.z >= LOGO_ORIGIN[2] - 0.6:
            return self.full_source

        def world(x, y, z=0):
            return (
                LOGO_ORIGIN[0] + x * LOGO_SCALE,
                LOGO_ORIGIN[1] + y * LOGO_SCALE,
                LOGO_ORIGIN[2] + z * LOGO_SCALE,
            )

        def project(point):
            x, y = view.project(point)
            return x * r, y * r

        # Uma janela widescreen no plano traseiro do título, recortada pela abertura real.
        rx = 0.73
        half_h = rx * self.h / self.w
        quad = [
            project(view.transform(world(x, y, 1.12)))
            for x, y in (
                (1.03 - rx, -half_h),
                (1.03 + rx, -half_h),
                (1.03 + rx, half_h),
                (1.03 - rx, half_h),
            )
        ]
        progress = smooth((t - 55) / 5.7)
        quad = [
            (x * (1 - progress) + a * progress, y * (1 - progress) + b * progress)
            for (x, y), (a, b) in zip(quad, full)
        ]
        coefficients = perspective_coefficients(quad, full)
        # O fundo interno também é opaco: prédios do outro lado não atravessam o menu.
        background = self.source.transform(
            self.size, Image.Transform.PERSPECTIVE, coefficients, backdrop.RESAMPLE,
            fillcolor=T.BACKGROUND,
        )
        aperture = [
            view.transform(
                world(
                    1.03 + rx * math.cos(i * math.tau / 64),
                    0.91 * math.sin(i * math.tau / 64),
                )
            )
            for i in range(64)
        ]
        aperture = view.clip_face(aperture)
        mask = Image.new("L", self.size, 0)
        if len(aperture) >= 3:
            Draw.Draw(mask).polygon([project(p) for p in aperture], fill=255)
        # Máscara só 0/255 (NEAREST): com alfa parcial o Tk mistura a tela inteira a cada redesenho
        frame = background.resize((self.w, self.h), backdrop.RESAMPLE)
        frame.putalpha(mask.resize((self.w, self.h), getattr(Image, "Resampling", Image).NEAREST))
        return frame

"""Folhas de revisão: 24/32 px reais, silhuetas pretas, cores e arcos da Orbital."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageDraw, ImageFont
import theme as T
from sprites_topview import (
    CYCLES,
    UNIT,
    STRUCTURE_MATERIALS,
    normalized_layers,
    model_bounds,
    render_top,
)


def font(size, bold=False):
    try:
        return ImageFont.truetype(
            "C:/Windows/Fonts/" + ("consolab.ttf" if bold else "consola.ttf"), size
        )
    except OSError:
        return ImageFont.load_default()


def caption(image, xy, value, size=16, color=T.CORE):
    ImageDraw.Draw(image).text(xy, value, font=font(size), fill=color, anchor="mm")


def paste_bike(image, model, center, color, scale=1.0, elapsed=0.0):
    art = render_top(model, color, scale, elapsed=elapsed)
    a, b, c, d = model_bounds(model)
    # A origem lógica está no nariz; a folha centraliza o limite geométrico do modelo.
    cx, cy = (a + c) * UNIT * scale / 2, (b + d) * UNIT * scale / 2
    image.paste(
        art,
        (round(center[0] - art.width / 2 - cx), round(center[1] - art.height / 2 - cy)),
        art,
    )


def silhouette(model, pixels=24):
    a, b, c, d = model_bounds(model)
    scale = (pixels - 1) / (c - a)
    result = Image.new("RGBA", (pixels, pixels))
    paint = ImageDraw.Draw(result)

    def transform(points):
        return [((x - a) * scale, (pixels - 1) / 2 + y * scale) for x, y in points]

    for points, material in normalized_layers(model):
        if material in STRUCTURE_MATERIALS:
            paint.polygon(transform(points), fill="black")
        elif material in ("ring", "support"):
            paint.line(transform(points), fill="black", width=1)
    return result


def main():
    out = Path(__file__).resolve().parents[1] / "previews"
    out.mkdir(exist_ok=True)
    w = 1200
    sheet = Image.new("RGB", (w, 760), T.BACKGROUND)
    caption(sheet, (w / 2, 30), "LIGHT CYCLES / LEITURA EM ESCALA REAL", 24)
    for model, cycle in enumerate(CYCLES):
        x = 110 + model * 196
        caption(sheet, (x, 75), cycle.name, 18, T.CYAN)
        paste_bike(sheet, model, (x, 155), T.CYAN, 3.4)
        for y, size in ((270, 24), (350, 32)):
            a, b, c, d = model_bounds(model)
            scale = size / (UNIT * (c - a))
            # As linhas do chão tornam qualquer transparência indevida visível.
            draw = ImageDraw.Draw(sheet)
            for yy in range(y - 20, y + 21, 5):
                draw.line((x - 70, yy, x + 70, yy), fill=T.GRID)
            paste_bike(sheet, model, (x, y), T.CYAN, scale)
        draw = ImageDraw.Draw(sheet)
        draw.rectangle((model * 196 + 12, 416, model * 196 + 208, 746), fill=T.CORE)
        for y, size in ((456, 24), (514, 32)):
            art = silhouette(model, size)
            sheet.paste(art, (round(x - size / 2), y - size // 2), art)
        art = silhouette(model, 24).resize((144, 144), Image.Resampling.NEAREST)
        sheet.paste(art, (x - 72, 572), art)
    for y, label in ((232, "24 px / 1:1"), (312, "32 px / 1:1")):
        caption(sheet, (w / 2, y), label, 15, T.MUTED)
    caption(
        sheet,
        (w / 2, 425),
        "SILHUETAS: 24 px, 32 px e 24 px ampliados 6×",
        14,
        T.BACKGROUND,
    )
    sheet.save(out / "cycles_readability.png")
    palette = (
        ("CIANO", T.CYAN),
        ("LARANJA", T.ORANGE),
        ("BRANCO", T.CORE),
        ("ROXO", T.PURPLE),
    )
    colors = Image.new("RGB", (1200, 680), T.BACKGROUND)
    caption(colors, (600, 25), "A COR É DO PILOTO / FRENTE À DIREITA", 22)
    for model, cycle in enumerate(CYCLES):
        caption(colors, (168 + model * 181, 64), cycle.name, 16, T.MUTED)
    for row, (name, color) in enumerate(palette):
        y = 138 + row * 142
        caption(colors, (50, y), name, 13, color)
        caption(colors, (50, y + 62), "24/32 px", 11, T.MUTED)
        for model in range(6):
            paste_bike(colors, model, (168 + model * 181, y), color, 3.0)
            a, b, c, d = model_bounds(model)
            for pixels, yy in ((24, y + 48), (32, y + 76)):
                paste_bike(
                    colors,
                    model,
                    (168 + model * 181, yy),
                    color,
                    pixels / (UNIT * (c - a)),
                )
    colors.save(out / "cycles_colors.png")
    frames = []
    for frame in range(80):
        image = Image.new("RGB", (660, 240), T.BACKGROUND)
        caption(image, (330, 26), "ORBITAL / ARCOS INDEPENDENTES / 10 s", 18)
        for i, color in enumerate((T.CYAN, T.ORANGE, T.PURPLE)):
            paste_bike(image, 5, (110 + i * 220, 135), color, 4.0, frame / 8)
        frames.append(image)
    frames[0].save(
        out / "orbital_arcs.gif",
        save_all=True,
        append_images=frames[1:],
        duration=125,
        loop=0,
    )
    print("Generated cycles_readability.png, cycles_colors.png and orbital_arcs.gif")


if __name__ == "__main__":
    main()

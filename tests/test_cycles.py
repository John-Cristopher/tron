"""Regressões de legibilidade, opacidade e animação das motos em escala de jogo."""

import unittest

import theme as T
from sprites_topview import (
    UNIT,
    CYCLES,
    ORBITAL_PERIOD,
    normalized_layers,
    model_bounds,
    centered_origin,
    render_top,
    draw_bike,
    move_bike,
)
from menu_screens import RiderPreview
from test_style import RecordingCanvas

if T.Image is not None:
    from tools.preview_cycles import silhouette


class CycleGeometryTests(unittest.TestCase):
    def test_orbital_moves_its_arcs_without_rotating_body_or_creating_items(self):
        cv = RecordingCanvas()
        items = draw_bike(cv, 100, 100, (1, 0), T.ORANGE, 5)
        body_count = len(items) - 9
        before = [cv.items[item][0] for item in items]
        count = cv.count
        move_bike(cv, items, 5, 100, 100, (1, 0), elapsed=1.0)
        after = [cv.items[item][0] for item in items]
        self.assertEqual(count, cv.count)
        self.assertEqual(before[:body_count], after[:body_count])
        self.assertNotEqual(before[body_count:], after[body_count:])
        move_bike(cv, items, 5, 100, 100, (1, 0), elapsed=ORBITAL_PERIOD)
        for item, old in zip(items, before):
            for a, b in zip(cv.items[item][0], old):
                self.assertAlmostEqual(a, b)

    def test_rotating_previews_stay_in_the_reserved_area_including_the_trail(self):
        for model in range(6):
            for box in ((0, 0, 140, 56), (0, 0, 400, 96)):
                cv = RecordingCanvas()
                preview = RiderPreview(cv, model, T.CYAN, box)
                count = cv.count
                for i in range(81):
                    preview.draw(i / 4)
                    self.assertEqual(cv.count, count)
                    for coords, options in cv.items.values():
                        for x, y in zip(coords[::2], coords[1::2]):
                            self.assertGreaterEqual(x, box[0])
                            self.assertLessEqual(x, box[2])
                            self.assertGreaterEqual(y, box[1])
                            self.assertLessEqual(y, box[3])


@unittest.skipIf(T.Image is None, "Pillow opcional")
class CycleRasterTests(unittest.TestCase):
    def test_24px_black_silhouettes_are_distinct(self):
        masks = [silhouette(model).getchannel("A") for model in range(6)]
        for i, a in enumerate(masks):
            for j, b in enumerate(masks[i + 1 :], i + 1):
                difference = sum(x != y for x, y in zip(a.tobytes(), b.tobytes()))
                self.assertGreater(difference, 12, (CYCLES[i].name, CYCLES[j].name))

    def test_body_remains_opaque_and_dark_in_every_player_color(self):
        sample_points = [
            (-0.55, 0.10),
            (-0.55, 0.09),
            (-0.56, 0.06),
            (-0.55, 0.12),
            (-0.80, 0),
            (-0.58, 0.06),
        ]
        for color in (T.CYAN, T.ORANGE, T.CORE, T.PURPLE):
            for model, (x, y) in enumerate(sample_points):
                image = render_top(model, color, scale=3.0)
                pixel = image.getpixel(
                    (
                        round(image.width / 2 + x * UNIT * 3),
                        round(image.height / 2 + y * UNIT * 3),
                    )
                )
                self.assertEqual(pixel[3], 255, (model, color, pixel))
                self.assertLess(max(pixel[:3]), 55, (model, color, pixel))

    def test_headlight_is_brighter_than_rear_emitter_at_24px(self):
        for model in (0, 5):
            a, b, c, d = model_bounds(model)
            scale = 24 / (UNIT * (c - a))
            for color in (T.CYAN, T.ORANGE, T.CORE, T.PURPLE):
                image = render_top(model, color, scale=scale)

                def light_at(material):
                    points = next(
                        points
                        for points, kind in normalized_layers(model)
                        if kind == material
                    )
                    x = sum(p[0] for p in points) / len(points)
                    px, py = (
                        round(image.width / 2 + x * UNIT * scale),
                        image.height // 2,
                    )
                    pixels = image.crop((px - 1, py - 1, px + 2, py + 2)).convert("RGB")
                    return max(
                        sum(pixel) for pixel in zip(*[iter(pixels.tobytes())] * 3)
                    )

                self.assertGreater(
                    light_at("lamp"), light_at("emitter") + 100, (model, color)
                )


if __name__ == "__main__":
    unittest.main()

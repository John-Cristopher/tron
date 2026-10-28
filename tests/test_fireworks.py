import unittest
from unittest.mock import patch

from effects import Effects
from test_style import RecordingCanvas


class FireworkCanvas(RecordingCanvas):
    def __init__(self):
        super().__init__()
        self.lines = []

    def create_line(self, *coords, **options):
        self.count += 1
        self.items[self.count] = [coords, options]
        self.lines.append(self.count)
        return self.count

    def delete(self, item):
        self.items.pop(item, None)


class FireworkTests(unittest.TestCase):
    def test_wireframe_fireworks_draw_and_animate_the_requested_polyhedra(self):
        shapes = (
            ("octahedron", 12),
            ("dodecahedron", 30),
            ("stellated_octahedron", 12),
        )
        shape_options = (
            "octahedron",
            "dodecahedron",
            "stellated_octahedron",
        )
        for shape, edge_count in shapes:
            with self.subTest(shape=shape):
                canvas = FireworkCanvas()
                effects = Effects(canvas)
                canvas.lines.clear()

                def choose(values):
                    return shape if values == shape_options else values[0]

                with patch("effects.random.random", return_value=0), patch(
                    "effects.random.choice", side_effect=choose
                ):
                    effects.firework(320, 240, "#00FFFF")
                    effects.update(0.36)

                active_lines = [item for item in canvas.lines if item in canvas.items]
                self.assertEqual(len(active_lines), edge_count)
                initial = [canvas.items[item][0] for item in active_lines]
                effects.update(0.4)
                self.assertTrue(
                    any(canvas.items[item][0] != coords
                        for item, coords in zip(active_lines, initial))
                )
                effects.update(0.7)
                self.assertTrue(all(item not in canvas.items for item in active_lines))

    def test_regular_firework_still_uses_radial_rays(self):
        canvas = FireworkCanvas()
        effects = Effects(canvas)
        canvas.lines.clear()
        with patch("effects.random.random", return_value=1):
            effects.firework(320, 240, "#00FFFF")
            effects.update(0.36)
        active_lines = [item for item in canvas.lines if item in canvas.items]
        self.assertEqual(len(active_lines), 18)


if __name__ == "__main__":
    unittest.main()

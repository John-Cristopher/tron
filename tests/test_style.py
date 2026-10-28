"""Regressões de composição e reutilização introduzidas pelos novos sprites."""

import unittest
from unittest.mock import Mock

from chase_mode import CanvasPool, ChaseRenderer
from chase_sim import ChaseSimulation, LightWall
from sprites_topview import draw_bike, move_bike
import theme as T


class RecordingCanvas:
    def __init__(self):
        self.items = {}
        self.count = 0

    def __getattr__(self, name):
        if name.startswith("create_"):

            def create(*coords, **options):
                self.count += 1
                self.items[self.count] = [coords, options]
                return self.count

            return create
        return lambda *args, **kwargs: None

    def coords(self, item, *coords):
        self.items[item][0] = coords

    def itemconfigure(self, item, **options):
        self.items[item][1].update(options)


class StyleTests(unittest.TestCase):
    def test_hidden_pooled_items_return_and_do_not_keep_collision_stipple(self):
        canvas = RecordingCanvas()
        pool = CanvasPool(canvas)
        pool.begin()
        item = pool.rect((0, 0, 10, 10), fill=T.RED, stipple="gray50")
        pool.end()
        pool.begin()
        pool.end()
        self.assertEqual(canvas.items[item][1]["state"], "hidden")
        pool.begin()
        again = pool.rect((0, 0, 20, 20), fill=T.CYAN)
        pool.end()
        self.assertEqual(item, again)
        self.assertEqual(canvas.items[item][1]["stipple"], "")
        self.assertEqual(canvas.items[item][1]["state"], "normal")

    def test_static_pool_avoids_unnecessary_tcl_calls(self):
        canvas = RecordingCanvas()
        pool = CanvasPool(canvas)
        for _ in range(2):
            pool.begin()
            pool.rect((0, 0, 10, 10), fill=T.CYAN)
            pool.end()
            if _ == 0:
                canvas.coords = Mock(wraps=canvas.coords)
                canvas.itemconfigure = Mock(wraps=canvas.itemconfigure)
                canvas.tag_raise = Mock()
        canvas.coords.assert_not_called()
        canvas.itemconfigure.assert_not_called()
        canvas.tag_raise.assert_not_called()

    def test_translucent_wall_does_not_leave_stipple_on_the_next_polygon(self):
        canvas = RecordingCanvas()
        pool = CanvasPool(canvas)
        pool.begin()
        item = pool.polygon((0, 0, 10, 0, 10, 10), fill=T.ORANGE, stipple="gray50")
        pool.end()
        pool.begin()
        pool.polygon((0, 0, 10, 0, 10, 10), fill=T.ASPHALT[0])
        pool.end()
        self.assertEqual(canvas.items[item][1]["stipple"], "")

    def test_foreground_road_never_paints_over_projected_posts(self):
        renderer = ChaseRenderer(RecordingCanvas(), 1280, 720)
        renderer.render(ChaseSimulation())
        options = [renderer.pool.previous[item][1] for item in renderer.pool.order]
        road = [i for i, item in enumerate(options) if item.get("fill") in T.ASPHALT]
        posts = [i for i, item in enumerate(options) if item.get("fill") == T.METAL]
        self.assertTrue(road and posts)
        self.assertLess(max(road), min(posts))

    def test_cinematic_redraw_is_frozen_and_retry_clears_the_particle_pool(self):
        canvas = RecordingCanvas()
        renderer = ChaseRenderer(canvas, 1280, 720)
        sim = ChaseSimulation()
        sim._begin_derez()
        sim._derez_step(2)
        renderer.render(sim)
        before = [(part.x, part.y, part.t) for part in renderer.voxels._all if part.active]
        self.assertTrue(before)
        count = canvas.count
        renderer.render(sim)
        self.assertEqual(before, [(part.x, part.y, part.t) for part in renderer.voxels._all if part.active])
        self.assertEqual(count, canvas.count)
        renderer.render(ChaseSimulation())
        self.assertFalse(renderer.voxels.busy)

    def test_vector_fallback_turns_every_model_without_recreating_items(self):
        for model in range(6):
            canvas = RecordingCanvas()
            items = draw_bike(canvas, 100, 100, (1, 0), T.CYAN, model)
            original = [canvas.items[item][0] for item in items]
            count = canvas.count
            move_bike(canvas, items, model, 100, 100, (0, -1))
            self.assertEqual(canvas.count, count)
            self.assertNotEqual(original, [canvas.items[item][0] for item in items])

    def test_render_covers_bottom_and_survives_effects_appearing_and_disappearing(self):
        canvas = RecordingCanvas()
        renderer = ChaseRenderer(canvas, 1280, 720)
        sim = ChaseSimulation()
        renderer.render(sim)
        self.assertTrue(
            any(
                722 in coords[1::2]
                for coords, options in canvas.items.values()
                if options.get("fill") in T.ASPHALT
            )
        )
        sim.walls.append(LightWall(65, -0.6, "rival", 0, 5))
        sim.player.boost_until = 1
        sim.player.hit_until = 0.9
        renderer.render(sim)
        sim.walls.clear()
        sim.player.boost_until = sim.player.hit_until = 0
        renderer.render(sim)
        count = canvas.count
        renderer.render(sim)
        self.assertEqual(count, canvas.count)

    @unittest.skipIf(T.Image is None, "Pillow opcional não instalado")
    def test_opaque_polygon_occludes_neon_behind_it(self):
        art = T.RasterArt((32, 32), supersample=1)
        art.line([(0, 16), (31, 16)], T.CYAN, 3)
        art.polygon([(8, 8), (24, 8), (24, 24), (8, 24)], T.SHELL)
        result = art.finish(radius=1)
        self.assertEqual(result.getpixel((16, 16))[:3], T.rgb(T.SHELL))


if __name__ == "__main__":
    unittest.main()

"""Tempo, ciclo de vida e densidade da nova abertura e do estádio."""

import random
import unittest
from unittest.mock import Mock, patch

from intro import Intro, T_TITLE_END, T_TITLE_START, terminal_text, LINES, TYPE_TIMES, INTRO_START
from intro_logo import Logo3D, camera_pose, letter_power, contour_pulse
from intro_terminal import REZ_START, REZ_END
from intro_world import IntroWorld, world_blocks, world_camera
import math
from menu_race import AttractSimulation
from menu_stadium import crowd_row, StadiumScene
from test_style import RecordingCanvas
import theme as T


class IntroCanvas(RecordingCanvas):
    def coords(self, item, *coords):
        if coords:
            return super().coords(item, *coords)
        return self.items[item][0]

    itemconfig = RecordingCanvas.itemconfigure


class IntroTests(unittest.TestCase):
    def test_constructing_intro_does_not_reseed_game_randomness(self):
        before = random.getstate()
        Intro(Mock(), Mock(), Mock())
        self.assertEqual(before, random.getstate())

    def test_finish_removes_only_owned_bindings_and_calls_menu_once(self):
        root, canvas, done = Mock(), Mock(), Mock()
        intro = Intro(root, canvas, done)
        intro._key_id, intro._click_id, intro._after_id = "key", "click", "timer"
        intro.running = True
        intro._finish()
        intro._finish()
        done.assert_called_once_with()
        root.after_cancel.assert_called_once_with("timer")
        self.assertEqual(root.unbind.call_count, 2)
        root.unbind.assert_any_call("<Key>", "key")
        root.unbind.assert_any_call("<Button-1>", "click")
        self.assertFalse(intro.running)

    def test_cancel_never_opens_menu(self):
        done = Mock()
        intro = Intro(Mock(), Mock(), done)
        intro.cancel()
        intro.cancel()
        done.assert_not_called()

    def test_repeated_keys_keep_the_original_skip_deadline(self):
        intro = Intro(Mock(), Mock(), Mock())
        intro.running = True
        with patch("intro.time.perf_counter", return_value=12):
            intro._on_key()
        with patch("intro.time.perf_counter", return_value=12.2):
            intro._on_key()
        self.assertEqual(intro.skip_t0, 12)
        self.assertTrue(intro.skipping)

    def test_camera_and_canvas_count_match_across_frame_rates(self):
        states = []
        for fps in (30, 60, 144):
            canvas = IntroCanvas()
            intro = Intro(Mock(), canvas, Mock())
            intro.w, intro.h, intro.horizon = 1280, 720, 302
            intro.focal, intro.cam_y = 648, 1.6
            intro._build_items()
            count = canvas.count
            for i in range(int(T_TITLE_END * fps) + 1):
                intro._update(i / fps)
            self.assertEqual(count, canvas.count)
            states.append(intro.cam_z)
        self.assertAlmostEqual(states[0], states[1])
        self.assertAlmostEqual(states[1], states[2])

    def test_narration_types_slowly_and_finishes_before_the_grid(self):
        self.assertEqual(terminal_text(INTRO_START), "")
        self.assertLess(len(terminal_text(INTRO_START + 2)), 70)
        self.assertEqual(terminal_text(34), "\n".join(LINES))

    def test_typing_has_variable_intervals_and_deliberate_ellipsis_pauses(self):
        intervals=[b-a for a,b in zip(TYPE_TIMES,TYPE_TIMES[1:])]
        self.assertGreater(max(intervals),.5)
        self.assertGreater(len(set(round(i,3) for i in intervals if i<.2)),8)
        self.assertGreater(TYPE_TIMES[-1],31)
        self.assertLess(TYPE_TIMES[-1],REZ_START)

    def test_rez_reveals_world_before_hiding_the_terminal_and_keeps_pool_size(self):
        canvas=IntroCanvas()
        intro=Intro(Mock(),canvas,Mock())
        intro.w,intro.h=1280,720
        intro._build_items()
        count=canvas.count
        intro._update(REZ_START+1)
        self.assertTrue(intro.world.visible)
        self.assertEqual(canvas.items[intro.terminal.panel][1]["state"],"normal")
        self.assertGreater(canvas.items[intro.terminal.panel][0][1],intro.terminal.top)
        self.assertTrue(any(canvas.items[item][1]["state"]=="normal" for item in intro.terminal.cubes))
        intro._update(REZ_END+.1)
        self.assertEqual(canvas.items[intro.term][1]["state"],"hidden")
        self.assertEqual(count,canvas.count)

    def test_neon_letters_ignite_sequentially_then_keep_moving(self):
        self.assertGreater(letter_power(0,0),letter_power(0,3))
        self.assertGreater(letter_power(.5,2),letter_power(.5,3))
        self.assertGreater(letter_power(2,3),.8)
        path=[(0,0),(10,0),(10,10),(0,10)]
        self.assertNotEqual(contour_pulse(path,.1),contour_pulse(path,.3))
        for phase in (.1,.95,1.05):
            self.assertTrue(all(math.isfinite(v) for point in contour_pulse(path,phase) for v in point))

    def test_logo_uses_music_position_even_if_wall_clock_is_far_ahead(self):
        canvas = IntroCanvas()
        position = Mock(return_value=45.999)
        done = Mock()
        intro = Intro(Mock(), canvas, done, timeline=position)
        intro.w, intro.h, intro.horizon = 1280, 720, 302
        intro.focal, intro.cam_y = 648, 1.6
        intro._build_items()
        intro.running = True
        with patch("intro.time.perf_counter", return_value=200):
            intro._tick()
            self.assertFalse(intro.logo3d.visible)
            position.return_value = 46.0
            intro._tick()
        self.assertEqual(T_TITLE_START, 46.0)
        self.assertTrue(intro.logo3d.visible)
        self.assertTrue(intro.running)
        done.assert_not_called()
        self.assertFalse(
            any(
                "ULTIMATE" in str(options.get("text", "")).upper()
                for coords, options in canvas.items.values()
            )
        )

    def test_missing_audio_clock_continues_from_its_last_position(self):
        intro = Intro(Mock(), Mock(), Mock(), timeline=Mock(side_effect=[45.0, None]))
        intro.t0 = 100.0
        with patch("intro.time.perf_counter", return_value=100.0):
            self.assertEqual(intro.elapsed(), 45.0)
        with patch("intro.time.perf_counter", return_value=100.25):
            self.assertEqual(intro.elapsed(), 45.25)

    def test_skip_finishes_even_if_audio_clock_does_not_advance(self):
        intro = Intro(Mock(), Mock(), Mock(), timeline=lambda: 0.0)
        intro.running, intro.skipping, intro.skip_t0 = True, True, 100.0
        intro._update = Mock()
        with patch("intro.time.perf_counter", return_value=101.0):
            intro._tick()
        intro.on_done.assert_called_once()

    def test_near_plane_crossing_reuses_finite_geometry_and_passes_through_o(self):
        canvas = IntroCanvas()
        scene = Logo3D(canvas, 1280, 720)
        count = canvas.count
        for age in (0.0, 2.0, 5.0, 7.0, 7.7, 7.9, 8.0, 8.2, 9.0):
            scene.render(age)
            for coords, options in canvas.items.values():
                self.assertTrue(all(math.isfinite(value) for value in coords))
        self.assertEqual(canvas.count, count)
        x, y, z, yaw, roll = camera_pose(8.2)
        self.assertAlmostEqual(x, 1.03)
        self.assertGreater(z, 1.1)


class IntroWorldTests(unittest.TestCase):
    def test_looking_up_clips_the_floor_instead_of_drawing_a_diagonal_over_the_sky(
        self,
    ):
        canvas = IntroCanvas()
        scene = IntroWorld(canvas, 1280, 720)
        scene.render(42.0)
        self.assertEqual(canvas.items[scene.ground][1]["state"], "normal")
        scene.render(46.0)
        self.assertEqual(canvas.items[scene.ground][1]["state"], "hidden")
        for item in scene.visible_faces:
            coords = canvas.items[item][0]
            self.assertTrue(all(-0.001 <= x <= 1280.001 for x in coords[::2]))
            self.assertTrue(all(-0.001 <= y <= 720.001 for y in coords[1::2]))

    def test_city_blocks_do_not_intersect_in_world_space(self):
        blocks = world_blocks()
        for i, a in enumerate(blocks):
            ax0, ax1, az0, az1 = a.bounds()
            for b in blocks[i + 1 :]:
                bx0, bx1, bz0, bz1 = b.bounds()
                overlap = (
                    min(ax1, bx1) - max(ax0, bx0),
                    min(a.base, b.base) - max(a.base - a.height, b.base - b.height),
                    min(az1, bz1) - max(az0, bz0),
                )
                self.assertFalse(all(length > 1e-8 for length in overlap), (a, b))

    def test_grid_builds_over_several_seconds_and_faces_are_depth_sorted(self):
        canvas = IntroCanvas()
        scene = IntroWorld(canvas, 1280, 720)
        scene.render(36.5)
        early = sum(
            canvas.items[item][1].get("state") == "normal" for item in scene.rows
        )
        scene.render(42.5)
        late = sum(
            canvas.items[item][1].get("state") == "normal" for item in scene.rows
        )
        self.assertGreater(early, 0)
        self.assertLess(early, len(scene.rows) / 2)
        self.assertGreater(late, early)
        self.assertEqual(scene.last_depths, sorted(scene.last_depths, reverse=True))

    def test_camera_has_no_cut_at_the_title_cue_and_looks_up(self):
        before = world_camera(45.9999, 1280, 720)
        after = world_camera(46.0, 1280, 720)
        landmark = (8.0, -10.0, 220.0)
        a, b = before.project(before.transform(landmark)), after.project(
            after.transform(landmark)
        )
        self.assertLess(math.dist(a, b), 0.05)
        self.assertGreater(after.pitch, world_camera(42.0, 1280, 720).pitch)
        self.assertGreater(world_camera(61.5, 1280, 720).z, 192.53)

    def test_terminal_preserves_english_prompts_and_uses_amber_cli(self):
        canvas = IntroCanvas()
        intro = Intro(Mock(), canvas, Mock())
        intro.w, intro.h = 1280, 720
        intro._build_items()
        intro._update(34.0)
        text = canvas.items[intro.term][1]["text"]
        self.assertTrue(all(line.startswith("> ") for line in text.splitlines()))
        labels = [options.get("text", "") for coords, options in canvas.items.values()]
        self.assertNotIn("File   Edit   View   Terminal   Tabs   Help", labels)
        self.assertIn("ENCOM OS  //  FLYNN ARCHIVE", labels)
        r,g,b=T.rgb(canvas.items[intro.term][1]["fill"])
        self.assertGreater(r,b*1.5)
        self.assertGreater(g,b)
        intro._update(INTRO_START + 4)
        self.assertEqual(canvas.items[intro.hint][1]["state"],"hidden")

    def test_shared_world_keeps_its_geometry_through_the_reveal_and_traversal(self):
        canvas = IntroCanvas()
        intro = Intro(Mock(), canvas, Mock())
        intro.w, intro.h = 1280, 720
        intro._build_items()
        count = canvas.count
        blocks = list(intro.world.blocks)
        for t in (35.0, 39.0, 43.0, 45.99, 46.0, 48.0, 52.0, 58.0, 60.7, 61.5, 62.0):
            intro._update(t)
            self.assertEqual(count, canvas.count)
            self.assertEqual(blocks, intro.world.blocks)
            for coords, options in canvas.items.values():
                self.assertTrue(all(math.isfinite(value) for value in coords))
        self.assertTrue(intro.world.visible)
        self.assertFalse(hasattr(intro, "logo_back"))


class CrowdTests(unittest.TestCase):
    def test_people_scale_with_projected_seat_spacing(self):
        near = crowd_row((10, 20), (610, 420), 36, rng=random.Random(4))
        far = crowd_row((10, 20), (310, 220), 36, rng=random.Random(4))
        self.assertEqual(len(near), len(far))
        for a, b in zip(near, far):
            self.assertAlmostEqual(a[2], b[2] * 2)

    def test_animated_crowd_is_bounded_and_geometry_is_reused(self):
        canvas = RecordingCanvas()
        scene = StadiumScene(canvas, lambda x, y, z=0: (x, y - z, 2), 1280, 720)
        scene.draw(live=True)
        self.assertGreater(len(scene.people), 400)
        self.assertLessEqual(len(scene.active), 64)
        self.assertLess(len(scene.active), len(scene.people) * 0.16)
        count = canvas.count
        for i in range(60):
            scene.animate(i / 60)
        self.assertEqual(count, canvas.count)


class DemoTests(unittest.TestCase):
    def test_race_is_independent_of_render_rate(self):
        states = []
        for fps in (30, 60, 144):
            sim = AttractSimulation()
            for _ in range(fps * 20):
                sim.advance(1 / fps)
            states.append(
                (
                    sim.round,
                    sim.occupied,
                    [(b.cell, b.alive, b.direction) for b in sim.bikes],
                )
            )
        self.assertEqual(states[0], states[1])
        self.assertEqual(states[1], states[2])

    def test_no_available_turn_causes_elimination_then_new_round(self):
        sim = AttractSimulation()
        sim.occupied = {(x, y) for x in range(sim.width) for y in range(sim.height)}
        sim.advance(0.1)
        self.assertFalse(any(bike.alive for bike in sim.bikes))
        for _ in range(120):
            sim.advance(1 / 60)
        self.assertEqual(sim.round, 2)
        self.assertTrue(all(bike.alive for bike in sim.bikes))


class SpatialNavigationTests(unittest.TestCase):
    # Caixas reais da tela de modos e dos pilotos em 1536x864.
    MODES = {
        "1v1": (32, 144, 512, 408), "ffa4": (528, 144, 1008, 408), "team": (1024, 144, 1504, 408),
        "training": (32, 424, 512, 688), "rinzler": (528, 424, 1008, 688), "chase": (1024, 424, 1504, 688),
        "back": (480, 712, 760, 760), "next": (776, 712, 1056, 760),
    }
    RIDERS = {
        "tab": (32, 72, 512, 120), "color1": (56, 368, 388, 416), "model1": (56, 616, 380, 664),
        "color2": (420, 368, 752, 416), "model2": (420, 616, 744, 664),
        "back": (480, 712, 760, 760), "start": (776, 712, 1056, 760),
    }

    def test_moves_to_the_nearest_item_in_each_direction(self):
        from menu_screens import spatial_neighbor as go
        self.assertEqual(go(self.MODES, "1v1", 0, 1), "training")
        self.assertEqual(go(self.MODES, "1v1", 1, 0), "ffa4")
        self.assertEqual(go(self.MODES, "rinzler", 0, -1), "ffa4")
        self.assertEqual(go(self.MODES, "training", 0, 1), "back")
        self.assertEqual(go(self.MODES, "back", 1, 0), "next")
        self.assertEqual(go(self.RIDERS, "color1", 1, 0), "color2")
        self.assertEqual(go(self.RIDERS, "color1", 0, 1), "model1")
        self.assertEqual(go(self.RIDERS, "model2", 0, 1), "back")
        self.assertEqual(go(self.RIDERS, "color1", 0, -1), "tab")

    def test_wraps_within_the_same_row_or_column(self):
        from menu_screens import spatial_neighbor as go
        self.assertEqual(go(self.MODES, "team", 1, 0), "1v1")
        self.assertEqual(go(self.MODES, "1v1", -1, 0), "team")
        self.assertIsNone(go({"a": (0, 0, 10, 10), "b": (50, 50, 60, 60)}, "a", -1, 0))


if __name__ == "__main__":
    unittest.main()

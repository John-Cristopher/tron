"""A janela do menu mantém perspectiva e recorte durante a travessia."""

import unittest
from unittest.mock import Mock

import backdrop
from intro_portal import IntroPortal, perspective_coefficients
from intro_world import world_camera


class PortalTests(unittest.TestCase):
    def test_inverse_perspective_maps_each_corner_to_the_source(self):
        screen = [(80, 50), (300, 30), (360, 240), (30, 210)]
        source = [(0, 0), (1280, 0), (1280, 720), (0, 720)]
        a, b, c, d, e, f, g, h = perspective_coefficients(screen, source)
        for (x, y), (u, v) in zip(screen, source):
            denominator = g * x + h * y + 1
            self.assertAlmostEqual((a * x + b * y + c) / denominator, u)
            self.assertAlmostEqual((d * x + e * y + f) / denominator, v)

    @unittest.skipUnless(backdrop.AVAILABLE, "Pillow opcional")
    def test_portal_is_transparent_outside_o_then_fills_the_screen(self):
        portal = IntroPortal(Mock(), 320, 180)
        portal.w, portal.h = 320, 180
        portal.ratio, portal.size = 1.0, (320, 180)
        portal.source = portal.full_source = backdrop.Image.new(
            "RGBA", portal.size, "cyan"
        )
        early = portal.frame(54, world_camera(54, 320, 180))
        self.assertEqual(early.getpixel((0, 0))[3], 0)
        self.assertIsNotNone(early.getchannel("A").getbbox())
        late = portal.frame(61.8, world_camera(61.8, 320, 180))
        self.assertEqual(late.getchannel("A").getextrema(), (255, 255))
        self.assertEqual(late.tobytes(), portal.source.tobytes())


if __name__ == "__main__":
    unittest.main()

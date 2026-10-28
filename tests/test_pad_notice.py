import unittest
from unittest.mock import Mock, patch

from intro import IntroFrame
from tron_light_cycle import LightCycleGame, MainMenu


class PadNoticeTests(unittest.TestCase):
    def make_game(self, frame, menu_from_intro):
        game = LightCycleGame.__new__(LightCycleGame)
        game.current_frame = frame
        game.menu_from_intro = menu_from_intro
        game.pad_notice = None
        game.pad_notice_connected = False
        game.pending_pad_notice = None
        game.sync_pad_leds = Mock()
        game.show_pad_notice = Mock()
        game.pads = Mock()
        game.pads.poll.return_value = [(0, "changed", True)]
        game.pads.ok = False
        game.root = Mock()
        return game

    def test_connection_during_intro_is_deferred_until_the_menu(self):
        frame = IntroFrame.__new__(IntroFrame)
        game = self.make_game(frame, False)

        with patch("tron_light_cycle.INPUT.sync"):
            game.poll_pads()

        self.assertEqual(game.pending_pad_notice, 0)
        game.show_pad_notice.assert_not_called()

    def test_connection_notice_is_shown_on_the_menu_after_intro(self):
        frame = MainMenu.__new__(MainMenu)
        frame.on_inputs_changed = Mock()
        game = self.make_game(frame, True)

        with patch("tron_light_cycle.INPUT.sync"):
            game.poll_pads()

        game.show_pad_notice.assert_called_once_with(0, connected=True)
        self.assertIsNone(game.pending_pad_notice)

    def test_connection_notice_is_suppressed_outside_the_post_intro_menu(self):
        frame = object()
        game = self.make_game(frame, True)

        with patch("tron_light_cycle.INPUT.sync"):
            game.poll_pads()

        game.show_pad_notice.assert_not_called()
        self.assertIsNone(game.pending_pad_notice)


if __name__ == "__main__":
    unittest.main()

"""Roteamento dos clipes personalizados e ciclo de vida do motor, sem reproduzir áudio."""

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch, call

from chase_mode import ChaseAudio
from chase_sim import Controls
from sound import SoundManager, effect_files


class ChaseAudioTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.manager = SimpleNamespace(
            backend="pygame",
            sfx_on=True,
            sfx_level=0.5,
            pg=Mock(),
            play=Mock(),
            _sounds={"go": Mock()},
        )
        self.manager.pg.mixer.Sound.side_effect = lambda path: Mock(
            name=Path(path).stem
        )
        self.channel = self.manager.pg.mixer.Channel.return_value
        self.channel.get_busy.return_value = True
        for filename in (
            "motoluz_parada.wav",
            "motoluz_acelerando.wav",
            "motoluz_ligando.wav",
            "motolu_zfreio.wav",
            "virar_01.WAV",
            "virar_02.WAV",
            "virar_03.WAV",
            "wall_on.wav",
            "impact.wav",
            "deresolucao.WAV",
        ):
            (self.directory / filename).touch()
        self.audio = ChaseAudio(self.manager, (self.directory,))

    def test_portuguese_names_and_uppercase_extensions_are_loaded(self):
        self.assertEqual(len(self.audio.loaded_files), 10)
        self.assertEqual(
            Path(self.audio.loaded_files["brake"]).name, "motolu_zfreio.wav"
        )
        self.assertIn("turn_03", self.audio.sounds)
        self.assertIn("lose", self.audio.sounds)

    def test_engine_switches_with_throttle_and_start_does_not_repeat_on_resume(self):
        self.audio.update(0, True, Controls())
        self.assertIs(self.channel.play.call_args.args[0], self.audio.sounds["engine"])
        self.audio.update(80, True, Controls(throttle=1))
        self.assertIs(
            self.channel.play.call_args.args[0], self.audio.sounds["accelerate"]
        )
        self.audio.update(80, True, Controls(throttle=1))
        self.assertEqual(self.channel.play.call_count, 2)
        self.audio.update(80, False)
        self.channel.stop.assert_called_once()
        self.audio.update(0, True, Controls())
        self.audio.sounds["start"].play.assert_called_once()
        self.audio.close()
        self.manager.pg.mixer.set_reserved.assert_called_with(3)

    def test_held_controls_do_not_stack_braking_or_turning_sounds(self):
        for _ in range(20):
            self.audio.update(60, True, Controls(steer=1, brake=1))
        self.audio.sounds["brake"].play.assert_called_once()
        self.audio.sounds["turn_01"].play.assert_called_once()
        self.audio.update(60, True, Controls())
        self.audio.update(60, True, Controls(steer=-1))
        self.audio.update(60, True, Controls(steer=1))
        self.audio.sounds["turn_02"].play.assert_called_once()
        self.audio.sounds["turn_03"].play.assert_called_once()

    def test_missing_effects_use_sound_manager_and_mute_stops_engine(self):
        for event, fallback in (
            ("boost", "go"),
            ("wall_warning", "beep"),
            ("win", "match_win"),
        ):
            self.audio.event(event)
            self.manager.play.assert_called_with(fallback)
        self.audio.update(80, True, Controls(throttle=1))
        self.manager.sfx_on = False
        self.audio.update(80, True, Controls(throttle=1))
        self.channel.stop.assert_called_once()
        before = self.manager.play.call_count
        self.audio.event("win")
        self.assertEqual(before, self.manager.play.call_count)

    def test_result_sound_is_not_cut_off_when_running_stops(self):
        self.audio.update(70, True)
        self.audio.event("lose")
        self.audio.update(70, False)
        self.audio.sounds["lose"].play.assert_called_once()
        self.audio.sounds["lose"].stop.assert_not_called()

    def test_engine_volume_is_independent_from_other_effects(self):
        self.manager.engine_level = 0.0
        self.audio.update(120, True)
        self.channel.set_volume.assert_called_with(0.0)
        self.audio.event("brake")
        self.audio.sounds["brake"].set_volume.assert_called_with(0.5 * 0.65)

    def test_corrupt_preferred_effect_tries_next_format(self):
        (self.directory / "boost.ogg").touch()
        (self.directory / "boost.WAV").touch()

        def decode(path):
            if path.endswith("boost.ogg"):
                raise ValueError("invalid audio")
            return Mock()

        self.manager.pg.mixer.Sound.side_effect = decode
        audio = ChaseAudio(self.manager, (self.directory,))
        self.assertEqual(Path(audio.loaded_files["boost"]).name, "boost.WAV")


class MenuAudioTests(unittest.TestCase):
    def manager_with_intro(self):
        with patch.object(SoundManager, "_ensure_files"), patch.object(
            SoundManager, "_init_backend"
        ):
            manager = SoundManager()
        manager.backend = "pygame"
        manager.pg = Mock()
        manager.pg.mixer.music.get_busy.return_value = True
        manager.pg.mixer.music.get_pos.return_value = 99500
        manager._active_music = manager._current_music = "intro"
        manager._music_phase = "playing"
        manager._music_duration_ms = 100075
        manager._start_music_track = Mock()
        return manager

    def test_menu_keeps_intro_running_without_fading_the_final_notes(self):
        manager = self.manager_with_intro()
        manager.enter_menu_music(preserve_intro=True)
        manager.enter_menu_music()
        manager.update_music()
        self.assertTrue(manager._intro_menu_tail)
        self.assertEqual(manager._music_phase, "playing")
        self.assertEqual(manager._current_music, "intro")
        manager.pg.mixer.music.stop.assert_not_called()
        manager._start_music_track.assert_not_called()

    def test_natural_intro_end_starts_menu_playlist(self):
        manager = self.manager_with_intro()
        manager.enter_menu_music(preserve_intro=True)
        manager.pg.mixer.music.get_busy.return_value = False
        manager.update_music()
        self.assertFalse(manager._intro_menu_tail)
        self.assertEqual(manager._current_music, "menu")
        manager._start_music_track.assert_called_once_with("menu")

    def test_launching_a_game_does_not_wait_for_the_intro_to_finish(self):
        manager = self.manager_with_intro()
        manager.enter_menu_music(preserve_intro=True)
        manager.set_music_track("game")
        self.assertFalse(manager._intro_menu_tail)
        self.assertEqual(manager._current_music, "game")
        self.assertEqual(manager._music_phase, "fade_out")

    def test_intro_track_starts_at_zero_without_menu_transition(self):
        manager = SoundManager.__new__(SoundManager)
        manager.pg = Mock()
        manager.backend, manager.music_on = "pygame", True
        manager._music_positions = {"intro": (0, 46000)}
        manager._music_remaining = {"intro": [0]}

        def started(*args, **kwargs):
            manager._active_music = "intro"

        manager._start_music_track = Mock(side_effect=started)
        self.assertTrue(manager.start_intro_music(20.0))
        manager.pg.mixer.music.stop.assert_called_once()
        manager._start_music_track.assert_called_once_with(
            "intro", index=0, position_ms=20000
        )
        self.assertNotIn("intro", manager._music_positions)
        manager.pg.mixer.music.get_busy.return_value = True
        manager.pg.mixer.music.get_pos.return_value = 26000  # 20 s de início + 26 s tocados
        self.assertEqual(manager.intro_position(), 46.0)

    def test_legacy_open_is_an_independent_non_looping_playlist(self):
        with TemporaryDirectory() as directory, patch(
            "sound.SOUND_DIR", directory
        ), patch("sound.MUSIC_DIR", directory), patch("builtins.print"):
            (Path(directory) / "01 - Legacy Open.mp3").touch()
            manager = SoundManager.__new__(SoundManager)
            manager._paths = {"music": "music.wav", "menu_music": "menu_music.wav"}
            lists = manager._resolve_music_playlists()
            self.assertEqual(lists["intro"][0][0][0], "Legacy Open")
            self.assertFalse(lists["intro"][2])
            self.assertNotIn(lists["intro"][0][0], lists["game"][0])

    def test_file_lookup_accepts_uppercase_and_prefers_ogg(self):
        with TemporaryDirectory() as directory:
            for name in ("menu.WAV", "MENU.ogg", "seletor_menu.WAV"):
                (Path(directory) / name).touch()
            files = list(effect_files(directory, ("menu",)))
            self.assertEqual([path.name for path in files], ["MENU.ogg", "menu.WAV"])

    def test_bad_menu_clip_falls_back_without_disabling_other_effects(self):
        manager = SoundManager.__new__(SoundManager)
        manager.pg = Mock()
        manager._paths = {"move": "move.wav", "menu_move": "bad.WAV", "go": "go.wav"}
        manager._crowd_mp3_paths = {}

        def decode(path):
            if path == "bad.WAV":
                raise ValueError("invalid audio")
            return Mock()

        manager.pg.mixer.Sound.side_effect = decode
        manager._load_effects()
        self.assertEqual(manager._paths["menu_move"], "move.wav")
        self.assertIn("go", manager._sounds)

    def test_menu_sounds_share_reserved_channel_instead_of_overlapping(self):
        manager = SoundManager.__new__(SoundManager)
        manager.pg = Mock()
        manager.backend, manager.sfx_on = "pygame", True
        manager._paths = {"menu_move": "seletor_menu.WAV", "menu_select": "menu.WAV"}
        manager._sounds = {key: Mock() for key in manager._paths}
        manager._last_play = {}
        manager.play("menu_move")
        manager.play("menu_select")
        self.assertEqual(manager.pg.mixer.Channel.call_args_list, [call(0), call(0)])
        channel = manager.pg.mixer.Channel.return_value
        self.assertEqual(channel.play.call_count, 2)

    def test_firework_uses_each_available_custom_variant(self):
        manager = SoundManager.__new__(SoundManager)
        manager.backend, manager.sfx_on = "pygame", True
        manager._paths = {
            "firework": "firework.wav",
            **{
                f"firework_{index}": f"firework_{index}.mp3"
                for index in range(1, 4)
            },
        }
        manager._sounds = {
            name: Mock() for name in manager._paths
        }
        manager._last_play = {}
        manager._crowd_channels = {}
        manager.pg = Mock()

        for index in range(1, 4):
            name = f"firework_{index}"
            with patch("sound.random.choice", return_value=name):
                manager.play("firework")
            manager._sounds[name].play.assert_called_once_with()
        manager._sounds["firework"].play.assert_not_called()

    def test_missing_chase_music_reuses_game_but_explicit_track_wins(self):
        with TemporaryDirectory() as directory, patch(
            "sound.SOUND_DIR", directory
        ), patch("sound.MUSIC_DIR", directory), patch("builtins.print"):
            (Path(directory) / "05 - Motochase.mp3").touch()
            manager = SoundManager.__new__(SoundManager)
            manager._paths = {"music": "music.wav", "menu_music": "menu_music.wav"}
            lists = manager._resolve_music_playlists()
            self.assertEqual(lists["chase"][0], lists["game"][0])
            (Path(directory) / "chase.ogg").touch()
            lists = manager._resolve_music_playlists()
            self.assertEqual([name for name, path in lists["chase"][0]], ["chase"])


if __name__ == "__main__":
    unittest.main()

"""Capturas reais e auditoria de áreas úteis, teclado, mouse e controle."""

from pathlib import Path
import sys
import tkinter as tk
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.preview_capture import capture_window
import tron_light_cycle as game
from preview_chase import SilentSound, NoPads


def main():
    root = tk.Tk()
    root.maxsize(4096, 2160)
    root.geometry("1366x768+0+0")
    errors = []
    root.report_callback_exception = lambda *args: errors.append(args)
    with patch.object(game, "SoundManager", SilentSound), patch.object(
        game, "GamepadManager", NoPads
    ), patch.object(root, "attributes"):
        app = game.LightCycleGame(root, play_intro=False)
    out = Path("previews")
    out.mkdir(exist_ok=True)
    for w, h in ((1366, 768), (800, 600), (1920, 1080)):
        root.geometry(f"{w}x{h}+0+0")
        app.screen_width, app.screen_height = w, h
        app.show_menu("title")
        menu = app.current_frame
        menu.after_cancel(menu.after_id)
        menu.after_id = None

        def snap(name):
            root.update_idletasks()
            capture_window(root).save(out / f"ui_{name}_{w}x{h}.png")

        def audit():
            root.update_idletasks()
            assert (menu.cv.winfo_width(), menu.cv.winfo_height()) == (w, h)
            for key, box in menu.focus_boxes.items():
                assert 0 <= box[0] < box[2] <= w, (w, h, key, box)
                assert 0 <= box[1] < box[3] < menu.layout.help_y - 16, (w, h, key, box)
                if (
                    menu.page == "setup"
                    and key not in ("config_level", "back", "start")
                    and not (isinstance(key, tuple) and key[0] == "setup_step")
                ):
                    content = menu.layout.content
                    assert content[1] <= box[1] and box[3] <= content[3], (
                        w,
                        h,
                        key,
                        box,
                        content,
                    )
            actions = [
                menu.focus_boxes[k] for k in ("back", "start") if k in menu.focus_boxes
            ]
            for box in actions:
                assert box[1] >= menu.layout.content[3] + 16

        snap("title")
        audit()
        menu.show_options()
        menu.apply_blur(1)
        snap("options")
        audit()
        menu.show_modes()
        snap("modes")
        audit()
        menu.mode = "training"
        menu.advanced_config = True
        menu.training_player_count = 4
        menu.training_human_count = 4
        menu.show_setup()
        for step in ("arena", "rules", "riders"):
            menu.set_setup_step(step)
            menu.apply_blur(1)
            audit()
            snap(step)
        menu.training_human_count = 1
        menu.model_idx = {1: 0, 2: 2, 3: 4, 4: 5}
        menu.draw_ui()
        for elapsed in (0.0, 4.0, 8.0):
            for preview in menu.rider_previews:
                preview.draw(elapsed)
            snap(f"riders_ai_{int(elapsed)}s")
        orbital = menu.rider_previews[-1]
        body_photo = orbital.items.photo
        cache_count = len(menu.cv._cycle_sprites)
        ring_coords = menu.cv.coords(orbital.items.rings[0][0])
        count = len(menu.cv.find_all())
        for tick in range(60):
            orbital.draw(8 + tick / 60)
        assert len(menu.cv.find_all()) == count
        assert orbital.items.photo is body_photo
        assert len(menu.cv._cycle_sprites) == cache_count
        assert menu.cv.coords(orbital.items.rings[0][0]) != ring_coords
        menu.set_setup_step("rules")
        menu.set_focus("training_players")
        menu.on_key(SimpleNamespace(keysym="Left"))
        assert menu.training_player_count == 3
        menu.on_key(SimpleNamespace(keysym="e"))
        assert menu.setup_step == "riders"
        menu.mode = "team2v2"
        menu.draw_ui()
        audit()
        snap("teams")
        menu.set_focus(("team_color", 1))
        menu.navigate(1, 0)
        menu.activate()
        assert menu.rgb is not None
        menu.rgb_close(False)
        color_control = menu.ui.controls[("team_color", 1)]
        color_control.clicked(
            SimpleNamespace(x=(color_control.box[0] + color_control.box[2]) / 2)
        )
        assert menu.rgb is not None
        menu.rgb_close(False)
        menu.on_pad(1, "button", "lb")
        assert menu.setup_step == "rules"
        print(f"Layout, input and RGB OK: {w}x{h}", flush=True)
    old_binding = menu._key_binding_id
    menu.show_options()
    menu.ui.controls["replay_intro"].invoke()
    root.update_idletasks()
    assert isinstance(app.current_frame, game.IntroFrame)
    assert old_binding not in root.bind("<KeyPress>")
    app.on_escape()
    assert app.current_frame.intro.skipping
    print("Replay intro cleans menu bindings OK", flush=True)
    # Exercita a animação na arena real, com quatro cores e quatro orientações.
    root.geometry("1366x768+0+0")
    app.screen_width, app.screen_height = 1366, 768
    app.start_game("ffa4", dict(app.colors), {pid: 5 for pid in (1, 2, 3, 4)}, 0)
    arena = app.current_frame
    root.update_idletasks()
    arena.render_riders(alpha=1.0)
    before = [
        arena.canvas.coords(rider.bike.rings[0][0]) for rider in arena.riders.values()
    ]
    photos = [rider.bike.photo for rider in arena.riders.values()]
    count = len(arena.canvas.find_all())
    for tick in range(60):
        arena.sim_time = tick / 60
        arena.render_riders(alpha=1.0)
    assert len(arena.canvas.find_all()) == count
    assert photos == [rider.bike.photo for rider in arena.riders.values()]
    assert before != [
        arena.canvas.coords(rider.bike.rings[0][0]) for rider in arena.riders.values()
    ]
    root.update_idletasks()
    capture_window(root).save(out / "cycles_arena_orbital.png")
    print(
        "Four Orbital bikes animate in the live arena without rebuilding sprites OK",
        flush=True,
    )
    app.clear_screen()
    app.current_frame = None
    root.after_cancel(app.music_after_id)
    root.destroy()
    assert not errors, errors


if __name__ == "__main__":
    main()

"""Captura as fases da introdução e o estádio sem reproduzir áudio."""

from pathlib import Path
import sys
import time
import tkinter as tk
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.preview_capture import capture_window
import tron_light_cycle as game
from intro import IntroFrame, T_TITLE_END
from preview_chase import SilentSound, NoPads
import backdrop
import theme as T


def main():
    root = tk.Tk()
    root.geometry("1280x720+20+20")
    output = Path(__file__).resolve().parents[1] / "previews"
    output.mkdir(exist_ok=True)
    errors = []

    def report(kind, value, tb):
        errors.append(value)
        import traceback

        traceback.print_exception(kind, value, tb)

    root.report_callback_exception = report

    def pump():
        deadline = time.perf_counter() + 0.15
        for _ in range(80):
            if time.perf_counter() > deadline or not root.tk.dooneevent(2):
                break

    def snapshot(name):
        root.update_idletasks()
        capture_window(root).save(output / name)
        print(name, flush=True)

    with patch.object(game, "SoundManager", SilentSound), patch.object(
        game, "GamepadManager", NoPads
    ), patch.object(root, "attributes"):
        app = game.LightCycleGame(root)
    app.screen_width, app.screen_height = 1280, 720
    pump()
    frame = app.current_frame
    assert isinstance(frame, IntroFrame)
    intro = frame.intro
    root.after_cancel(intro._after_id)
    intro._after_id = None
    old_binding = intro._key_id
    intro_count = len(intro.c.find_all())
    for t, name in (
        (27.0, "intro_terminal.png"),
        (36.5, "intro_laser.png"),
        (39.0, "intro_grid_building.png"),
        (42.0, "intro_grid.png"),
        (44.5, "intro_look_up.png"),
        (45.9, "intro_before_title.png"),
        (46.0, "intro_title_46s.png"),
        (48.0, "intro_title.png"),
        (54.0, "intro_enter.png"),
        (58.0, "intro_portal.png"),
        (60.7, "intro_portal_entry.png"),
        (61.8, "intro_menu_arrival.png"),
    ):
        intro._update(t)
        assert len(intro.c.find_all()) == intro_count
        snapshot(name)
    intro.t0 = time.perf_counter() - T_TITLE_END - 0.2
    intro._tick()
    assert app.current_frame.page == "title"
    assert old_binding not in root.bind("<Key>")
    menu = app.current_frame
    menu.after_cancel(menu.after_id)
    menu.after_id = None
    for age,name in ((0,"menu_arrival"),(.5,"menu_buttons"),(1.5,"menu_crowd"),(2.3,"menu_ready")):
        menu.t=age
        menu.update_arrival(age)
        menu.stadium_scene.animate(age)
        if age==0:
            assert not any(button.visible for button in menu.ui.controls.values())
            assert not any(menu.stadium_scene.row_visibility.values())
        elif age==.5:
            assert menu.ui.controls["play"].visible
            assert not menu.ui.controls["exit"].visible
        elif age==1.5:
            assert menu.stadium_scene.row_visibility[0]
            assert not menu.stadium_scene.row_visibility[5]
        else:
            assert all(button.visible for button in menu.ui.controls.values())
            assert all(menu.stadium_scene.row_visibility.values())
            assert not menu.arrival_active
        snapshot(name+".png")
    menu.arrival_active=True
    menu.update_arrival(0)
    menu.navigate(0,1)
    assert not menu.arrival_active and menu.focus=="chase"
    assert all(button.visible for button in menu.ui.controls.values())
    menu.navigate(0,-1)
    menu.fx.update(1.3)
    cx = menu.W / 2
    y = menu.cv.coords(menu.title_line)[1]
    menu.cv.coords(menu.title_line, cx - 260, y, cx + 260, y)
    for _ in range(60 * 4):
        menu.menu_race.sim.advance(1 / 60)
    menu.menu_race.render()
    menu.stadium_scene.animate(4)
    snapshot("menu_title.png")
    timings = []
    for i in range(90):
        started = time.perf_counter()
        menu.menu_race.advance(1 / 60)
        menu.stadium_scene.animate(4 + i / 60)
        timings.append((time.perf_counter() - started) * 1000)
    print(
        f"Menu simulation + Canvas calls: mean={sum(timings)/len(timings):.2f} ms max={max(timings):.2f} ms",
        flush=True,
    )
    assert len(menu.cv.find_withtag("focus_mark")) == 4
    assert menu.cv.type(menu.focus_rect) == "line"
    assert menu.stadium_scene.photo is not None
    print(
        "Crowd:",
        len(menu.stadium_scene.people),
        "animated:",
        len(menu.stadium_scene.active),
        flush=True,
    )
    for _ in range(20):
        menu.menu_race.render()
    count = len(menu.cv.find_all())
    for _ in range(20):
        menu.menu_race.render()
    assert count == len(menu.cv.find_all())
    menu.show_modes()
    menu.apply_blur(1)
    snapshot("menu_selection.png")
    menu.show_title()
    menu.apply_blur(0)
    menu.menu_race.render()
    snapshot("menu_return.png")
    # O botão que pula a introdução não aciona INICIAR no mesmo evento.
    app.clear_screen()
    frame = app.current_frame = IntroFrame(root, app)
    pump()
    frame.on_pad(1, "button", "a")
    assert frame.intro.skipping
    frame.intro.skip_t0 -= 0.4
    frame.intro._tick()
    assert app.current_frame.page == "title"
    for source in ("key", "click", "escape"):
        app.clear_screen()
        frame = app.current_frame = IntroFrame(root, app)
        pump()
        if source == "escape":
            app.on_escape()
        else:
            frame.intro._on_key()
        assert frame.intro.skipping
        frame.intro.skip_t0 -= 0.4
        if frame.intro._after_id is not None:
            root.after_cancel(frame.intro._after_id)
        frame.intro._tick()
        assert app.current_frame.page == "title"
    # Atalhos específicos R e Esc também pulam, e sair cancela a introdução.
    app.clear_screen()
    frame = app.current_frame = IntroFrame(root, app)
    pump()
    app.reset_match()
    assert frame.intro.skipping
    app.clear_screen()
    # A alternativa vetorial continua navegável sem Pillow e sem imagens de fundo.
    app.current_frame = None
    with patch.object(backdrop, "AVAILABLE", False), patch.object(T, "Image", None):
        app.show_menu("title")
        menu = app.current_frame
        menu.show_modes()
        menu.apply_blur(1)
        menu.show_title()
        menu.apply_blur(0)
        menu.step_demo(0.05)
        app.clear_screen()
    # Confere também um viewport menor, com a mesma geometria e controles.
    app.current_frame = None
    root.geometry("800x600+20+20")
    app.screen_width, app.screen_height = 800, 600
    app.show_menu("title")
    menu = app.current_frame
    menu.fx.update(1.3)
    menu.navigate(0, 1)
    assert menu.focus == "chase"
    menu.navigate(0, -1)
    assert menu.focus == "play"
    snapshot("menu_compact.png")
    app.clear_screen()
    app.current_frame = None
    root.after_cancel(app.music_after_id)
    root.destroy()
    if errors:
        raise RuntimeError(errors)
    print("Intro/menu GUI smoke OK", flush=True)


if __name__ == "__main__":
    main()

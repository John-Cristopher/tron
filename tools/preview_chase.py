"""Prévia e smoke test visual (abre janela; não reproduz áudio)."""

from pathlib import Path
import sys
import time
from unittest.mock import patch
import tkinter as tk

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.preview_capture import capture_window
import tron_light_cycle as game
from chase_sim import Controls
from effects import BIKES
from sprites_topview import draw_bike
from sprites_topview import move_bike
from rider_rear import RearSprites
from chase_mode import CanvasPool
import theme as T


class SilentSound:
    backend = "none"
    music_level = sfx_level = engine_level = 1.0
    _sounds = {}
    sfx_on = True

    def __getattr__(self, name):
        return lambda *a, **k: None


class NoPads:
    count = 0
    connected = False
    ok = False

    def poll(self):
        return []

    def shutdown(self):
        pass

    def driving_state(self, index=0):
        return dict(steer=0, throttle=0, brake=0, boost=False, wall=False)


def main():
    print("Preparando menu", flush=True)
    root = tk.Tk()

    def pump():
        # update() pode nunca retornar quando há animações e repinturas contínuas.
        deadline = time.perf_counter() + 0.2
        for _ in range(100):
            if time.perf_counter() > deadline or not root.tk.dooneevent(2):
                break

    errors = []

    def report(kind, value, tb):
        errors.append(value)
        import traceback

        traceback.print_exception(kind, value, tb)

    root.report_callback_exception = report
    with patch.object(game, "SoundManager", SilentSound), patch.object(
        game, "GamepadManager", NoPads
    ), patch.object(root, "attributes"):
        app = game.LightCycleGame(root, play_intro=False)
    root.attributes("-fullscreen", False)
    root.geometry("1280x720+20+20")
    app.screen_width, app.screen_height = 1280, 720
    output = Path(__file__).resolve().parents[1] / "previews"
    output.mkdir(exist_ok=True)

    def snapshot(name):
        root.update_idletasks()
        # Captura a janela específica, mesmo quando o IDE estiver na frente.
        capture_window(root).save(output / name)
        print("Snapshot:", name, flush=True)

    print("Menu pronto; abrindo janela", flush=True)
    pump()
    print("Iniciando perseguição", flush=True)
    app.start_chase()
    pump()
    snapshot("chase_intro.png")
    frame = app.current_frame
    frame._resume()
    frame.keys.add("w")
    for _ in range(4):
        pump()
    frame.keys.clear()
    frame.running = False
    # Avança para mostrar curvas e obstáculos em uma situação de jogo reproduzível.
    for i in range(120 * 10):
        frame.sim.advance(1 / 120, Controls(steer=-frame.sim.player.x * 3, throttle=1))
    frame.renderer.render(frame.sim)
    root.update_idletasks()
    snapshot("chase_road.png")
    timings = []
    for _ in range(30):
        frame.renderer.render(frame.sim)
        timings.append(frame.renderer.last_ms)
    print(
        f"Canvas estático: média={sum(timings)/len(timings):.2f} ms máximo={max(timings):.2f} ms",
        flush=True,
    )
    moving = []
    for _ in range(90):
        frame.sim.advance(1 / 60, Controls(steer=-frame.sim.player.x * 3, throttle=1))
        frame.renderer.render(frame.sim)
        moving.append(frame.renderer.last_ms)
    print(
        f"Canvas em movimento: média={sum(moving)/len(moving):.2f} ms máximo={max(moving):.2f} ms",
        flush=True,
    )
    from chase_sim import LightWall

    frame.sim.walls.append(
        LightWall(frame.sim.player.s + 75, -0.6, "rival", 0, frame.sim.time + 5)
    )
    frame.renderer.render(frame.sim)
    snapshot("chase_wall.png")
    saved_boost, saved_hit = frame.sim.player.boost_until, frame.sim.player.hit_until
    saved_rival_s = frame.sim.rival.s
    frame.sim.rival.s = frame.sim.player.s + 32
    frame.sim.player.boost_until = frame.sim.time + 1.5
    frame.renderer.render(frame.sim)
    snapshot("chase_boost.png")
    frame.sim.player.hit_until = frame.sim.time + 0.9
    frame.renderer.render(frame.sim)
    snapshot("chase_impact.png")
    frame.sim.player.boost_until, frame.sim.player.hit_until = saved_boost, saved_hit
    frame.sim.rival.s = saved_rival_s
    frame.renderer.render(frame.sim)
    frame._show_panel("pause")
    snapshot("chase_pause.png")
    frame._retry()
    assert frame.sim.time == 0 and frame.sim.pressure == 0
    frame.sim.result = "won"
    frame.sim.reason = "Rinzler foi encurralado. O caminho para CLU está aberto."
    frame._show_panel("result")
    snapshot("chase_win.png")
    # A ida e volta exercita cancelamento de timers e restauração das teclas.
    app.show_menu()
    pump()
    snapshot("menu_modes.png")
    menu = app.current_frame
    menu.set_mode("chase")
    menu.show_setup()
    pump()
    assert app.current_frame.__class__.__name__ == "ChaseFrame"
    app.start_game("rinzler", dict(app.colors), dict(app.models), 0)
    arena = app.current_frame
    arena.running = False
    arena.game_over = True
    arena.match_complete = True
    app.scores[1] = app.match_target
    arena.finish_rinzler_match(1)
    root.after_cancel(arena.restart_cooldown_id)
    arena.finish_round_cooldown()
    assert arena.victory_buttons[0].cget("text") == "CONTINUAR PERSEGUIÇÃO"
    arena.victory_buttons[0].invoke()
    pump()
    assert app.current_frame.from_duel
    assert app.scores[1] == app.match_target
    app.clear_screen()
    sheet = tk.Canvas(
        root, width=1280, height=720, bg=T.BACKGROUND, highlightthickness=0
    )
    sheet.pack(fill="both", expand=True)
    sheet.create_text(
        640,
        45,
        text="LIGHT CYCLES / VISTA SUPERIOR",
        fill=T.CORE,
        font=(T.FONT, 24, "bold"),
    )
    for i, (name, *_) in enumerate(BIKES):
        x = 250 + (i % 3) * 390
        y = 245 + (i // 3) * 290
        draw_bike(sheet, x + 70, y, (1, 0), T.CYAN, i, 7)
        sheet.create_text(x, y + 75, text=name, fill=T.CORE, font=(T.FONT, 16, "bold"))
        # Escala da arena e quatro direções: tamanho pequeno também deve ser legível.
        for j, direction in enumerate(((1, 0), (0, 1), (-1, 0), (0, -1))):
            items = draw_bike(sheet, x - 55 + j * 42, y + 120, (1, 0), T.CYAN, i, 1)
            move_bike(sheet, items, i, x - 55 + j * 42, y + 120, direction)
    snapshot("bikes_top.png")
    sheet.delete("all")
    sheet.create_text(
        640,
        55,
        text="PILOTO / CINCO INCLINAÇÕES",
        fill=T.CORE,
        font=(T.FONT, 24, "bold"),
    )
    pool = CanvasPool(sheet)
    sprites = RearSprites(sheet)
    pool.begin()
    for i, lean in enumerate((-1, -0.5, 0, 0.5, 1)):
        x = 150 + i * 245
        sprites.draw(pool, x, 495, 220, T.CYAN, lean, 0)
        pool.text(x, 555, text=f"{lean:+.1f}", fill=T.MUTED, font=(T.FONT, 16))
    pool.end()
    snapshot("rider_lean.png")
    sheet.destroy()
    pump()
    if app.music_after_id:
        root.after_cancel(app.music_after_id)
    root.destroy()
    if errors:
        raise RuntimeError(errors)
    print("GUI smoke OK; previews:", output)


if __name__ == "__main__":
    main()

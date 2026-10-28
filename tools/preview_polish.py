"""Revisão real do Canvas: HUD, encolhimento, derez e um finale completo."""

from pathlib import Path
import sys
import tkinter as tk
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.preview_capture import capture_window
from PIL import Image
import tron_light_cycle as game
from chase_sim import Controls, MAX_SPEED, clamp
from tools.preview_chase import SilentSound, NoPads
import theme as T


def autopilot(sim, step):
    target = sim.rival.x if sim.gap < 100 else 0
    pending = [wall for wall in sim.walls if wall.owner == "rival" and 0 < wall.s - sim.player.s < 120]
    if pending:
        target = min(pending, key=lambda wall: wall.s).gap_x
    if sim.phase == "finale":
        target = sim.target_lane
    desired = sim.rival.speed + (sim.gap - 22) * .8
    throttle = clamp((desired - sim.player.speed) * .2 + .15625, 0, 1)
    brake = .3 if sim.player.speed > desired + 4 else 0
    drift = sim.road.curvature(sim.player.s) * sim.player.speed**2 * .035
    steer = ((target - sim.player.x) * 5 + drift) / (.30 + .95 * sim.player.speed / MAX_SPEED)
    wall = sim.phase == "finale" and abs(sim.player.x - sim.target_lane) < .10 and not sim.cut_deployed
    sim.visual_steer = steer
    return Controls(steer, throttle, brake, step % 1000 == 0 and sim.gap > 65, wall)


def main():
    root = tk.Tk()
    root.maxsize(4096, 2160)
    root.geometry("1280x720+0+0")
    errors = []
    root.report_callback_exception = lambda *args: errors.append(args)
    with patch.object(game, "SoundManager", SilentSound), patch.object(
        game, "GamepadManager", NoPads
    ), patch.object(root, "attributes"):
        app = game.LightCycleGame(root, play_intro=False)
    root.attributes("-fullscreen", False)
    output = Path(__file__).resolve().parents[1] / "previews"
    output.mkdir(exist_ok=True)

    def grab():
        root.update_idletasks()
        return capture_window(root)

    def snapshot(name):
        grab().save(output / name)
        print(name, flush=True)

    for w, h in ((800, 600), (1366, 768), (1920, 1080)):
        root.geometry(f"{w}x{h}+0+0")
        app.screen_width, app.screen_height = w, h
        app.training_player_count, app.training_human_count = 4, 1
        app.training_teams = False
        app.models = {1: 0, 2: 1, 3: 2, 4: 5}
        app.colors = {1: T.CYAN, 2: T.ORANGE, 3: T.PURPLE, 4: T.GREEN}
        app.modifiers["shrinking_arena"] = True
        app.start_game("training", dict(app.colors), dict(app.models), 6)
        arena = app.current_frame
        root.after_cancel(arena.after_id)
        arena.after_id = None
        arena.running = False
        arena.sim_time = 7
        arena.anim_t = 7
        arena.update_shrinking_arena(snap=True)
        arena.chrome.raise_layers()
        initial = arena.arena_rect
        snapshot(f"arena_warning_{w}x{h}.png")
        arena.sim_time = 11
        arena.update_shrinking_arena(.016)
        assert initial[0] < arena.arena_rect[0] < arena.current_cell_bounds()[0] * game.CELL
        arena.update_shrinking_arena(snap=True)
        for item in arena.chrome.edges:
            assert tuple(arena.canvas.coords(item)) == arena.arena_rect
        root.update_idletasks()
        for pid in range(1, 5):
            name = arena.canvas.bbox(arena.chrome.names[pid])
            score = arena.canvas.bbox(arena.chrome.scores[pid])
            assert name[2] + 4 < score[0], (w, pid, name, score)
            assert arena.canvas.bbox(arena.chrome.cards[pid])[3] < arena.arena_rect[1]
        arena.chrome.raise_layers()
        snapshot(f"arena_shrinking_{w}x{h}.png")
        arena.open_pause()
        assert arena.paused and arena.canvas.itemcget(arena.pause_button.body, "state") == "hidden"
        arena.close_pause()
        assert not arena.paused and arena.canvas.itemcget(arena.pause_button.body, "state") == "normal"
        if w == 800:
            app.match_target = 10
            app.modifiers["lives"] = True
            arena.riders[3].alive = False
            arena.update_hud()
            root.update_idletasks()
            for pid in range(1, 5):
                name = arena.canvas.bbox(arena.chrome.names[pid])
                score = arena.canvas.bbox(arena.chrome.scores[pid])
                assert name[2] + 4 < score[0], (pid, name, score)
                assert arena.canvas.bbox(arena.chrome.pips[pid][-1])[2] < arena.canvas.bbox(arena.chrome.cards[pid])[2]
            snapshot("arena_hud_800x600.png")
            app.match_target = 5
            app.modifiers["lives"] = False
        if w == 1366:
            rider = arena.riders[1]
            rider.cell = (arena.base_cell_bounds[0] + 20, arena.height // 16)
            x, y = rider.cell[0] * game.CELL, rider.cell[1] * game.CELL
            rider.prev_cell = rider.cell
            rider.trail = [x - 160, y - 50, x - 60, y - 50, x - 60, y, x, y]
            for item in (rider.line_halo, rider.line_glow, rider.line_core):
                arena.canvas.coords(item, *rider.trail)
            rider.alive = False
            for item in rider.bike:
                arena.canvas.delete(item)
            arena.fx.derez(x, y, rider.color, rider.dir, scale=1.4)
            arena.fx.dissolve_trail([(list(rider.trail), list(zip(
                (rider.line_halo, rider.line_glow, rider.line_core),
                [color for color, _ in T.glow_layers(rider.color, 3)])))], .9, .5)
            arena.fx.update(.32)
            arena.update_hud()
            snapshot("arena_derez.png")
            particles = {part.item for part in arena.fx.voxels._all}
            arena.round_ready_at = 0
            arena.init_round()
            assert particles <= set(arena.canvas.find_all())
            assert not arena.fx.voxels.busy

    root.geometry("1280x720+0+0")
    app.screen_width, app.screen_height = 1280, 720
    app.start_chase()
    frame = app.current_frame
    frame._resume()
    frame.running = False
    root.after_cancel(frame.after_id)
    frame.after_id = None
    sim = frame.sim
    for step in range(120 * 100):
        sim.advance(1 / 120, autopilot(sim, step))
        if sim.phase == "finale":
            frame.renderer.render(sim)
            snapshot("chase_finale.png")
            break
    else:
        raise AssertionError("Não alcançou a janela de corte")
    for step in range(step + 1, step + 120 * 10):
        sim.advance(1 / 120, autopilot(sim, step))
        if sim.phase == "derez":
            break
    assert sim.phase == "derez"
    frames = []
    saved = set()
    for i in range(86):
        if i:
            sim.advance(.05)
        frame.renderer.render(sim)
        shot = grab()
        frames.append(shot.resize((768, 432), Image.Resampling.LANCZOS))
        for threshold, name in ((0, "impact"), (.65, "skid"), (1.3, "overload"), (1.95, "cubes")):
            if sim.derez_time >= threshold and name not in saved:
                shot.save(output / f"chase_derez_{name}.png")
                saved.add(name)
    assert sim.result == "won" and sim.score > 0
    frames[0].save(output / "chase_derez.gif", save_all=True,
                   append_images=frames[1:], duration=50, loop=0)
    frame._show_panel("result")
    snapshot("chase_result.png")
    print(f"Finale OK: {sim.chase_time:.1f}s / {sim.attempts} tentativa(s) / {sim.score} pontos", flush=True)
    frame._retry()
    frame.running = False
    frame.renderer.render(frame.sim)
    assert not frame.renderer.voxels.busy
    app.clear_screen()
    if app.music_after_id:
        root.after_cancel(app.music_after_id)
    root.destroy()
    if errors:
        raise RuntimeError(errors)
    print("Polimento: revisão visual e ciclo de vida OK", flush=True)


if __name__ == "__main__":
    main()

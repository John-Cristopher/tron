"""Cena de perseguição pseudo-3D, controles contínuos e áudio opcional."""

import math
from pathlib import Path
import time
import tkinter as tk

from chase_sim import ChaseSimulation, Controls, ROAD_HALF_WIDTH, clamp
from config import BG_COLOR, CYAN
from menu_nav import INPUT
from rider_rear import RearSprites
from background_grid import GridBackground
from road_pseudo3d import RoadRenderer
from hud import draw_hud
from derez import Derez
from sound import effect_files
import theme as T


class CanvasPool:
    """Reutiliza itens: o número de objetos do Canvas não cresce a cada quadro."""

    def __init__(self, canvas):
        self.canvas = canvas
        self.items = {}
        self.used = {}
        self.photos = {}
        self.previous = {}
        self.hidden = set()
        self.order = []
        self.last_order = []

    def begin(self):
        self.used = {}
        self.order = []
        self.layer = "chase_scene"

    def _draw(self, kind, coords, **options):
        options.setdefault("tags", getattr(self, "layer", "chase_scene"))
        index = self.used.get(kind, 0)
        items = self.items.setdefault(kind, [])
        coords = tuple(coords)
        if index == len(items):
            items.append(getattr(self.canvas, "create_" + kind)(*coords, **options))
        else:
            old_coords, old_options = self.previous[items[index]]
            if old_coords != coords:
                self.canvas.coords(items[index], *coords)
            changed = {
                key: value
                for key, value in options.items()
                if old_options.get(key) != value
            }
            if items[index] in self.hidden:
                changed["state"] = "normal"
                self.hidden.remove(items[index])
            if changed:
                self.canvas.itemconfigure(items[index], **changed)
        self.previous[items[index]] = (coords, options)
        self.order.append(items[index])
        self.used[kind] = index + 1
        return items[index]

    def polygon(self, coords, **options):
        options.setdefault("outline", "")
        options.setdefault("stipple", "")
        return self._draw("polygon", coords, **options)

    def line(self, coords, **options):
        return self._draw("line", coords, **options)

    def text(self, x, y, **options):
        options.setdefault("anchor", "center")
        return self._draw("text", (x, y), **options)

    def rect(self, coords, **options):
        options.setdefault("outline", "")
        options.setdefault("stipple", "")
        return self._draw("rectangle", coords, **options)

    def image(self, x, y, **options):
        item = self._draw("image", (x, y), **options)
        self.photos[item] = options["image"]
        return item

    def end(self):
        for kind, items in self.items.items():
            for item in items[self.used.get(kind, 0) :]:
                if item not in self.hidden:
                    self.canvas.itemconfigure(item, state="hidden")
                    self.hidden.add(item)
        if self.order != self.last_order:
            for item in self.order:
                self.canvas.tag_raise(item)
            self.last_order = self.order


class ChaseRenderer:
    def __init__(self, canvas, width, height, color=CYAN, model=0):
        self.cv, self.w, self.h = canvas, width, height
        self.color, self.model = color, model
        self.pool = CanvasPool(canvas)
        self.background = GridBackground(canvas, width, height)
        self.road = RoadRenderer()
        self.sprites = RearSprites(canvas)
        self.sprites.warm(height * 0.235, color, model)
        self.last_ms = 0
        self.voxels = Derez(canvas, tag="chase_derez")
        self._session = None
        self._derez_clock = 0.0
        self._derez_spawned = False
        self.rival_screen = None

    def render(self, sim):
        started = time.perf_counter()
        p, w, h = self.pool, self.w, self.h
        if self._session is not sim:
            self._session = sim
            self.voxels.clear()
            self._derez_clock = 0.0
            self._derez_spawned = False
        self.rival_screen = None
        p.begin()
        self.background.draw(p, sim)
        horizon = h * 0.40
        camera_s = sim.player.s - 8
        camera_y = sim.road.height(camera_s) + 5
        camera_x = sim.road.center(camera_s) + sim.player.x * ROAD_HALF_WIDTH
        heading = sim.road.heading(camera_s)
        boosted = sim.time < sim.player.boost_until and sim.phase != "derez"
        zoom = 1.035 if boosted else 1.0
        shock = max(0, 1 - sim.derez_time / .3) * 3 if sim.phase == "derez" else 0
        shake_x = math.sin(sim.derez_time * 151 + 1) * shock
        shake_y = math.sin(sim.derez_time * 113 + 2) * shock * .5

        def project(s, lateral=0, altitude=0):
            dz = s - camera_s
            if dz <= 0.6:
                return None
            scale = 1.1 * zoom / dz
            cx = (
                sim.road.center(s) - camera_x - heading * dz + lateral * ROAD_HALF_WIDTH
            )
            y = sim.road.height(s) + altitude - camera_y
            return (
                w * 0.5 + scale * cx * w * 0.5 + shake_x,
                horizon - scale * y * h * 0.65 + shake_y,
                scale * ROAD_HALF_WIDTH * w * 0.5,
            )

        self.road.draw(
            p,
            sim,
            project,
            w,
            h,
            lambda a, b, clip: self._objects(sim, project, a, b, clip),
        )
        x, y, _ = project(sim.player.s, sim.player.x)
        size = h * 0.235
        if boosted:
            self._ribbon(sim, project, sim.player, self.color, 22)
            self._speed_lines(sim)
        self.sprites.draw(
            p, x, y, size, self.color, getattr(sim, "visual_steer", 0), self.model,
            phase=sim.time * 2
        )
        self._crash_effects(sim)
        self.background.finish(p)
        # Flash curto no impacto; a invulnerabilidade continua regida pela simulação.
        remaining = sim.player.hit_until - sim.time
        if remaining > 0.72:
            p.rect(
                (0, 0, w, h), fill=T.blend(T.RED, T.BACKGROUND, 0.45), stipple="gray50"
            )
            p.line((0, h - 4, w, h - 4), fill=T.CORE, width=4)
        p.layer = "chase_hud"
        draw_hud(p, sim, w, h, self.color)
        p.end()
        if sim.phase == "derez":
            if sim.derez_time >= 1.6 and not self._derez_spawned and self.rival_screen:
                rx, ry, size = self.rival_screen
                self.voxels.spawn(rx, ry - size * .40, color=T.ORANGE,
                    heading=-math.pi / 2, length=max(60, size * .90),
                    width=max(30, size * .66), gravity=900, power=1.4,
                    hot="#E6FDFF")
                self._derez_spawned = True
                self._derez_clock = 1.6
            if self._derez_spawned:
                self.voxels.update(max(0, sim.derez_time - self._derez_clock))
                self._derez_clock = sim.derez_time
                self.cv.tag_raise("chase_derez")
                self.cv.tag_raise("chase_hud")
        self.last_ms = (time.perf_counter() - started) * 1000

    def _objects(self, sim, project, s0, s1, clip):
        p, h = self.pool, self.h
        for obstacle in sim.obstacles:
            if not s0 <= obstacle.s < s1:
                continue
            point = project(obstacle.s, obstacle.x)
            if point and point[1] <= clip:
                x, y, r = point
                rw, rh = r * obstacle.width, min(h * 0.22, r * 0.48)
                coords = (
                    x - rw,
                    y,
                    x + rw,
                    y,
                    x + rw,
                    y - rh,
                    x - rw,
                    y - rh,
                    x - rw,
                    y,
                )
                p.polygon(coords, fill=T.ARMOR)
                T.neon_line(p, coords, T.AMBER, max(0.7, r * 0.006))
                p.line(
                    (x - rw, y - rh, x, y - rh * 1.22, x + rw, y - rh),
                    fill=T.CORE,
                    width=1,
                )
        for wall in sim.walls:
            if not s0 <= wall.s < s1:
                continue
            point = project(wall.s)
            if point and point[1] <= clip:
                if wall.cut_x is not None:
                    self._cut_wall(sim, project, wall)
                    continue
                x, y, r = point
                active = sim.time >= wall.active_at
                color = T.ORANGE if wall.owner == "rival" else self.color
                height = min(h * 0.5, r * 0.75) if active else max(2, r * 0.035)
                for left, right in (
                    (-1, wall.gap_x - wall.gap_width / 2),
                    (wall.gap_x + wall.gap_width / 2, 1),
                ):
                    coords = (
                        x + r * left,
                        y,
                        x + r * right,
                        y,
                        x + r * right,
                        y - height,
                        x + r * left,
                        y - height,
                        x + r * left,
                        y,
                    )
                    p.polygon(coords, fill=T.blend(color, T.BACKGROUND, .35), stipple="gray50")
                    T.neon_line(p, coords, color, max(0.7, r * 0.007))
                    if active:
                        p.line((x + r * left, y - height, x + r * right, y - height),
                               fill=T.CORE, width=max(1, r * .008))
                        # Varreduras verticais e uma falha móvel na energia.
                        for i in range(1, 10):
                            phase = (i / 10 + sim.time * .12) % 1
                            xx = x + r * (left + (right - left) * phase)
                            p.line(
                                (xx, y - height * .20, xx, y - height * .94),
                                fill=T.blend(color, T.BACKGROUND, .40),
                                width=1,
                            )
                        glitch = (sim.time * .7) % 1
                        yy = y - height * (.2 + glitch * .65)
                        p.line((x + r * left, yy, x + r * right, yy), fill=T.BACKGROUND, width=2)
                # O corredor seguro fica livre; chevrons nas bordas apontam para ele.
                center = x + r * wall.gap_x
                gap = r * wall.gap_width / 2
                for side in (-1, 1):
                    xx = center + side * gap
                    T.neon_line(
                        p,
                        (
                            xx + side * r * 0.09,
                            y - height * 0.56,
                            xx + side * r * 0.025,
                            y - height * 0.40,
                            xx + side * r * 0.09,
                            y - height * 0.24,
                        ),
                        T.CORE,
                        max(0.7, r * 0.009),
                    )
                p.line(
                    (center - gap, y, center + gap, y),
                    fill=T.CORE,
                    width=max(1, r * 0.01),
                )
        if s0 <= sim.rival.s < s1:
            point = project(sim.rival.s, sim.rival.x)
            if point and point[1] <= clip:
                x, y, r = point
                size = min(self.h * .45, r * .55)
                self.rival_screen = (x, y, size)
                tint, lean, view = T.ORANGE, sim.ai_steer, 0
                if sim.phase == "derez":
                    t = sim.derez_time
                    if t >= 1.6:
                        return
                    tint = T.CORE if t < .15 or t >= 1.2 else (T.ORANGE, T.CORE, T.BACKGROUND)[int(t * 30) % 3]
                    lean = math.sin(t * 29) * min(1, t * 1.5)
                    view = 2 if t >= 1.08 else 1 if t >= .65 else 0
                elif sim.telegraphing and int(sim.time * 12) % 2 == 0:
                    tint = T.CORE
                self._ribbon(sim, project, sim.rival, tint, 34)
                if sim.phase == "finale":
                    self._target_lane(sim, project)
                self.sprites.draw(p, x, y, size, tint, lean, 1, view=view, phase=sim.time * 2)

    def _target_lane(self, sim, project):
        a = project(sim.rival.s + 5, sim.target_lane)
        b = project(sim.rival.s + 65, sim.target_lane)
        if a and b:
            ax, ay, ar = a
            bx, by, br = b
            self.pool.polygon((ax - ar * .22, ay, ax + ar * .22, ay,
                bx + br * .22, by, bx - br * .22, by),
                fill=T.ORANGE, stipple="gray25")
            for side in (-1, 1):
                self.pool.line((ax + side * ar * .23, ay, bx + side * br * .23, by),
                               fill=T.AMBER, width=1)

    def _cut_wall(self, sim, project, wall):
        near, far = project(wall.s - 60, wall.cut_x), project(wall.s + 12, wall.cut_x)
        if near and far:
            ax, ay, ar = near
            bx, by, br = far
            ah, bh = min(self.h * .3, ar * .45), min(self.h * .3, br * .45)
            coords = (ax, ay, bx, by, bx, by - bh, ax, ay - ah, ax, ay)
            self.pool.polygon(coords, fill=self.color, stipple="gray50")
            T.neon_line(self.pool, coords, self.color, max(1, ar * .007))
            self.pool.line((ax, ay - ah, bx, by - bh), fill=T.CORE, width=2)

    def _crash_effects(self, sim):
        if sim.phase != "derez" or self.rival_screen is None:
            return
        p, t = self.pool, sim.derez_time
        x, y, size = self.rival_screen
        if t < .15:
            yy = y - size * (1 - t / .15)
            T.neon_line(p, (x - size * .45, yy, x + size * .45, yy), T.CORE, 2)
        elif t < 1.2:
            for i in range(16):
                phase = (t * 5 + i * .618) % 1
                xx = x + math.sin(i * 17.3) * phase * size * .85
                yy = y - math.sin(phase * math.pi) * size * .24 + phase * size * .08
                p.line((xx, yy, xx - size * .06, yy - size * .03),
                       fill=T.AMBER if i % 3 else T.CORE, width=1)
        elif t < 1.6:
            radius = size * .13
            cy = y - size * .52
            for rr in (radius, radius * .68):
                coords = [v for i in range(33) for v in
                    (x + math.cos(i * math.tau / 32) * rr, cy + math.sin(i * math.tau / 32) * rr)]
                T.neon_line(p, coords, T.CORE, 1.5)
        elif t < 2.25:
            q = (t - 1.6) / .65
            radius = size * (.5 + q * 2)
            coords = [v for i in range(33) for v in
                (x + math.cos(i * math.tau / 32) * radius,
                 y + math.sin(i * math.tau / 32) * radius * .15)]
            p.polygon(coords, fill=T.blend(T.CORE, T.BACKGROUND, .65 + q * .35), stipple="gray25")

    def _ribbon(self, sim, project, bike, color, length):
        for i in range(6):
            crash = sim.phase == "derez" and bike is sim.rival
            if crash and i >= 6 * max(0, 1 - sim.derez_time / 1.2):
                continue
            wave = math.sin(sim.derez_time * 26 - i * .9) * .12 * min(1, sim.derez_time) if crash else 0
            a = project(bike.s - length * (i + 1) / 6, bike.x + wave, 0.025)
            b = project(bike.s - length * i / 6, bike.x - wave * .35, 0.025)
            if a is None or b is None:
                continue
            ax, ay, ar = a
            bx, by, br = b
            p = self.pool
            p.polygon(
                (
                    ax - ar * 0.025,
                    ay,
                    ax + ar * 0.025,
                    ay,
                    bx + br * 0.025,
                    by,
                    bx - br * 0.025,
                    by,
                ),
                fill=T.blend(color, T.BACKGROUND, 0.25 + i * 0.10),
            )
            p.line(
                (ax, ay, bx, by),
                fill=T.blend(color, T.CORE, 0.6 - i * 0.08),
                width=max(1, br * 0.006),
            )

    def _speed_lines(self, sim):
        w, h, p = self.w, self.h, self.pool
        for i in range(18):
            angle = (i + 0.5) * math.tau / 18
            radius = 0.38 + ((i * 0.618 + sim.time * 1.7) % 1) * 0.30
            x, y = (
                w * 0.5 + math.cos(angle) * w * radius,
                h * 0.44 + math.sin(angle) * h * radius,
            )
            x2, y2 = w * 0.5 + math.cos(angle) * w * (
                radius + 0.10
            ), h * 0.44 + math.sin(angle) * h * (radius + 0.10)
            p.line(
                (x, y, x2, y2),
                fill=T.blend(self.color, T.BACKGROUND, 0.55),
                width=1 + i % 2,
            )


class ChaseAudio:
    """Efeitos próprios da perseguição, com alternativa nos sons da arena."""

    files = {
        "engine": ("engine", "motoluz_parada"),
        "accelerate": ("accelerate", "motoluz_acelerando"),
        "start": ("start", "motoluz_ligando"),
        "brake": ("brake", "motolu_zfreio", "motoluz_freio"),
        "turn": ("turn",),
        "turn_01": ("turn_01", "virar_01"),
        "turn_02": ("turn_02", "virar_02"),
        "turn_03": ("turn_03", "virar_03"),
        "boost": ("boost",),
        "wall_warning": ("wall_warning",),
        "wall_on": ("wall_on",),
        "impact": ("impact",),
        "win": ("win",),
        "lose": ("lose", "deresolucao"),
        "finale_ready": ("finale_ready",),
        "finale_miss": ("finale_miss",),
        "rival_impact": ("rival_impact",),
        "rival_skid": ("rival_skid",),
        "rival_overload": ("rival_overload",),
        "rival_derez": ("rival_derez",),
        "rival_tail": ("rival_tail",),
    }
    fallback = {
        "start": "go",
        "brake": "turn",
        "turn": "turn",
        "boost": "go",
        "wall_warning": "beep",
        "wall_on": "turn",
        "impact": "bike_impact",
        "win": "match_win",
        "lose": "bike_derez",
        "finale_ready": "beep",
        "finale_miss": "turn",
        "rival_impact": "bike_impact",
        "rival_skid": "turn",
        "rival_overload": "beep",
        "rival_derez": "bike_derez",
        "rival_tail": "bike_impact",
    }

    def __init__(self, manager, directories=None):
        self.manager = manager
        self.sounds, self.loaded_files = {}, {}
        self.engine = self.engine_playing = None
        self.started = self.was_running = self.braking = False
        self.steer, self.turn_index = 0, 0
        self.effect_channels = []
        if manager.backend != "pygame":
            return
        assets = Path(__file__).resolve().parent / "assets"
        directories = (
            directories
            if directories is not None
            else (assets / "chase", assets / "sounds" / "chase")
        )
        for name, stems in self.files.items():
            for directory in directories:
                for file in effect_files(directory, stems):
                    try:
                        self.sounds[name] = manager.pg.mixer.Sound(str(file))
                        self.loaded_files[name] = str(file)
                        break
                    except Exception:
                        continue
                if name in self.sounds:
                    break
        if self._loop_sample(False) is not None or self._loop_sample(True) is not None:
            manager.pg.mixer.set_reserved(4)
            self.engine = manager.pg.mixer.Channel(3)

    def _loop_sample(self, accelerating):
        if accelerating and "accelerate" in self.sounds:
            return self.sounds["accelerate"]
        if "engine" in self.sounds:
            return self.sounds["engine"]
        if "accelerate" in self.sounds:
            return self.sounds["accelerate"]
        return getattr(self.manager, "_sounds", {}).get("go")

    def event(self, name):
        if not self.manager.sfx_on or self.manager.backend == "none":
            return
        selected = name
        if name == "rival_derez" and "rival_derez" not in self.sounds and "lose" in self.sounds:
            selected = "lose"
        if name == "turn":
            variants = [
                key for key in ("turn_01", "turn_02", "turn_03") if key in self.sounds
            ]
            if variants:
                selected = variants[self.turn_index % len(variants)]
                self.turn_index += 1
        if selected in self.sounds:
            sound = self.sounds[selected]
            sound.set_volume(self.manager.sfx_level * 0.65)
            channel = sound.play()
            if channel is not None and name.startswith("rival_"):
                self.effect_channels = [ch for ch in self.effect_channels if ch.get_busy()]
                self.effect_channels.append(channel)
        elif name in self.fallback:
            self.manager.play(self.fallback[name])

    def pause_effects(self, paused):
        for channel in self.effect_channels:
            if paused:
                channel.pause()
            else:
                channel.unpause()

    def update(self, speed, running, controls=None):
        if not running or not self.manager.sfx_on:
            if self.engine is not None and self.engine_playing is not None:
                self.engine.stop()
                self.engine_playing = None
            if self.was_running:
                for name, sound in self.sounds.items():
                    if name in ("start", "brake") or name.startswith("turn"):
                        sound.stop()
            self.was_running = self.braking = False
            self.steer = 0
            return
        if not self.started:
            self.event("start")
            self.started = True
        braking = controls is not None and controls.brake > 0.1
        steer = (
            (1 if controls.steer > 0.25 else -1 if controls.steer < -0.25 else 0)
            if controls
            else 0
        )
        if braking and not self.braking:
            self.event("brake")
        if steer and steer != self.steer:
            self.event("turn")
        self.steer, self.braking, self.was_running = steer, braking, True
        accelerating = (
            controls.throttle > 0.1 and not braking if controls else speed > 15
        )
        sample = self._loop_sample(accelerating)
        if self.engine is not None and sample is not None:
            self.engine.set_volume(
                self.manager.sfx_level
                * getattr(self.manager, "engine_level", 1.0)
                * (0.12 + 0.28 * clamp(speed / 120, 0, 1))
            )
            if sample is not self.engine_playing or not self.engine.get_busy():
                self.engine.play(sample, loops=-1, fade_ms=70)
                self.engine_playing = sample

    def close(self):
        for sound in self.sounds.values():
            sound.stop()
        if self.engine is not None:
            self.engine.stop()
            self.manager.pg.mixer.set_reserved(3)
        self.engine_playing = None


class ChaseFrame(tk.Frame):
    def __init__(self, parent, controller, from_duel=False):
        super().__init__(parent, bg=BG_COLOR)
        self.root, self.controller = parent, controller
        self.from_duel = from_duel
        self.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(
            self,
            width=controller.screen_width,
            height=controller.screen_height,
            bg=BG_COLOR,
            highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True)
        self.renderer = ChaseRenderer(
            self.canvas,
            controller.screen_width,
            controller.screen_height,
            controller.colors[1],
            controller.models[1],
        )
        self.audio = ChaseAudio(controller.sound)
        self.sim = ChaseSimulation()
        self.keys = set()
        self.running = False
        self.closed = False
        self.after_id = None
        self.panel = None
        self.panel_mode = None
        self.buttons = []
        self.selection = 0
        self.last = time.perf_counter()
        self.press_bind = parent.bind("<KeyPress>", self.key_down)
        self.release_bind = parent.bind("<KeyRelease>", self.key_up)
        self.focus_bind = parent.bind("<FocusOut>", self.focus_lost, add="+")
        self._show_panel("intro")
        self._tick()

    def destroy_arena(self):
        self.closed = True
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        self.audio.close()
        self.root.unbind("<KeyPress>", self.press_bind)
        self.root.unbind("<KeyRelease>", self.release_bind)
        self.root.unbind("<FocusOut>", self.focus_bind)
        self.keys.clear()

    def _controls(self):
        pad = self.controller.pads.driving_state(0)
        keys = self.keys
        left = bool(keys & {"a", "left"})
        right = bool(keys & {"d", "right"})
        steer = float(right) - float(left)
        if not (left or right):
            steer = pad["steer"]
        return Controls(
            steer,
            max(float(bool(keys & {"w", "up"})), pad["throttle"]),
            max(float(bool(keys & {"s", "down"})), pad["brake"]),
            bool(keys & {"space", "shift_l", "shift_r"}) or pad["boost"],
            "e" in keys or pad["wall"],
        )

    def _tick(self):
        self.after_id = None
        if self.closed:
            return
        started = time.perf_counter()
        elapsed = min(0.25, started - self.last)
        self.last = started
        controls = None
        if self.running:
            controls = self._controls()
            self.sim.visual_steer = controls.steer
            self.sim.advance(elapsed, controls)
            for event in self.sim.events:
                self.audio.event(event)
            self.sim.events.clear()
            if self.sim.result:
                self.running = False
                self.audio.event("win" if self.sim.result == "won" else "lose")
                self._show_panel("result")
        self.audio.update(self.sim.player.speed, self.running and self.sim.phase != "derez", controls)
        self.renderer.render(self.sim)
        self.after_id = self.root.after(
            max(1, int(16 - (time.perf_counter() - started) * 1000)), self._tick
        )

    def _resume(self):
        self.controller.sound.play("menu_select")
        self.audio.pause_effects(False)
        if self.panel:
            self.panel.destroy()
            self.panel = None
        self.panel_mode = None
        self.keys.clear()
        self.last = time.perf_counter()
        self.running = True
        self.canvas.focus_set()
        self.controller.sound.set_music_track("chase")

    def _retry(self):
        self.sim = ChaseSimulation()
        self.audio.close()
        self.audio = ChaseAudio(self.controller.sound)
        self._resume()

    def _volume(self, kind, direction=1):
        sound = self.controller.sound
        if kind == "music":
            sound.set_music_level(clamp(sound.music_level + direction * 0.1, 0, 1))
        else:
            sound.set_sfx_level(clamp(sound.sfx_level + direction * 0.1, 0, 1))
        sound.play("menu_move")
        self._refresh_focus()

    def _show_panel(self, mode):
        if mode == "pause":
            self.controller.sound.play("menu_select")
            self.audio.pause_effects(True)
        self.running = False
        self.keys.clear()
        self.audio.update(0, False)
        self.panel_mode = mode
        if self.panel:
            self.panel.destroy()
        self.panel = tk.Frame(
            self, bg=T.PANEL, highlightbackground=T.GRID_BRIGHT, highlightthickness=2
        )
        self.panel.place(relx=0.5, rely=0.50, anchor="center", relwidth=0.70)
        self.buttons = []
        self.selection = 0
        title = {
            "intro": "TOP GEAR / TERRAS ERMAS",
            "pause": "PERSEGUIÇÃO PAUSADA",
            "result": (
                "RINZLER DERESOLVIDO" if self.sim.result == "won" else
                "ENERGIA ESGOTADA" if self.sim.player.energy <= 0 else "CONTATO PERDIDO"
            ),
        }[mode]
        detail = {
            "intro": (
                "A fuga da arena foi só o começo."
                if self.from_duel
                else "Alcance Rinzler e encerre a perseguição com um corte de luz."
            ),
            "pause": "A pista espera por você.",
            "result": self.sim.reason,
        }[mode]
        tk.Label(
            self.panel,
            text=title,
            bg=T.PANEL,
            fg=CYAN,
            font=(T.FONT, 19, "bold"),
            wraplength=self.controller.screen_width * 0.6,
        ).pack(pady=(22, 8))
        tk.Label(
            self.panel,
            text=detail,
            bg=T.PANEL,
            fg=T.CORE,
            font=(T.FONT, 11),
            wraplength=self.controller.screen_width * 0.6,
        ).pack(padx=18, pady=(0, 12))
        if mode == "intro":
            text = (
                "1 / ALCANCE: comece a 240 m e chegue a menos de 40 m.\n"
                "2 / PRESSÃO: siga no vácuo, perto e alinhado à moto dele.\n"
                "3 / CORTE: ele pisca e anuncia a próxima faixa.\n"
                "Alinhe sua moto nessa faixa e use E (X no controle).\n"
                "Você tem 4 s. Errar devolve a pressão a 60%.\n"
                "A 400 m você o perde. Sem energia, a perseguição termina."
            )
            tk.Label(
                self.panel,
                text=text,
                bg=T.PANEL,
                fg=T.MUTED,
                font=(T.FONT, 10),
                wraplength=self.controller.screen_width * 0.6,
                justify="left",
            ).pack(padx=18, pady=(0, 14))
            entries = [
                ("INICIAR PERSEGUIÇÃO", self._resume),
                ("VOLTAR AO MENU", self.controller.show_menu),
            ]
        elif mode == "pause":
            entries = [
                ("CONTINUAR", self._resume),
                ("music", lambda: self._volume("music")),
                ("sfx", lambda: self._volume("sfx")),
                ("REINICIAR", self._retry),
                ("VOLTAR AO MENU", self.controller.show_menu),
            ]
        else:
            if self.sim.result == "won":
                tk.Label(self.panel, text=(f"{self.sim.score:06d} PONTOS\n"
                    f"{self.sim.chase_time:.1f}s / ENERGIA {self.sim.player.energy:.0f}% / "
                    f"{self.sim.attempts} TENTATIVA(S)"), bg=T.PANEL, fg=T.CORE,
                    font=(T.FONT, 14, "bold")).pack(pady=(0, 12))
            entries = [
                ("TENTAR NOVAMENTE", self._retry),
                ("VOLTAR AO MENU", self.controller.show_menu),
            ]
        for index, (label, command) in enumerate(entries):
            button = tk.Button(
                self.panel,
                text=label,
                command=lambda cmd=command: self._panel_action(cmd),
                font=(T.FONT, 11, "bold"),
                relief="flat",
                bd=0,
                pady=8,
                cursor="hand2",
            )
            button.pack(fill="x", padx=28, pady=3)
            button.bind("<Enter>", lambda event, i=index: self._select(i))
            self.buttons.append((button, label))
        device = "DIRECIONAL" if INPUT.use_pad else "↑ ↓"
        hint = f"{device} escolhe   {INPUT.confirm_name()} confirma"
        if mode == "pause":
            hint += "   ← → ajusta volume"
        tk.Label(self.panel, text=hint, bg=T.PANEL, fg=T.MUTED, font=(T.FONT, 9)).pack(
            pady=(12, 18)
        )
        self._refresh_focus()

    def _select(self, index):
        selection = index % len(self.buttons)
        if selection != self.selection:
            self.controller.sound.play("menu_move")
        self.selection = selection
        self._refresh_focus()

    def _panel_action(self, command):
        self.controller.sound.play("menu_select")
        command()

    def _refresh_focus(self):
        for i, (button, label) in enumerate(self.buttons):
            if label in ("music", "sfx"):
                level = getattr(
                    self.controller.sound,
                    "music_level" if label == "music" else "sfx_level",
                )
                text = (
                    "MÚSICA" if label == "music" else "EFEITOS"
                ) + f"   {int(level*100)}%"
            else:
                text = label
            selected = i == self.selection
            button.configure(
                text=text,
                bg=CYAN if selected else T.ARMOR,
                fg=T.BACKGROUND if selected else T.CORE,
                activebackground=T.CORE,
                activeforeground=T.BACKGROUND,
            )

    def on_escape(self):
        if self.panel_mode == "pause":
            self._resume()
        elif self.running:
            self._show_panel("pause")
            self.controller.sound.set_music_track("pause")

    def focus_lost(self, event):
        if event.widget is self.root and self.running:
            self.on_escape()

    def key_down(self, event):
        key = event.keysym.lower()
        if key in ("escape", "p"):
            if key == "p":
                self.on_escape()
            return
        if self.panel:
            if key in ("up", "w"):
                self._select(self.selection - 1)
            elif key in ("down", "s"):
                self._select(self.selection + 1)
            elif key in ("left", "right") and self.buttons[self.selection][1] in (
                "music",
                "sfx",
            ):
                self._volume(
                    self.buttons[self.selection][1], -1 if key == "left" else 1
                )
            elif key in ("return", "space"):
                self.buttons[self.selection][0].invoke()
            return "break"
        self.keys.add(key)

    def key_up(self, event):
        self.keys.discard(event.keysym.lower())

    def on_pad(self, pid, kind, value):
        if pid != 1:
            return
        if kind == "button" and value in ("start", "back"):
            if self.panel_mode == "intro" and value == "start":
                self._resume()
            else:
                self.on_escape()
        elif self.panel:
            if kind == "dir":
                if value[1]:
                    self._select(self.selection + value[1])
                elif value[0] and self.buttons[self.selection][1] in ("music", "sfx"):
                    self._volume(self.buttons[self.selection][1], value[0])
            elif kind == "button" and value == "a":
                self.buttons[self.selection][0].invoke()
            elif kind == "button" and value == "b" and self.panel_mode == "pause":
                self._resume()

    def on_inputs_changed(self):
        # Desconectar o controle durante a direção pausa a cena.
        if self.running:
            self.on_escape()

    def on_input_source_changed(self):
        if self.panel_mode:
            self._show_panel(self.panel_mode)

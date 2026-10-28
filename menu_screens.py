"""Telas de menu: componentes compartilhados, área útil e navegação previsível."""

import math
import time

import theme as T
import ui
from config import (
    MAPS,
    RANDOM_MAP,
    AI_LEVELS,
    COLOR_PALETTE,
    FRAME_MS,
)
from menu_nav import INPUT, help_for
from menu_scene import MenuScene, brand_box, title_boxes
from sprites_topview import (
    draw_bike,
    move_bike,
    CYCLES,
    UNIT,
    model_bounds,
    centered_origin,
)
from chase_mode import CanvasPool


def spatial_neighbor(boxes, current, dx, dy):
    """Item mais próximo na direção (dx, dy) pela posição na tela.
    Sem nenhum à frente, volta pelo outro lado da mesma linha/coluna; None se não houver."""
    x0, y0, x1, y1 = boxes[current]
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    ahead = behind = None
    for key, (a0, b0, a1, b1) in boxes.items():
        if key == current:
            continue
        if dx:
            gap = a0 - x1 if dx > 0 else x0 - a1
            side = max(0, b0 - y1, y0 - b1)  # afastamento na outra direção
            offset = abs((b0 + b1) / 2 - cy)
        else:
            gap = b0 - y1 if dy > 0 else y0 - b1
            side = max(0, a0 - x1, x0 - a1)
            offset = abs((a0 + a1) / 2 - cx)
        if gap >= -1:
            score = (gap + 2 * side, offset)
            if ahead is None or score < ahead[0]:
                ahead = (score, key)
        elif side == 0:
            score = (gap, offset)  # o mais distante para trás
            if behind is None or score < behind[0]:
                behind = (score, key)
    best = ahead or behind
    return best[1] if best else None


class MapPreview:
    def __init__(self, canvas, box, index, changed):
        self.pool, self.box, self.index, self.changed = (
            CanvasPool(canvas),
            box,
            index,
            changed,
        )

    def draw(self, t):
        x0, y0, x1, y1 = self.box
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        scale = min((x1 - x0) * 0.34, (y1 - y0) * 0.35)
        angle = t * 0.20
        ca, sa = math.cos(angle), math.sin(angle)

        def project(u, v, z=0):
            u, v = u * ca - v * sa, u * sa + v * ca
            return cx + u * scale, cy + v * scale * 0.5 - z * scale

        def flat(points):
            return [p for v in points for p in project(*v)]

        p = self.pool
        p.begin()
        tags = ("ui", "map3d")
        p.polygon(
            flat([(-1, -0.7, 0), (1, -0.7, 0), (1, 0.7, 0), (-1, 0.7, 0)]),
            fill=T.PANEL,
            outline=T.CYAN,
            width=1,
            tags=tags,
        )
        for i in range(-3, 4):
            p.line(flat([(i / 4, -0.7, 0), (i / 4, 0.7, 0)]), fill=T.GRID, tags=tags)
        idx = int(t / 3) % len(MAPS) if self.index == RANDOM_MAP else self.index
        grow = min(1, max(0, (t - self.changed) / 0.6))
        faces = []
        for a, b, c, d in MAPS[idx][1]:
            a, c = a * 2 - 1, c * 2 - 1
            b, d = b * 1.4 - 0.7, d * 1.4 - 0.7
            h = 0.24 * grow
            faces.extend(
                [
                    ([(a, b, 0), (c, b, 0), (c, b, h), (a, b, h)], T.ARMOR),
                    ([(c, b, 0), (c, d, 0), (c, d, h), (c, b, h)], T.SHELL),
                    ([(a, b, h), (c, b, h), (c, d, h), (a, d, h)], T.GLASS),
                ]
            )
        for points, color in sorted(faces, key=lambda item: sum(v[1] for v in item[0])):
            p.polygon(
                flat(points), fill=color, outline=T.GRID_BRIGHT, width=1, tags=tags
            )
        p.end()


class RiderPreview:
    """Rotação pelo centro, corpo e rastro contidos na faixa reservada à prévia."""

    def __init__(self, canvas, model, color, box):
        self.cv, self.model, self.color, self.box = canvas, model, color, box
        x0, y0, x1, y1 = box
        self.center = ((x0 + x1) / 2, (y0 + y1) / 2)
        a, b, c, d = model_bounds(model)
        diagonal = math.hypot(c - a, d - b) * UNIT
        self.scale = min(3.4, (min(x1 - x0, y1 - y0) - 8) / (diagonal + 4))
        self.trail = [
            canvas.create_line(0, 0, 0, 0, fill=tint, width=weight, tags="ui")
            for tint, weight in T.glow_layers(color, 1.2)
        ]
        x, y = centered_origin(model, *self.center, scale=self.scale)
        self.items = draw_bike(
            canvas, x, y, (1, 0), color, model, self.scale, tags="ui"
        )
        self.draw(0.0)

    def draw(self, t):
        angle = round(t * 0.35 * 8 / math.tau) * math.tau / 8
        direction = (math.cos(angle), math.sin(angle))
        x, y = centered_origin(self.model, *self.center, direction, self.scale)
        move_bike(
            self.cv, self.items, self.model, x, y, direction, self.scale, elapsed=t
        )
        # O rastro acompanha a traseira; sua ponta distante é recortada dentro da prévia.
        tail = model_bounds(self.model)[0] * UNIT * self.scale
        end = (x + direction[0] * tail, y + direction[1] * tail)
        length = min(72, (self.box[2] - self.box[0]) * 0.28)
        for axis, component in enumerate(direction):
            if abs(component) < 1e-8:
                continue
            bound = self.box[axis] + 5 if component > 0 else self.box[axis + 2] - 5
            length = min(length, max(0, (end[axis] - bound) / component))
        start = (end[0] - direction[0] * length, end[1] - direction[1] * length)
        for item in self.trail:
            self.cv.coords(item, *start, *end)


class MenuScreens:
    def draw_background(self, cv=None, live=True):
        cv = cv if cv is not None else self.cv
        scene = MenuScene(cv, self.W, self.H, live)
        if live:
            self.scene = scene
            self.stadium_scene = scene.stadium
            self.stadium = scene.stadium.bounds
            self.menu_race = scene.race
            self.beam = scene.beam
            self.hz = self.H * 0.36

    def project(self, x, y, h=0):
        return self.scene.project(x, y, h)

    def draw_title(self):
        self.brand = ui.TubeLogo(self.cv, brand_box(self.W, self.H))
        self.title_glow = []
        self.title_line = self.cv.create_line(
            self.W * 0.2,
            self.H * 0.225,
            self.W * 0.61,
            self.H * 0.225,
            fill=T.GRID_BRIGHT,
            tags="title",
        )
        ui.text(
            self.cv,
            self.W * 0.405,
            self.H * 0.255,
            "LIGHT CYCLE ULTIMATE",
            14,
            T.CORE,
            "center",
            "title",
        )
        self.disc = ui.IdentityDisc(
            self.cv, self.W * 0.90, self.H * 0.13, min(54, self.H * 0.065)
        )

    def _button(self, key, box, label, command, size=14):
        return self.ui.add(
            ui.Button(
                self.cv,
                key,
                box,
                label,
                command=lambda: self._invoke(command),
                focus=self.set_focus,
                size=size,
            )
        )

    def _selector(self, key, box, label, value, change, size=14, activate=None):
        if box[2] - box[0] > 360:
            middle = (box[0] + box[2]) / 2
            box = (middle - 180, box[1], middle + 180, box[3])
        return self.ui.add(
            ui.Selector(
                self.cv,
                key,
                box,
                label,
                value,
                change,
                activate=activate,
                focus=self.set_focus,
                size=size,
            )
        )

    def _toggle(self, key, box, label, value, command, description="", size=14):
        return self.ui.add(
            ui.Toggle(
                self.cv,
                key,
                box,
                label,
                value,
                command,
                description,
                focus=self.set_focus,
                size=size,
            )
        )

    def _invoke(self, command):
        self.finish_arrival()
        self.controller.sound.play("menu_select")
        command()

    def section(self, x, y, label):
        ui.text(self.cv, x, y, label, 13, T.CYAN, bold=True)

    def draw_ui(self):
        if self.page != "title" and getattr(self,"arrival_active",False):
            self.finish_arrival()
        self.cv.delete("ui")
        self.ui = ui.Registry()
        self.layout = ui.Layout(self.W, self.H)
        self.map_preview = None
        self.rider_previews = []
        self.preview_glows = []
        self.sel_card = None
        self.cv.itemconfig(
            "title", state="normal" if self.page == "title" else "hidden"
        )
        if self.page == "title":
            self.draw_title_buttons()
        elif self.page == "mode":
            self.draw_modes_page()
        elif self.page == "options":
            self.draw_options()
        else:
            self.draw_setup()
        self.focus_boxes = self.ui.boxes
        if self.focus not in self.focus_boxes:
            self.focus = (
                self.setup_primary_focus()
                if self.page == "setup"
                else next(iter(self.focus_boxes), "play")
            )
        if self.focus not in self.focus_boxes:
            self.focus = next(iter(self.focus_boxes))
        self.draw_focus()
        ui.text(self.cv, self.W - 24, self.H - 8, "v" + T.VERSION, 10, T.MUTED, "se")
        if self.rgb:
            self.draw_rgb_panel()

    def draw_title_buttons(self):
        choices = (
            ("play", "ARENA CLÁSSICA", self.show_modes),
            ("chase", "PERSEGUIÇÃO", self.controller.start_chase),
            ("options", "OPÇÕES", self.show_options),
            ("exit", "SAIR", self.controller.quit_game),
        )
        for box, (key, label, command) in zip(title_boxes(self.W, self.H), choices):
            self._button(key, box, label, command, 16)
        ui.text(
            self.cv,
            self.W * 0.62,
            self.H * 0.43,
            "ARENA AO VIVO  /  3 PILOTOS",
            12,
            T.MUTED,
            "center",
        )

    def draw_modes_page(self):
        ui.text(
            self.cv,
            self.W / 2,
            self.layout.header * 0.55,
            "ESCOLHA O MODO",
            22,
            T.CORE,
            "center",
            bold=True,
        )
        x0, y0, x1, y1 = self.layout.content
        gap = 16
        columns = 3 if self.W >= 1000 else 2
        rows = math.ceil(len(self.MODES) / columns)
        cw = (x1 - x0 - gap * (columns - 1)) / columns
        ch = (y1 - y0 - gap * (rows - 1)) / rows
        self.card_pos = {}
        for i, (key, label, description, icons) in enumerate(self.MODES):
            x = x0 + i % columns * (cw + gap)
            y = y0 + i // columns * (ch + gap)
            compact = ch < 120
            card = self._button(
                ("mode", key),
                (x, y, x + cw, y + ch),
                "" if compact else label,
                lambda k=key: self.open_mode(k),
                14,
            )
            if compact:
                ui.text(
                    self.cv,
                    x + cw * 0.62,
                    y + ch * 0.32,
                    label,
                    13,
                    T.CORE,
                    "center",
                    card.tags,
                    bold=True,
                )
            ui.text(
                self.cv,
                x + cw * (0.62 if compact else 0.5),
                y + ch * 0.70 if compact else y + ch - 24,
                description,
                11 if compact else 12,
                T.MUTED,
                "center",
                tags=card.tags,
                width=cw * (0.68 if compact else 1) - 24,
            )
            for j, (pid, ox, oy, d) in enumerate(icons):
                draw_bike(
                    self.cv,
                    x + cw * (0.16 if compact else 0.5) + ox * 2,
                    y + ch * (0.5 if compact else 0.28) + oy * 1.6,
                    d,
                    T.ORANGE if key == "rinzler" and pid == 2 else self.color(pid),
                    self.model_idx[pid],
                    0.7 if compact else 1.0,
                    tags=card.tags,
                )
            self.card_pos[key] = (x + cw / 2, y + ch / 2)
        self.draw_actions(
            "back_title",
            "VOLTAR",
            self.show_title,
            "next",
            "CONFIGURAR",
            lambda: self.open_mode(self.mode),
        )

    def open_mode(self, key):
        self.set_mode(key)
        self.focus = ("mode", key)
        self.show_setup()

    def draw_actions(
        self,
        left_key,
        left_label,
        left_command,
        right_key=None,
        right_label=None,
        right_command=None,
    ):
        y = self.layout.actions_y
        width = min(280, (self.W - 96) / 2)
        if right_key:
            self._button(
                left_key,
                (self.W / 2 - width - 8, y - 24, self.W / 2 - 8, y + 24),
                left_label,
                left_command,
            )
            self._button(
                right_key,
                (self.W / 2 + 8, y - 24, self.W / 2 + width + 8, y + 24),
                right_label,
                right_command,
            )
        else:
            self._button(
                left_key,
                (self.W / 2 - width / 2, y - 24, self.W / 2 + width / 2, y + 24),
                left_label,
                left_command,
            )

    def draw_setup(self):
        ui.text(
            self.cv,
            self.layout.margin,
            self.layout.header * 0.45,
            "CONFIGURAR PARTIDA",
            20,
            T.CORE,
            bold=True,
        )
        width = min(264, self.W * 0.31)
        self._toggle(
            "config_level",
            (self.W - self.layout.margin - width, 8, self.W - self.layout.margin, 56),
            "Modo avançado",
            self.advanced_config,
            self.toggle_config_level,
            size=12,
        )
        tabs = ui.Tabs(
            self.cv,
            self.layout.tabs,
            (("arena", "ARENA"), ("rules", "REGRAS"), ("riders", "PILOTOS")),
            self.setup_step,
            self.set_setup_step,
            self.set_focus,
        )
        self.ui.controls.update(tabs.controls)
        ui.panel(self.cv, self.layout.content)
        if self.setup_step == "arena":
            self.draw_arena_page()
        elif self.setup_step == "rules":
            self.draw_rules_page()
        else:
            self.draw_riders_page()
        index = ("arena", "rules", "riders").index(self.setup_step)
        self.draw_actions(
            "back",
            "MODOS" if not index else "ANTERIOR",
            self.go_back,
            "start",
            "INICIAR PARTIDA" if index == 2 else "CONTINUAR",
            self.go_forward,
        )

    def draw_arena_page(self):
        x0, y0, x1, y1 = self.layout.content
        x0 += 16
        x1 -= 16
        y0 += 24
        width = (x1 - x0) * 0.43
        self.section(x0, y0, "ARENA")
        value = "SORTEAR MAPA" if self.map_idx == RANDOM_MAP else MAPS[self.map_idx][0]
        self._selector(
            "map", (x0, y0 + 24, x0 + width, y0 + 80), "Mapa", value, self.set_map
        )
        self._toggle(
            "mod_trail",
            (x0, y0 + 96, x0 + width, y0 + 160),
            "Rastro efêmero",
            self.modifiers["fading_trail"],
            lambda: self.set_modifier("fading_trail"),
            "Libera espaço com o tempo",
            size=13,
        )
        self._selector(
            "trail_duration",
            (x0, y0 + 176, x0 + width, y0 + 232),
            "Duração do rastro",
            f"{self.trail_fade_sec:.0f} segundos",
            self.adjust_trail_duration,
        )
        box = (x0 + width + 32, y0 + 24, x1, y1 - 16)
        self.section(box[0], y0, "PRÉVIA DA ARENA")
        self.map_preview = MapPreview(self.cv, box, self.map_idx, self.map_changed_at)
        self.map_preview.draw(self.t)

    def draw_rules_page(self):
        a, b, c, d = self.layout.content
        a += 16
        b += 16
        c -= 16
        gap = 32
        left_w = (c - a) * 0.56
        right = a + left_w + gap
        self.section(a, b, "PARTIDA")
        if self.mode == "rinzler":
            ui.text(self.cv, a, b + 48, "Sobreviva ao duelo", 18, T.ORANGE)
        else:
            self._selector(
                "target",
                (a, b + 24, a + left_w, b + 80),
                (
                    "Objetos para vencer"
                    if self.modifiers["collect_items"]
                    else "Pontos para vencer"
                ),
                self.match_target,
                self.set_target,
            )
        self.section(a, b + 104, "MODIFICADORES")
        if self.advanced_config and self.mode != "rinzler":
            choices = (
                ("shrinking_arena", "Encolher arena", "Bordas em movimento"),
                ("lightning_round", "Relâmpago", "Velocidade crescente"),
                ("collect_items", "Coleta", "Pontue coletando"),
                ("lives", "Vidas extras", "Volte após colidir"),
            )
            cw = (left_w - 16) / 2
            for i, (key, label, description) in enumerate(choices):
                x = a + i % 2 * (cw + 16)
                y = b + 128 + i // 2 * 72
                self._toggle(
                    "mod_" + key,
                    (x, y, x + cw, y + 64),
                    label,
                    self.modifiers[key],
                    lambda k=key: self.set_modifier(k),
                    description,
                    size=12 if cw < 240 else 14,
                )
        else:
            ui.text(
                self.cv,
                a,
                b + 144,
                "Ative o modo avançado para personalizar.",
                12,
                T.MUTED,
                width=left_w,
            )
        self.section(right, b, "JOGADORES")
        width = c - right
        y = b + 24
        if self.mode == "training":
            if self.advanced_config:
                row_h = 40 if d - b < 320 else 48
                self._selector(
                    "training_players",
                    (right, y, c, y + row_h),
                    "Total de motos",
                    4 if self.training_teams else self.training_player_count,
                    self.set_training_players,
                    13,
                )
                y += row_h + 8
                self._selector(
                    "training_humans",
                    (right, y, c, y + row_h),
                    "Humanos",
                    self.training_human_count,
                    self.set_training_humans,
                    13,
                )
                y += row_h + 8
                ui.text(
                    self.cv,
                    right,
                    y + 8,
                    f"IA: {(4 if self.training_teams else self.training_player_count)-self.training_human_count} pilotos",
                    12,
                    T.MUTED,
                )
                y += 24
                self._toggle(
                    "training_teams",
                    (right, y, c, y + 48),
                    "Equipes 2v2",
                    self.training_teams,
                    self.toggle_training_teams,
                    size=12,
                )
                y += 56
            else:
                self._selector(
                    "ai_count",
                    (right, y, c, y + 56),
                    "Adversários IA",
                    self.ai_count,
                    self.set_ai_count,
                    14,
                )
                y += 72
            self._selector(
                "ai_level",
                (right, y, c, y + 48),
                "Dificuldade da IA",
                dict(AI_LEVELS)[self.ai_level],
                self.set_ai_level,
                13,
            )
        else:
            count = 4 if self.mode in ("ffa4", "team2v2") else 2
            ui.text(self.cv, right, y + 16, f"{count} pilotos na arena", 16, T.CORE)
            ui.text(
                self.cv,
                right,
                y + 56,
                "Equipes 2v2" if self.mode == "team2v2" else "Cada piloto por si",
                13,
                T.MUTED,
                width=width,
            )

    def draw_riders_page(self):
        a, b, c, d = self.layout.content
        a += 16
        b += 16
        c -= 16
        d -= 16
        team = self.mode == "team2v2" or self.mode == "training" and self.training_teams
        owners = (
            [("team_color", 1), ("team_color", 2)]
            if team
            else [("color", pid) for pid in self.active_player_ids()]
        )
        gap = 16
        cw = (c - a - gap * (len(owners) - 1)) / len(owners)
        compact = d - b < 360
        for i, owner in enumerate(owners):
            kind, who = owner
            x = a + i * (cw + gap)
            center = x + cw / 2
            members = ((1, 3) if who == 1 else (2, 4)) if team else (who,)
            pid = members[0]
            color = self.color(pid)
            ai = not team and self.is_ai(pid)
            ui.panel(
                self.cv, (x, b, x + cw, d), T.PANEL, T.blend(color, T.BACKGROUND, 0.55)
            )
            ui.text(
                self.cv,
                center,
                b + 18,
                (
                    f"EQUIPE {who}"
                    if team
                    else f"P{pid} / {'IA' if ai else self.controller.input_label(pid)}"
                ),
                13,
                color,
                "center",
                bold=True,
            )
            for j, pilot in enumerate(members):
                model = 1 if ai and self.mode == "rinzler" else self.model_idx[pilot]
                preview_width = cw / len(members)
                box = (
                    x + j * preview_width + 12,
                    b + (32 if compact else 40),
                    x + (j + 1) * preview_width - 12,
                    b + (88 if compact else 136),
                )
                self.rider_previews.append(RiderPreview(self.cv, model, color, box))
            if ai:
                ui.text(
                    self.cv,
                    center,
                    b + (128 if compact else 196),
                    "COR E MOTO\nSORTEADAS" if self.mode == "training" else "RINZLER",
                    14,
                    T.MUTED,
                    "center",
                )
                continue
            pal_y = b + (104 if compact else 152)
            spacing = min(24, (cw - 24) / 8)
            for index, (name, tint) in enumerate(COLOR_PALETTE):
                xx = center + (index % 8 - 3.5) * spacing
                yy = pal_y + (index // 8) * 24
                locked = (
                    self.team_color_is_taken(who, index)
                    if team
                    else self.color_is_taken(pid, index)
                )
                tag = f"palette_{who}_{index}"
                selected = (
                    self.team_color_idx[who] if team else self.color_idx[pid]
                ) == index
                self.cv.create_oval(
                    xx - 7,
                    yy - 7,
                    xx + 7,
                    yy + 7,
                    fill=T.blend(tint, T.BACKGROUND, 0.75) if locked else tint,
                    outline=T.CORE if selected else T.GRID_BRIGHT,
                    width=2 if selected else 1,
                    tags=("ui", tag),
                )
                self.swatch_pos[("team", who, index) if team else (pid, index)] = (
                    xx,
                    yy,
                )
                if not locked:
                    self.cv.tag_bind(
                        tag, "<Enter>", lambda event, owner=owner: self.set_focus(owner)
                    )
                    command = (
                        (
                            lambda who=who, index=index, xx=xx, yy=yy: self.set_team_color(
                                who, index, xx, yy
                            )
                        )
                        if team
                        else (
                            lambda pid=pid, index=index, xx=xx, yy=yy: self.set_color(
                                pid, index, xx, yy
                            )
                        )
                    )
                    self.cv.tag_bind(
                        tag, "<Button-1>", lambda event, cmd=command: cmd()
                    )
            current = self.team_color_idx[who] if team else self.color_idx[pid]
            value = (
                "RGB" if current == len(COLOR_PALETTE) else COLOR_PALETTE[current][0]
            )

            def adjust_color(step, owner=owner):
                self.focus = owner
                self.adjust(step)

            color_y = b + (144 if compact else 208)
            self._selector(
                owner,
                (x + 8, color_y, x + cw - 8, color_y + (40 if compact else 48)),
                "Cor / RGB",
                value,
                adjust_color,
                12,
                activate=lambda owner=owner: self.open_rgb(owner),
            )
            self.swatch_pos[
                ("team", who, len(COLOR_PALETTE)) if team else (pid, len(COLOR_PALETTE))
            ] = (center, color_y + (20 if compact else 24))
            mw = (cw - 24 - (8 if team else 0)) / len(members)
            for j, pilot in enumerate(members):
                xx = x + 8 + j * (mw + 8)
                self._selector(
                    ("model", pilot),
                    (xx, d - 56, xx + mw, d - 8),
                    "Moto" if not team else f"Moto P{pilot}",
                    CYCLES[self.model_idx[pilot]].name,
                    lambda step, pilot=pilot: self.set_model(pilot, step),
                    12 if cw < 260 or team else 14,
                )

    def draw_options(self):
        ui.text(
            self.cv,
            self.W / 2,
            self.layout.header * 0.6,
            "OPÇÕES",
            24,
            T.CORE,
            "center",
            bold=True,
        )
        a, b, c, d = self.layout.content
        width = min(520, c - a - 32)
        x = (self.W - width) / 2
        self.section(x, b, "ÁUDIO")
        sound = self.controller.sound
        for i, (key, label, attribute, setter) in enumerate(
            (
                ("music", "Música", "music_level", sound.set_music_level),
                ("sfx", "Efeitos", "sfx_level", sound.set_sfx_level),
                (
                    "engine",
                    "Motor da perseguição",
                    "engine_level",
                    sound.set_engine_level,
                ),
            )
        ):
            level = getattr(sound, attribute, 1.0)
            if not isinstance(level, (float, int)):
                level = 1.0
            self._selector(
                key,
                (x, b + 24 + i * 64, x + width, b + 80 + i * 64),
                label,
                f"{int(level*100)}%",
                lambda step, l=level, s=setter: self.change_volume(s, l, step),
            )
        self._button(
            "replay_intro",
            (x, b + 224, x + width, b + 272),
            "REPRODUZIR INTRODUÇÃO",
            self.controller.show_intro,
        )
        self.draw_actions("back_title", "VOLTAR", self.show_title)

    def change_volume(self, setter, value, step):
        setter(max(0, min(1, round(value + step * 0.1, 2))))
        self.controller.sound.play("menu_move")
        self.draw_ui()

    def show_options(self):
        self.page = "options"
        self.focus = "music"
        self.set_blur(True)
        self.draw_ui()

    def draw_focus(self):
        self.cv.delete("focus_mark")
        self.ui.paint(self.focus, self.t)
        box = self.focus_boxes.get(self.focus)
        if box:
            self.focus_rect = ui.corners(
                self.cv,
                (box[0] - 4, box[1] - 4, box[2] + 4, box[3] + 4),
                tags=("ui", "focus_mark"),
            )[0]
        self.draw_hints()

    def set_focus(self, key, sound=True):
        if key == self.focus or key not in self.focus_boxes:
            return
        self.focus = key
        if isinstance(key, tuple) and key[0] == "mode":
            self.mode = key[1]
        if sound:
            self.controller.sound.play("menu_move")
        self.draw_focus()

    def help_line(self):
        if isinstance(self.focus, tuple) and self.focus[0] in ("color", "team_color"):
            change = "LB RB" if INPUT.use_pad else "Q E"
            return f"{change} trocam a cor. {INPUT.confirm_name()} abre o editor RGB."
        return {
            "play": "Configure uma partida na arena.",
            "chase": "Entre direto na perseguição a Rinzler.",
            "options": "Áudio e apresentação.",
            "music": "Volume da trilha; Legacy Open continua até o fim no menu.",
            "sfx": "Volume dos efeitos e dos sons de navegação.",
            "engine": "Ajusta o loop de motor sem alterar os outros efeitos.",
            "replay_intro": "Assista à sequência inicial novamente.",
            "start": (
                "Inicia a partida."
                if self.setup_step == "riders"
                else "Continua para a próxima etapa."
            ),
            "back": "Volta à etapa anterior.",
        }.get(self.focus if isinstance(self.focus, str) else "", help_for(self.focus))

    def draw_hints(self):
        self.cv.delete("hint")
        y = self.layout.help_y if self.page != "title" else self.H - 76
        message = self.help_line()
        if message:
            ui.text(
                self.cv,
                self.W / 2 + 1,
                y + 1,
                "i  " + message,
                14,
                T.BACKGROUND,
                "center",
                ("ui", "hint"),
                width=self.W - 64,
            )
            ui.text(
                self.cv,
                self.W / 2,
                y,
                "i  " + message,
                14,
                T.CORE,
                "center",
                ("ui", "hint"),
                width=self.W - 64,
            )
        groups = (
            [("SETAS", "navegar"), ("Q E", "alterar")]
            if self.page in ("setup", "options")
            else [("SETAS", "escolher")]
        )
        groups.extend(
            [
                ("ENTER", "confirmar"),
                (
                    "B" if INPUT.use_pad else "ESC" if self.page == "title" else "BACK",
                    "voltar" if self.page != "title" else "sair",
                ),
            ]
        )
        if INPUT.use_pad:
            groups = [
                ("D-PAD", "navegar"),
                (INPUT.label("a"), "confirmar"),
                (INPUT.label("b"), "voltar"),
            ] + ([("LB RB", "alterar")] if self.page in ("setup", "options") else [])
        ui.keycaps(self.cv, self.W / 2, self.layout.keys_y, groups, 12)

    def navigate(self, dx, dy):
        self.finish_arrival()
        if self.rgb:
            return
        if self.focus not in self.ui.controls:
            return
        if dx:
            dy = 0  # diagonal: horizontal primeiro, como no direcional
        if dx and isinstance(self.focus, tuple) and self.focus[0] == "setup_step":
            self.move_setup_step(dx, True)
            return
        boxes = {
            key: control.box
            for key, control in self.ui.controls.items()
            if getattr(control, "visible", True) or key == self.focus
        }
        control = self.ui.controls[self.focus]
        if dx and isinstance(control, (ui.Selector, ui.Toggle)):
            y0, y1 = boxes[self.focus][1], boxes[self.focus][3]
            # Sozinho na linha: ← → mudam o valor; com vizinhos ao lado, andam entre eles.
            if not any(b[1] < y1 and b[3] > y0 for k, b in boxes.items() if k != self.focus):
                control.change(dx)
                return
        target = spatial_neighbor(boxes, self.focus, dx, dy)
        if target is not None:
            self.set_focus(target)

    def shift(self, step):
        """LB/RB, Q/E: muda o valor do item em foco (nas abas e botões de baixo, troca de etapa)."""
        self.finish_arrival()
        if self.rgb:
            return
        control = self.ui.controls.get(self.focus)
        if isinstance(control, (ui.Selector, ui.Toggle)):
            control.change(step)
        else:
            self.adjust(step)

    def activate(self):
        self.finish_arrival()
        if isinstance(self.focus, tuple) and self.focus[0] in ("color", "team_color"):
            self.open_rgb(self.focus)
        elif self.focus in self.ui.controls:
            self.ui.controls[self.focus].invoke()

    def on_key(self, event):
        k = event.keysym
        if self.rgb:
            if k in ("Up", "Down", "Left", "Right"):
                self.rgb_input(
                    "dir",
                    {"Up": (0, -1), "Down": (0, 1), "Left": (-1, 0), "Right": (1, 0)}[
                        k
                    ],
                )
            elif k in ("Return", "BackSpace"):
                self.rgb_input("button", "a" if k == "Return" else "b")
            return
        if k == "Return":
            self.activate()
        elif k in ("Left", "Right"):
            self.navigate(1 if k == "Right" else -1, 0)
        elif k in ("Up", "Down"):
            self.navigate(0, 1 if k == "Down" else -1)
        elif k == "BackSpace":
            self.go_back()
        elif k.lower() in ("q", "e") or k in ("Prior", "Next"):
            self.shift(-1 if k.lower() == "q" or k == "Prior" else 1)

    def on_escape(self):
        if self.rgb:
            self.rgb_close(False)
        elif self.page == "title":
            self.controller.quit_game()
        else:
            self.go_back()

    def on_pad(self, pid, kind, value):
        if self.rgb:
            self.rgb_input(kind, value)
        elif kind == "dir":
            self.navigate(*value)
        elif kind == "button":
            if value == "a":
                self.activate()
            elif value == "b":
                self.go_back()
            elif value == "start":
                self.go_forward()
            elif value in ("lb", "rb"):
                self.shift(-1 if value == "lb" else 1)

    def go_back(self):
        if self.page == "setup":
            if self.setup_step == "arena":
                self.show_modes()
            else:
                self.move_setup_step(-1)
        elif self.page in ("mode", "options"):
            self.show_title()

    def go_forward(self):
        if self.page == "title":
            self.activate()
        elif self.page == "mode":
            self.show_setup()
        elif self.page == "setup":
            if self.setup_step == "riders":
                self.on_start()
            else:
                self.move_setup_step(1)

    def loop(self):
        now = time.perf_counter()
        dt = min(0.1, now - self.last)
        self.last = now
        self.t += dt
        self.update_blur(dt)
        if self.blur_k == 0:
            self.menu_race.advance(dt)
            self.stadium_scene.animate(self.t)
        if self.page == "title":
            self.brand.animate(self.t + 1 if self.from_intro and not self.arrival_active else self.t)
            self.disc.animate(self.t)
        self.ui.paint(self.focus, self.t)
        if self.arrival_active:
            self.update_arrival(self.t)
        if self.map_preview:
            self.map_preview.draw(self.t)
        for preview in self.rider_previews:
            preview.draw(self.t)
        self.fx.update(dt)
        self.after_id = self.after(FRAME_MS, self.loop)

    def finish_arrival(self):
        if getattr(self,"arrival_active",False):
            self.update_arrival(3)

    def update_arrival(self, age):
        """O menu responde durante a chegada; uma entrada conclui o acendimento."""
        if self.page != "title":
            age = 3
        self.cv.itemconfig("title",state="normal" if age > 0 else "hidden")
        self.brand.animate(age, min(1,age/.35))
        for index,key in enumerate(("play","chase","options","exit")):
            button = self.ui.controls.get(key)
            if button is not None:
                gain = max(0,min(1,(age-.32-index*.18)/.24))
                button.set_visible(gain>0)
                if gain:
                    button.paint(key==self.focus,self.t,gain)
        self.cv.itemconfig("focus_mark",state="normal" if age>.32 else "hidden")
        self.cv.itemconfig("hint",state="normal" if age>1.05 else "hidden")
        self.stadium_scene.reveal(age-1.15)
        if age>=2.2:
            self.arrival_active=False

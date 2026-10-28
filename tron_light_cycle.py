import tkinter as tk
from tkinter import font as tkfont
from pathlib import Path
import sys
import time
import math
import random
from collections import deque

# Importação dos módulos do projeto
from config import (
    BG_COLOR,
    GRID_COLOR,
    GRID_PULSE,
    CELL,
    BORDER_MARGIN,
    MATCH_TARGET,
    CYAN,
    PALETTES,
    COLOR_PALETTE,
    MAPS,
    RANDOM_MAP,
    KEY_LOOKUP,
    KEY_LAYOUTS,
    MAX_PLAYERS,
    FRAME_MS,
    TICK_START_MS,
    TICK_MIN_MS,
    TICK_RAMP,
    DISSOLVE_DELAY,
    DISSOLVE_SEC,
    ROUND_RESTART_COOLDOWN_MS,
    TRAIL_FADE_OPTIONS,
    TRAIL_FADE_SEC,
    LIGHTNING_TICK_FACTOR,
    SHRINK_START_SEC,
    SHRINK_STEP_SEC,
    PORTAL_COLOR,
    RINZLER_BOOST_COOLDOWN_SEC,
    RINZLER_BOOST_DURATION_SEC,
    RINZLER_BOOST_INTERVAL_SEC,
    AI_LEVELS,
    MENU_BLUR_RADIUS,
    MENU_DIM,
    MENU_BLUR_SEC,
    map_options,
    blend,
)
from effects import Effects, BIKES
from sound import SoundManager
from gamepad import GamepadManager, SHORT_NAMES, FAMILY_NAMES
from menu_nav import (
    INPUT,
    pause_hints,
    victory_hints,
    rgb_hints,
    rgb_button_label,
    start_prompt,
)
import ai
import backdrop
import theme as T
from sprites_topview import CYCLES, draw_bike, move_bike
from arena_presentation import ArenaChrome
from intro import IntroFrame
from menu_screens import MenuScreens

DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]
CUSTOM = len(COLOR_PALETTE)  # índice extra da paleta = cor RGB personalizada
WALL_GAP = 10  # px mínimos entre a moto e a linha da borda
OBSTACLE_GAP = 7  # px mínimos entre a moto e um obstáculo


def draw_control_prompt(cv, x, y, segments, font, fill, tags):
    """Desenha uma dica centralizada. Os botões do controle viram "teclas" redondas com o nome certo
    para o controle em uso (A B X Y no Xbox, × ○ □ ▲ no PlayStation...)."""
    font_obj = tkfont.Font(root=cv, font=font)
    height = max(font_obj.metrics("linespace") - 1, 14)
    parts = []
    total_width = 0
    for kind, value in segments:
        if kind == "button":
            text = INPUT.label(value)
            width = max(height, font_obj.measure(text) + 8)
        else:
            text = value
            width = font_obj.measure(value)
        parts.append((kind, value, text, width))
        total_width += width

    cursor = x - total_width / 2
    items = []
    for kind, value, text, width in parts:
        if kind == "button":
            color = INPUT.color(value)
            items.append(
                cv.create_oval(
                    cursor,
                    y - height / 2,
                    cursor + width,
                    y + height / 2,
                    fill="#07111B",
                    outline=color,
                    width=1,
                    tags=tags,
                )
            )
            items.append(
                cv.create_text(
                    cursor + width / 2,
                    y,
                    text=text,
                    font=("Courier", max(7, font_obj.cget("size") - 1), "bold"),
                    fill=color,
                    tags=tags,
                )
            )
        else:
            items.append(
                cv.create_text(
                    cursor,
                    y,
                    text=text,
                    anchor=tk.W,
                    font=font,
                    fill=fill,
                    tags=tags,
                )
            )
        cursor += width
    return items


def draw_round_start_prompt(cv, x, y, segments, tag):
    font = ("Courier", 17, "bold")
    font_obj = tkfont.Font(root=cv, font=font)
    height = max(font_obj.metrics("linespace"), 18)
    width = sum(
        (
            max(height, font_obj.measure(INPUT.label(value)) + 8)
            if kind == "button"
            else font_obj.measure(value)
        )
        for kind, value in segments
    )
    half_w, half_h = width / 2 + 22, height / 2 + 10
    cv.create_rectangle(
        x - half_w - 5,
        y - half_h - 5,
        x + half_w + 5,
        y + half_h + 5,
        fill="",
        outline=blend(BG_COLOR, CYAN, 0.55),
        width=2,
        dash=(3, 4),
        tags=("game_obj", tag),
    )
    cv.create_rectangle(
        x - half_w,
        y - half_h,
        x + half_w,
        y + half_h,
        fill="#030B14",
        outline=CYAN,
        width=2,
        tags=("game_obj", tag),
    )
    return draw_control_prompt(
        cv,
        x,
        y,
        segments,
        font,
        "#FFFFFF",
        ("game_obj", tag),
    )


class Rider:
    """Representa uma moto (jogador ou IA) na arena, estruturada para integração com o módulo ai.py."""

    def __init__(self, pid, cell, direction, color, model=0):
        self.pid = pid
        self.cell = cell  # Posicionamento em coordenadas de célula da grade
        self.dir = direction  # Direção atual (dx, dy)
        self.alive = True
        self.queue = []  # Fila de comandos de direção (input buffer)
        self.color = color
        self.model = model  # Índice em effects.BIKES
        # Só os vértices das curvas + a cabeça (últimos 2 valores): o tamanho não cresce com o tempo de rodada
        self.trail = [cell[0] * CELL, cell[1] * CELL, cell[0] * CELL, cell[1] * CELL]
        self.line_halo = None
        self.line_glow = None
        self.line_core = None
        self.bike = []  # Itens do canvas que desenham a moto
        self.spark_ids = []
        self.is_ai = False
        ai.reset(self)
        self.hint_ids = ()
        self.hint_until = 0.0
        self.prev_cell = cell  # célula do tick anterior (a moto é desenhada interpolando prev_cell -> cell)
        self.turned = (
            False  # virou neste tick? (então a cabeça atual vira um vértice do rastro)
        )
        self.cells = {cell}  # células ocupadas por este rastro (para liberar ao morrer)
        # Rastro efêmero (modificador): None = o rastro é permanente; senão, segundos de vida de cada trecho.
        # É uma propriedade de cada moto, então dá para usar só em algumas (ex.: no Rinzler).
        self.trail_life = None
        self.path = deque(
            [(0.0, cell)]
        )  # (instante de jogo, célula) de cada passo; path[0] é a cauda
        self.vidx = [
            0
        ]  # índice, no caminho, de cada vértice do rastro (menos a cabeça)
        self.steps = 0  # passos dados (índice da cabeça no caminho)
        self.tail = 0  # passos já apagados pela cauda
        # Travessia de portais: a linha é quebrada em peças. As antigas ficam fixas aqui (mais velha primeiro);
        # `trail`/`vidx`/`line_*` são sempre a peça atual, onde está a cabeça.
        self.old = deque()
        self.cur_first = 0  # índice, no caminho, da primeira célula da peça atual
        self.is_rinzler = False
        self.lives = 1
        self.boost_until = 0.0
        self.next_boost_at = 0.0
        self.next_boost_step = 0.0


class LightCycleGame:
    """Controlador principal do jogo, gerenciando telas, placares, áudio e estados globais."""

    def __init__(self, root, play_intro=True):
        self.root = root
        self.root.configure(bg=BG_COLOR)
        self.root.title("TRON: LIGHT CYCLE ULTIMATE")
        assets = Path(__file__).resolve().parent / "assets"
        self.icon_image = tk.PhotoImage(
            data=(assets / "tron_icon.png").read_bytes(), master=root
        )
        self.root.iconphoto(True, self.icon_image)
        if sys.platform == "win32":
            self.root.iconbitmap(str(assets / "tron_icon.ico"))
        self.root.attributes("-fullscreen", True)

        # Inicializar gerenciador de som
        self.sound = SoundManager()
        self.music_after_id = self.root.after(25, self.update_music)

        # Controles (Xbox etc.): lidos a cada ~8 ms e repassados para a tela atual
        self.pads = GamepadManager()
        INPUT.sync(self.pads)
        self.pad_notice = self.pad_notice_frame = self.pad_notice_after = None
        self.pad_notice_connected = False
        self.pending_pad_notice = None
        self.menu_from_intro = False
        # Qual dispositivo o jogador usou por último (teclado/mouse ou controle): as dicas na tela seguem isso
        self.root.bind_all("<KeyPress>", self.note_keyboard, add="+")
        self.root.bind_all("<Button-1>", self.note_keyboard, add="+")

        # Obter resolução real da tela
        self.screen_width = root.winfo_screenwidth()
        self.screen_height = root.winfo_screenheight()

        # Atalhos globais
        self.root.bind("<Escape>", lambda e: self.on_escape())
        self.root.bind("r", lambda e: self.reset_match())
        self.root.bind("R", lambda e: self.reset_match())

        # Placar global da partida
        self.scores = {1: 0, 2: 0, 3: 0, 4: 0}
        self.match_target = MATCH_TARGET
        self.ai_count = 1
        self.ai_level = "normal"
        self.trail_fade_sec = TRAIL_FADE_SEC
        self.training_player_count = 2
        self.training_human_count = 1
        self.training_teams = False
        self.advanced_config = False
        self.modifiers = {
            "fading_trail": False,
            "shrinking_arena": False,
            "lightning_round": False,
            "collect_items": False,
            "lives": False,
        }  # modificadores de partida (o menu lembra a escolha)

        # Configurações padrão de jogo (o menu lembra a última escolha)
        self.game_mode = "1v1"  # "1v1", "ffa4", "team2v2", "training", "rinzler"
        defaults = {1: CYAN, 2: T.RED, 3: T.GREEN, 4: T.ORANGE}
        self.colors = defaults
        self.models = {1: 0, 2: 1, 3: 2, 4: 1}
        self.map_idx = 0

        self.current_frame = None
        self.root.protocol("WM_DELETE_WINDOW", self.quit_game)
        if play_intro:
            self.current_frame = IntroFrame(root, self)
        else:
            self.show_menu("title")
        self.poll_pads()

    # ---- quem controla cada jogador: controles primeiro, depois os esquemas de teclado
    def num_pads(self):
        return min(self.pads.count, MAX_PLAYERS)

    def pad_player(self, idx):
        """Controle nº idx (0, 1...) -> pid, ou None se já há jogadores demais."""
        return idx + 1 if idx is not None and idx < MAX_PLAYERS else None

    def keys_player(self, layout):
        """Esquema de teclado nº layout (0 = WASD...) -> pid, ou None se sobrou."""
        pid = self.num_pads() + layout + 1
        return pid if pid <= MAX_PLAYERS else None

    def input_label(self, pid):
        n = self.num_pads()
        if pid <= n:
            off = "" if self.pads.is_connected(pid - 1) else " (OFF)"
            return f"{SHORT_NAMES[self.pads.family(pid - 1)]} {pid}{off}"
        return KEY_LAYOUTS[pid - 1 - n][0]

    def gamepad_connected(self):
        """True se há ao menos um controle conectado (os textos de ajuda mostram os botões dele)."""
        return self.pads.connected

    def note_keyboard(self, event=None):
        if INPUT.note("keys") and hasattr(
            self.current_frame, "on_input_source_changed"
        ):
            self.current_frame.on_input_source_changed()

    def sync_pad_leds(self):
        """Luz do controle (PS4/PS5) = cor da moto do jogador que ele controla.
        No menu de pilotos usa a cor em edição, então a luz muda junto com a escolha."""
        pick = getattr(self.current_frame, "color", None)
        for i in range(self.num_pads()):
            try:
                color = pick(i + 1) if callable(pick) else self.colors.get(i + 1, CYAN)
            except Exception:
                color = self.colors.get(i + 1, CYAN)
            self.pads.set_led(i, color)

    def release_pad(self, index):
        """Libera a vaga de um controle que caiu: qualquer controle novo pode assumir esse jogador."""
        self.pads.release(index)
        INPUT.sync(self.pads)
        self.show_pad_notice()
        if hasattr(self.current_frame, "on_inputs_changed"):
            self.current_frame.on_inputs_changed()

    def show_pad_notice(self, idx=None, connected=False):
        """Faixa no topo: lista os controles desconectados (fica até reconectar ou clicar)
        ou avisa por 3 s que um controle conectou."""
        if self.pad_notice is not None:
            self.pad_notice.destroy()
            self.pad_notice = None
        if self.pad_notice_after:
            self.root.after_cancel(self.pad_notice_after)
            self.pad_notice_after = None
        self.pad_notice_connected = False
        missing = [
            i
            for i in range(self.num_pads())
            if not self.pads.is_connected(i) and not self.pads.is_released(i)
        ]
        rows = [(i, False) for i in missing]
        if not rows and connected and idx is not None and idx < MAX_PLAYERS:
            rows = [(idx, True)]
        if not rows:
            return
        alert = not rows[0][1]
        box = tk.Frame(
            self.root,
            bg=T.PANEL,
            highlightthickness=2,
            highlightbackground=T.RED if alert else CYAN,
        )
        box.place(relx=0.5, rely=0.04, anchor="n")
        for i, ok in rows:
            line = tk.Frame(box, bg=T.PANEL)
            line.pack(anchor="w", padx=18, pady=(10, 0))
            led = self.pads.led(i)
            if led:  # mostra a cor que está acesa na barra de luz do controle
                tk.Frame(line, bg=led, width=26, height=26).pack(side="left", padx=(0, 12))
            status = "CONECTADO" if ok else "DESCONECTADO"
            tk.Label(
                line,
                text=f"CONTROLE {i + 1} {status}  •  {self.pads.name(i) or 'controle'}"
                f" ({FAMILY_NAMES[self.pads.family(i)]})",
                bg=T.PANEL,
                fg=CYAN if ok else T.RED,
                font=(T.FONT, 15, "bold"),
            ).pack(side="left")
        detail = (
            f"Ele controla o jogador {rows[0][0] + 1}."
            if not alert
            else "Reconecte para continuar, ou use LIBERAR CONTROLE no menu de pausa."
        )
        tk.Label(box, text=detail, bg=T.PANEL, fg=T.MUTED, font=(T.FONT, 11)).pack(
            anchor="w", padx=18, pady=(6, 10)
        )
        for widget in (box, *box.winfo_children()):
            widget.bind("<Button-1>", lambda e: self.hide_pad_notice())
        box.lift()
        self.pad_notice, self.pad_notice_frame = box, self.current_frame
        self.pad_notice_connected = not alert
        if not alert:
            self.pad_notice_after = self.root.after(3000, self.hide_pad_notice)

    def hide_pad_notice(self):
        self.pad_notice_after = None
        if self.pad_notice is not None:
            self.pad_notice.destroy()
            self.pad_notice = None
        self.pad_notice_connected = False

    def poll_pads(self):
        if self.pad_notice is not None and self.pad_notice_frame is not self.current_frame:
            if self.pad_notice_connected and not self._can_show_pad_connection_notice():
                self.hide_pad_notice()
            else:
                self.pad_notice.lift()  # a tela nova nasce por cima: traz o aviso de volta
                self.pad_notice_frame = self.current_frame
        self.sync_pad_leds()  # barato: só fala com o controle quando a cor muda
        for idx, kind, value in self.pads.poll():
            frame = self.current_frame
            if kind == "changed":
                INPUT.sync(self.pads)
                if not value and idx < MAX_PLAYERS and hasattr(frame, "open_pause"):
                    frame.open_pause()  # partida em andamento para quando um controle cai
                if value:
                    if self._can_show_pad_connection_notice():
                        self.show_pad_notice(idx, connected=True)
                    elif isinstance(frame, IntroFrame):
                        self.pending_pad_notice = idx
                else:
                    self.show_pad_notice(idx, connected=False)
                if hasattr(frame, "on_inputs_changed"):
                    frame.on_inputs_changed()
                continue
            if INPUT.note("pad") and hasattr(frame, "on_input_source_changed"):
                frame.on_input_source_changed()
            if hasattr(frame, "on_pad"):
                frame.on_pad(self.pad_player(idx), kind, value)
        if self.pads.ok:
            self.root.after(8, self.poll_pads)

    def _can_show_pad_connection_notice(self):
        return isinstance(self.current_frame, MainMenu) and self.menu_from_intro

    def update_music(self):
        self.sound.update_music()
        self.music_after_id = self.root.after(25, self.update_music)

    def quit_game(self):
        self.clear_screen()
        if self.pad_notice_after:
            self.root.after_cancel(self.pad_notice_after)
        self.pads.shutdown()
        if self.music_after_id is not None:
            self.root.after_cancel(self.music_after_id)
            self.music_after_id = None
        self.sound.shutdown()
        self.root.destroy()

    def clear_screen(self):
        if self.current_frame:
            if hasattr(self.current_frame, "destroy_arena"):
                self.current_frame.destroy_arena()
            self.current_frame.destroy()

    def show_menu(self, page="mode", preserve_intro=False, arrival=False):
        """page="title": tela inicial (ao abrir o jogo); "mode": direto na escolha do modo (volta de uma partida)."""
        handoff = None
        if arrival and isinstance(self.current_frame, IntroFrame):
            photo = self.current_frame.intro.portal.photo
            if photo is not None:
                handoff = tk.Label(self.root,image=photo,bg=BG_COLOR,borderwidth=0)
                handoff.photo = photo
                handoff.place(x=0,y=0,relwidth=1,relheight=1)
                handoff.lift()
        self.sound.stop_crowd()
        if not preserve_intro:
            self.sound.play("menu_select")
        self.sound.enter_menu_music(preserve_intro=preserve_intro)
        self.clear_screen()
        self.menu_from_intro = preserve_intro
        self.menu_arrival = arrival
        self.current_frame = MainMenu(self.root, self, page)
        if preserve_intro and self.pending_pad_notice is not None:
            idx, self.pending_pad_notice = self.pending_pad_notice, None
            if self.pads.is_connected(idx):
                self.show_pad_notice(idx, connected=True)
        if handoff is not None:
            handoff.lift()
            self.root.update_idletasks()
            handoff.destroy()

    def show_intro(self):
        self.sound.stop_crowd()
        self.clear_screen()
        self.current_frame = IntroFrame(self.root, self)

    def start_game(self, mode, color_config, model_config, map_idx):
        self.sound.stop_crowd()
        self.sound.play("menu_select")
        self.sound.set_music_track("game", restart=True)
        self.game_mode = mode
        self.map_idx = map_idx
        self.colors.update(color_config)
        self.models.update(model_config)
        self.scores = {1: 0, 2: 0, 3: 0, 4: 0}
        self.clear_screen()
        self.current_frame = GameArena(self.root, self)

    def start_chase(self, from_duel=False):
        """Cena independente; não zera o placar do duelo já vencido."""
        from chase_mode import ChaseFrame

        self.sound.stop_crowd()
        self.clear_screen()
        self.sound.set_music_track("chase", restart=True)
        self.current_frame = ChaseFrame(self.root, self, from_duel=from_duel)

    def on_escape(self):
        """Na partida, ESC abre/fecha o menu de pausa; nos menus, sai do jogo."""
        frame = self.current_frame
        if hasattr(frame, "on_escape"):
            frame.on_escape()
        else:
            self.quit_game()

    def reset_match(self):
        """Tecla R: reinicia a partida, mas só entre rodadas (para um toque sem querer não apagar o placar)."""
        frame = self.current_frame
        if isinstance(frame, IntroFrame):
            frame.skip()
            return
        if isinstance(frame, GameArena) and not (
            frame.running or frame.counting or frame.paused
        ):
            self.sound.play("menu_select")
            frame.restart_match()


class MainMenu(MenuScreens, tk.Frame):
    """Menu em etapas para escolher modo e configurar mapa, cores, motos e alvo."""

    # (chave, título, descrição, ícone: [(pid, offset x, offset y, direção)])
    MODES = [
        ("1v1", "1 VS 1", "Duelo clássico", [(1, -8, 0, (1, 0)), (2, 8, 0, (-1, 0))]),
        (
            "ffa4",
            "TODOS x TODOS",
            "4 jogadores, cada um por si",
            [
                (1, -8, 0, (1, 0)),
                (2, 8, 0, (-1, 0)),
                (3, 0, -8, (0, 1)),
                (4, 0, 8, (0, -1)),
            ],
        ),
        (
            "team2v2",
            "EQUIPES 2v2",
            "P1+P3 vs P2+P4",
            [
                (1, -8, -7, (1, 0)),
                (3, -8, 7, (1, 0)),
                (2, 8, -7, (-1, 0)),
                (4, 8, 7, (-1, 0)),
            ],
        ),
        (
            "training",
            "TREINO",
            "1 jogador + até 3 IAs",
            [(1, -8, 0, (1, 0)), (2, 8, 0, (-1, 0))],
        ),
        (
            "rinzler",
            "RINZLER",
            "Sobreviva ao perseguidor",
            [(1, -8, 0, (1, 0)), (2, 8, 0, (-1, 0))],
        ),
        (
            "chase",
            "PERSEGUIÇÃO 3D",
            "Rinzler nas Terras Ermas",
            [(1, -20, 0, (0, -1)), (2, 20, -12, (0, -1))],
        ),
    ]

    def __init__(self, parent, controller, page="title"):
        super().__init__(parent, bg=BG_COLOR)
        self.controller = controller
        self.pack(fill=tk.BOTH, expand=True)
        self.W, self.H = controller.screen_width, controller.screen_height

        self.cv = tk.Canvas(
            self, width=self.W, height=self.H, bg=BG_COLOR, highlightthickness=0
        )
        self.cv.pack(fill=tk.BOTH, expand=True)
        self.fx = Effects(self.cv)

        self.mode = controller.game_mode
        self.setup_step = "arena"
        # Índice na paleta; CUSTOM = cor escolhida no painel RGB (guardada em self.custom)
        self.color_idx = {
            p: next(
                (i for i, (_, c) in enumerate(pal) if c == controller.colors[p]), CUSTOM
            )
            for p, pal in PALETTES.items()
        }
        self.custom = {p: controller.colors[p] for p in PALETTES}
        self.custom.update(
            {("team", 1): controller.colors[1], ("team", 2): controller.colors[2]}
        )
        self.team_color_idx = {
            1: self.color_idx[1],
            2: self.color_idx[2],
        }
        self.rgb = None  # painel RGB aberto: {"owner", "key", "rgb", "ch"}
        self.map_changed_at = 0.0
        self.model_idx = dict(controller.models)
        self.map_idx = controller.map_idx
        self.match_target = controller.match_target
        self.ai_count = controller.ai_count
        self.ai_level = controller.ai_level
        self.modifiers = dict(controller.modifiers)
        self.trail_fade_sec = controller.trail_fade_sec
        self.training_player_count = controller.training_player_count
        self.training_human_count = controller.training_human_count
        self.training_teams = controller.training_teams
        self.advanced_config = controller.advanced_config
        if self.mode != "team2v2":
            self.ensure_unique_player_colors()
        self.from_intro = getattr(controller, "menu_from_intro", False)
        self.arrival_active = getattr(controller, "menu_arrival", False) and page == "title"
        self.page = page  # "title" (tela inicial), "mode" (modo de jogo) ou "setup" (configuração)
        self.t = 0.0
        self.last = time.perf_counter()
        self.after_id = None
        self.sel_card = None
        self.preview_glows = []
        self.focus = (
            ("mode", self.mode) if page == "mode" else "play"
        )  # item selecionado pelo controle/teclado
        self.focus_boxes = {}  # item -> retângulo (x1, y1, x2, y2) para o destaque
        self.focus_rect = None
        self.swatch_pos = {}  # (pid, cor) -> centro da amostra (para o efeito de anel)
        self.backdrop = None  # fundo desfocado (Pillow); None = só escurece a cena viva
        self.blur_k = self.blur_goal = (
            0.0  # 0 = cena viva e nítida (tela inicial), 1 = desfocada e escura
        )
        self.bg_hidden = False  # a cena viva está escondida atrás da imagem desfocada
        self.bg_colors = None  # cores originais do fundo (escurecimento sem Pillow)
        self.dim_applied = 0.0

        self.draw_background()
        self.prepare_backdrop()
        self.draw_title()
        self.draw_ui()
        if self.arrival_active:
            self.update_arrival(0)
        if page != "title":  # voltando de uma partida: já abre com o fundo desfocado
            self.blur_k = self.blur_goal = 1.0
            self.apply_blur(1.0)
        self._key_binding_id = self.winfo_toplevel().bind("<KeyPress>", self.on_key)
        self.loop()

    def destroy(self):
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None
        self.backdrop = None
        if getattr(self, "_key_binding_id", None):
            self.winfo_toplevel().unbind("<KeyPress>", self._key_binding_id)
            self._key_binding_id = None
        super().destroy()

    def color(self, pid):
        if self.mode == "team2v2" or (self.mode == "training" and self.training_teams):
            team = 1 if pid in (1, 3) else 2
            idx, key = self.team_color_idx[team], ("team", team)
        else:
            idx, key = self.color_idx[pid], pid
        return self.custom[key] if idx == CUSTOM else COLOR_PALETTE[idx][1]

    def humans(self):
        return [p for p in self.active_player_ids() if not self.is_ai(p)]

    def is_ai(self, pid):
        return (self.mode == "training" and pid > self.training_human_count) or (
            self.mode == "rinzler" and pid == 2
        )

    def active_player_ids(self):
        if self.mode == "training":
            count = 4 if self.training_teams else self.training_player_count
            return list(range(1, count + 1))
        if self.mode == "rinzler":
            return [1, 2]
        if self.mode in ("ffa4", "team2v2"):
            return [1, 2, 3, 4]
        return [1, 2]

    def color_is_taken(self, pid, color_index):
        # A IA sorteia a cor no início da partida, então não bloqueia ninguém; RGB nunca bloqueia.
        return color_index != CUSTOM and any(
            other != pid and self.color_idx[other] == color_index
            for other in self.humans()
        )

    def team_color_is_taken(self, team, color_index):
        return color_index != CUSTOM and any(
            other != team and self.team_color_idx[other] == color_index
            for other in (1, 2)
        )

    def ensure_unique_player_colors(self):
        used_colors = set()
        for pid in self.humans():
            if self.color_idx[pid] in used_colors and self.color_idx[pid] != CUSTOM:
                self.color_idx[pid] = next(
                    index
                    for index in range(len(COLOR_PALETTE))
                    if index not in used_colors
                )
            used_colors.add(self.color_idx[pid])

    # ---- fundo desfocado (menus de seleção)
    def prepare_backdrop(self):
        """Pré-renderiza o fundo em vários graus de desfoque. Sem Pillow (ou se falhar), os menus
        de seleção só escurecem a cena viva."""
        if not backdrop.AVAILABLE:
            print(
                "Pillow não encontrado: o fundo dos menus será só escurecido (python -m pip install pillow)."
            )
            return
        try:
            base = backdrop.snapshot(
                lambda pc: self.draw_background(pc, live=False),
                self.W,
                self.H,
                BG_COLOR,
                scale=min(0.5, 960 / self.W),
            )  # base de ~960 px: o desfoque esconde o resto
            self.backdrop = backdrop.Backdrop(
                self.cv,
                self.W,
                self.H,
                base,
                MENU_BLUR_RADIUS * base.width / 1920,
                MENU_DIM,
            )
        except Exception as e:  # o menu funciona mesmo sem o desfoque
            print("Fundo desfocado indisponível:", e)
            self.backdrop = None

    def set_blur(self, on):
        self.blur_goal = 1.0 if on else 0.0

    def update_blur(self, dt):
        """Aproxima o desfoque da meta (transição suave); chamado a cada quadro do loop."""
        if self.blur_k == self.blur_goal:
            return
        step = dt / max(0.05, MENU_BLUR_SEC)
        if self.blur_goal > self.blur_k:
            self.blur_k = min(self.blur_goal, self.blur_k + step)
        else:
            self.blur_k = max(self.blur_goal, self.blur_k - step)
        self.apply_blur(self.blur_k)

    def apply_blur(self, k):
        if self.backdrop is None:
            self.dim_bg(k)
            return
        covered = k > 0
        if covered:
            self.backdrop.show(k)
        else:
            self.backdrop.hide()
        if (
            covered != self.bg_hidden
        ):  # a cena viva (itens "bg") some atrás da imagem e volta ao sair
            self.cv.itemconfig("bg", state="hidden" if covered else "normal")
            self.bg_hidden = covered
            if not covered and hasattr(self, "menu_race"):
                self.menu_race.restore_visibility()

    def dim_bg(self, k):
        """Sem Pillow: escurece a cena viva recolorindo os itens do fundo (em poucos degraus)."""
        k = round(k * 6) / 6
        if k == self.dim_applied:
            return
        cv = self.cv
        if self.bg_colors is None:
            self.bg_colors = {}
            for it in cv.find_withtag("bg"):
                if cv.type(it) == "image":
                    continue
                opts = ("fill",) if cv.type(it) == "line" else ("fill", "outline")
                self.bg_colors[it] = [(o, cv.itemcget(it, o)) for o in opts]
        for it, opts in self.bg_colors.items():
            for opt, col in opts:
                if len(col) == 7 and col[0] == "#":
                    cv.itemconfig(it, **{opt: blend(col, "#000000", MENU_DIM * k)})
        self.dim_applied = k

    # ---- desenho

    def clickable(self, tag, rect, cmd):
        """Hover (borda mais grossa + cursor de mão) e clique para itens com a mesma tag."""
        w = float(self.cv.itemcget(rect, "width"))

        def invoke(event):
            self.controller.sound.play("menu_select")
            cmd()

        self.cv.tag_bind(tag, "<Button-1>", invoke)
        self.cv.tag_bind(
            tag,
            "<Enter>",
            lambda e: (
                self.cv.itemconfig(rect, width=w + 2),
                self.cv.config(cursor="hand2"),
            ),
        )
        self.cv.tag_bind(
            tag,
            "<Leave>",
            lambda e: (self.cv.itemconfig(rect, width=w), self.cv.config(cursor="")),
        )

    def on_input_source_changed(self):
        """Trocou entre teclado e controle: só as dicas mudam."""
        if self.rgb:
            self.draw_ui()
        else:
            self.draw_hints()

    def toggle_config_level(self):
        self.advanced_config = not self.advanced_config
        self.controller.advanced_config = self.advanced_config
        if not self.advanced_config:
            self.modifiers["shrinking_arena"] = False
            self.modifiers["lightning_round"] = False
            self.modifiers["collect_items"] = False
            self.modifiers["lives"] = False
            self.training_teams = False
            self.training_player_count = min(self.training_player_count, 4)
            self.training_human_count = 1
        self.controller.modifiers = dict(self.modifiers)
        self.controller.training_teams = self.training_teams
        self.controller.sound.play("menu_move")
        self.draw_ui()

    def setup_primary_focus(self):
        if self.page != "setup":
            return "map"
        if self.setup_step == "arena":
            return "map"
        if self.setup_step == "rules":
            return (
                ("training_players" if self.advanced_config else "ai_count")
                if self.mode == "training"
                else "start" if self.mode == "rinzler" else "target"
            )
        return (
            ("team_color", 1)
            if self.mode == "team2v2"
            or (self.mode == "training" and self.training_teams)
            else ("color", 1)
        )

    def set_setup_step(self, step, keep_focus=False):
        if step not in ("arena", "rules", "riders"):
            return
        self.setup_step = step
        self.focus = {
            "arena": "map",
            "rules": "target" if self.mode != "rinzler" else "start",
            "riders": (
                ("team_color", 1)
                if self.mode == "team2v2"
                or (self.mode == "training" and self.training_teams)
                else ("color", 1)
            ),
        }[step]
        if step == "rules" and self.mode == "training":
            self.focus = "training_players" if self.advanced_config else "ai_count"
        if (
            keep_focus
        ):  # navegando pelas abas: o destaque fica na aba, não pula para dentro da etapa
            self.focus = ("setup_step", step)
        self.controller.sound.play("menu_move")
        self.draw_ui()

    def move_setup_step(self, step, keep_focus=False):
        order = ("arena", "rules", "riders")
        current = order.index(self.setup_step)
        new = order[max(0, min(len(order) - 1, current + step))]
        if new != self.setup_step:
            self.set_setup_step(new, keep_focus)

    # ---- painel RGB
    def open_rgb(self, owner):
        pid = owner[1] if owner[0] == "color" else (1 if owner[1] == 1 else 2)
        col = self.color(pid)
        self.rgb = {
            "owner": owner,
            "key": pid if owner[0] == "color" else ("team", owner[1]),
            "rgb": [int(col[i : i + 2], 16) for i in (1, 3, 5)],
            "ch": 0,
        }
        self.controller.sound.play("menu_select")
        self.draw_ui()

    def rgb_hex(self):
        rgb = self.rgb["rgb"]
        m = max(rgb)
        if (
            m < 80
        ):  # cor escura demais some no fundo preto: sobe o brilho mantendo o tom
            rgb = [80] * 3 if m == 0 else [int(v * 80 / m) for v in rgb]
        return "#%02X%02X%02X" % tuple(rgb)

    def rgb_change(self, ch=None, step=0):
        if ch is not None:
            self.rgb["ch"] = ch % 3
        c = self.rgb["ch"]
        self.rgb["rgb"][c] = max(0, min(255, self.rgb["rgb"][c] + step))
        self.controller.sound.play("menu_move")
        self.draw_ui()

    def rgb_set(self, ch, value):
        self.rgb["ch"] = ch
        self.rgb["rgb"][ch] = max(0, min(255, int(value)))
        self.draw_ui()

    def rgb_close(self, confirm):
        if confirm:
            kind, who = self.rgb["owner"]
            self.custom[self.rgb["key"]] = self.rgb_hex()
            if kind == "color":
                self.color_idx[who] = CUSTOM
            else:
                self.team_color_idx[who] = CUSTOM
                for pid in ((1, 3) if who == 1 else (2, 4)):
                    self.color_idx[pid] = CUSTOM
        self.rgb = None
        self.controller.sound.play("menu_select" if confirm else "menu_move")
        self.draw_ui()

    def rgb_input(self, kind, value):
        """Painel aberto: ↑↓ escolhe o canal, ←→ / LB RB mudam o valor, A confirma, B cancela."""
        if kind == "dir":
            if value[1]:
                self.rgb_change(ch=self.rgb["ch"] + value[1])
            else:
                self.rgb_change(step=17 * value[0])
        elif value in ("lb", "rb"):
            self.rgb_change(step=17 if value == "rb" else -17)
        elif value in ("a", "start"):
            self.rgb_close(True)
        elif value in ("b", "back"):
            self.rgb_close(False)

    def draw_rgb_panel(self):
        cv, cx, cy = self.cv, self.W / 2, self.H / 2
        w, h = 520, 330
        col = self.rgb_hex()
        x1, y1 = cx - w / 2, cy - h / 2
        cv.create_rectangle(
            x1 - 6,
            y1 - 6,
            x1 + w + 6,
            y1 + h + 6,
            outline=blend(BG_COLOR, col, 0.3),
            width=6,
            tags="ui",
        )
        cv.create_rectangle(
            x1, y1, x1 + w, y1 + h, fill="#04070d", outline=col, width=2, tags="ui"
        )
        cv.create_text(
            cx,
            y1 + 24,
            text="COR PERSONALIZADA",
            font=(T.FONT, 15, "bold"),
            fill=col,
            tags="ui",
        )
        py = y1 + 72
        cv.create_line(
            x1 + 40, py, cx + 20, py, fill=col, width=7, capstyle=tk.ROUND, tags="ui"
        )
        cv.create_line(
            x1 + 40,
            py,
            cx + 20,
            py,
            fill="#FFFFFF",
            width=2,
            capstyle=tk.ROUND,
            tags="ui",
        )
        owner = self.rgb["owner"]
        model = self.model_idx[
            owner[1] if owner[0] == "color" else (1 if owner[1] == 1 else 2)
        ]
        draw_bike(cv, cx + 70, py, (1, 0), col, model, 2.6, tags="ui")
        bar_x, bar_w = x1 + 90, w - 190
        for ch, (label, c) in enumerate(
            (("R", "#FF3344"), ("G", "#33FF66"), ("B", "#3399FF"))
        ):
            by = y1 + 130 + ch * 44
            sel = ch == self.rgb["ch"]
            v = self.rgb["rgb"][ch]
            tag = f"rgbbar_{ch}"
            cv.create_text(
                bar_x - 34,
                by,
                text=("▶ " if sel else "  ") + label,
                font=(T.FONT, 14, "bold"),
                fill="#FFFFFF" if sel else c,
                tags="ui",
            )
            cv.create_rectangle(
                bar_x,
                by - 11,
                bar_x + bar_w,
                by + 11,
                fill="#0b1426",
                outline="#FFFFFF" if sel else blend(BG_COLOR, c, 0.5),
                width=2,
                tags=("ui", tag),
            )
            cv.create_rectangle(
                bar_x + 2,
                by - 9,
                bar_x + 2 + (bar_w - 4) * v / 255,
                by + 9,
                fill=c,
                outline="",
                tags=("ui", tag),
            )
            cv.create_text(
                bar_x + bar_w + 34,
                by,
                text=str(v),
                font=(T.FONT, 13, "bold"),
                fill=c,
                tags="ui",
            )
            cv.tag_bind(
                tag,
                "<Button-1>",
                lambda e, ch=ch: self.rgb_set(ch, (e.x - bar_x) / bar_w * 255),
            )
        for tag, bx, text, button, fill, fg, ok in (
            (
                "rgb_cancel",
                cx - 90,
                "CANCELAR (",
                "B",
                BG_COLOR,
                "#6A8AAA",
                False,
            ),
            ("rgb_ok", cx + 90, "OK (", "A", col, BG_COLOR, True),
        ):
            r = cv.create_rectangle(
                bx - 80,
                y1 + h - 52,
                bx + 80,
                y1 + h - 18,
                fill=fill,
                outline=fg if fill == BG_COLOR else fill,
                width=2,
                tags=("ui", tag),
            )
            draw_control_prompt(
                cv,
                bx,
                y1 + h - 35,
                rgb_button_label(ok),
                (T.FONT, 11, "bold"),
                fg,
                ("ui", tag),
            )
            self.clickable(tag, r, lambda ok=ok: self.rgb_close(ok))
        draw_control_prompt(
            cv,
            cx,
            y1 + h + 22,
            rgb_hints(),
            (T.FONT, 10),
            "#6A8AAA",
            "ui",
        )

    # ---- interação
    def set_mode(self, key):
        self.mode = key
        if self.page == "mode":
            self.focus = ("mode", key)
        if key == "team2v2":
            if self.team_color_idx[1] == self.team_color_idx[2]:
                self.team_color_idx[2] = next(
                    index
                    for index in range(len(COLOR_PALETTE))
                    if index != self.team_color_idx[1]
                )
            for team, members in ((1, (1, 3)), (2, (2, 4))):
                for pid in members:
                    self.color_idx[pid] = self.team_color_idx[team]
        else:
            self.ensure_unique_player_colors()
        self.controller.sound.play("menu_move")
        self.draw_ui()
        x, y = self.card_pos[key]
        self.fx.ring(x, y, CYAN, max_r=120, dur=0.45)

    def set_color(self, pid, j, sx, sy):
        if self.color_is_taken(pid, j):
            return
        self.color_idx[pid] = j
        self.controller.sound.play("menu_move")
        self.draw_ui()
        self.fx.ring(sx, sy, self.color(pid), max_r=34, dur=0.35)

    def set_team_color(self, team, index, sx, sy):
        if self.team_color_is_taken(team, index):
            return
        self.team_color_idx[team] = index
        for pid in ((1, 3) if team == 1 else (2, 4)):
            self.color_idx[pid] = index
        self.controller.sound.play("menu_move")
        self.draw_ui()
        self.fx.ring(sx, sy, self.color(1 if team == 1 else 2), max_r=34, dur=0.35)

    def set_model(self, pid, step):
        self.model_idx[pid] = (self.model_idx[pid] + step) % len(BIKES)
        self.controller.sound.play("menu_move")
        self.draw_ui()

    def set_map(self, step):
        self.map_idx = (self.map_idx + step) % (len(MAPS) + 1)
        self.map_changed_at = self.t  # a maquete 3D cresce de novo do chão
        self.controller.sound.play("menu_move")
        self.draw_ui()

    def set_modifier(self, key):
        if key == "fading_trail" and (
            self.modifiers["collect_items"] or self.modifiers["lives"]
        ):
            return
        self.modifiers[key] = not self.modifiers[key]
        if key in ("collect_items", "lives") and self.modifiers[key]:
            self.modifiers["fading_trail"] = True
        self.controller.sound.play("menu_move")
        self.draw_ui()

    def adjust_trail_duration(self, step):
        if not self.modifiers["fading_trail"]:
            return
        index = TRAIL_FADE_OPTIONS.index(self.trail_fade_sec)
        self.trail_fade_sec = TRAIL_FADE_OPTIONS[
            (index + step) % len(TRAIL_FADE_OPTIONS)
        ]
        self.controller.sound.play("menu_move")
        self.draw_ui()

    def set_target(self, step):
        self.match_target = max(3, min(10, self.match_target + step))
        self.controller.sound.play("menu_move")
        self.draw_ui()

    def set_ai_count(self, step):
        self.ai_count = max(1, min(3, self.ai_count + step))
        self.training_player_count = self.ai_count + 1
        self.ensure_unique_player_colors()
        self.controller.ai_count = self.ai_count
        self.controller.sound.play("menu_move")
        self.draw_ui()

    def set_ai_level(self, step):
        keys = [k for k, _ in AI_LEVELS]
        self.ai_level = keys[
            max(0, min(len(keys) - 1, keys.index(self.ai_level) + step))
        ]
        self.controller.sound.play("menu_move")
        self.draw_ui()

    def set_training_players(self, step):
        if self.training_teams:
            return
        self.training_player_count = max(2, min(4, self.training_player_count + step))
        self.training_human_count = min(
            self.training_human_count, self.training_player_count
        )
        self.ai_count = self.training_player_count - 1
        self.controller.sound.play("menu_move")
        self.draw_ui()

    def set_training_humans(self, step):
        maximum = 4 if self.training_teams else self.training_player_count
        self.training_human_count = max(
            1, min(maximum, self.training_human_count + step)
        )
        self.ensure_unique_player_colors()
        self.controller.sound.play("menu_move")
        self.draw_ui()

    def toggle_training_teams(self):
        self.training_teams = not self.training_teams
        if self.training_teams:
            self.training_player_count = 4
            self.ai_count = 3
        self.controller.sound.play("menu_move")
        self.draw_ui()

    def show_title(self):
        self.page = "title"
        self.rgb = None
        self.focus = "play"
        self.set_blur(False)
        self.draw_ui()

    def show_modes(self):
        if self.page == "title":
            self.controller.sound.play("menu_select")
        self.page = "mode"
        self.rgb = None
        self.focus = ("mode", self.mode)
        self.set_blur(True)
        self.draw_ui()

    def show_setup(self):
        if self.mode == "chase":
            self.controller.start_chase()
            return
        self.page = "setup"
        self.setup_step = "arena"
        self.map_changed_at = self.t
        self.focus = "map"
        self.set_blur(True)
        self.draw_ui()

    # ---- navegação por controle/teclado

    def adjust(self, step):
        """LB / RB (ou ← / →) muda o valor do item selecionado."""
        f = self.focus
        if isinstance(f, tuple) and f[0] == "mode":
            keys = [m[0] for m in self.MODES]
            self.set_mode(keys[(keys.index(self.mode) + step) % len(keys)])
        elif isinstance(f, tuple) and f[0] == "setup_step":
            self.move_setup_step(step, keep_focus=True)
        elif f in ("back", "start") and self.page == "setup":
            self.move_setup_step(
                step
            )  # LB / RB nos botões de baixo: etapa anterior / próxima
        elif f == "config_level":
            self.toggle_config_level()
        elif f == "map":
            self.set_map(step)
        elif f == "mod_trail":
            self.set_modifier("fading_trail")
        elif f == "trail_duration":
            self.adjust_trail_duration(step)
        elif isinstance(f, str) and f.startswith("mod_"):
            self.set_modifier(f[4:])
        elif f == "training_teams":
            self.toggle_training_teams()
        elif f == "training_players":
            self.set_training_players(step)
        elif f == "training_humans":
            self.set_training_humans(step)
        elif f == "target":
            self.set_target(step)
        elif f == "ai_count":
            self.set_ai_count(step)
        elif f == "ai_level":
            self.set_ai_level(step)
        elif isinstance(f, tuple) and f[0] == "color":
            pid = f[1]
            for offset in range(1, len(COLOR_PALETTE) + 2):
                j = (self.color_idx[pid] + step * offset) % (CUSTOM + 1)
                if not self.color_is_taken(pid, j):
                    self.set_color(pid, j, *self.swatch_pos[(pid, j)])
                    break
        elif isinstance(f, tuple) and f[0] == "team_color":
            team = f[1]
            for offset in range(1, len(COLOR_PALETTE) + 2):
                j = (self.team_color_idx[team] + step * offset) % (CUSTOM + 1)
                if not self.team_color_is_taken(team, j):
                    self.set_team_color(team, j, *self.swatch_pos[("team", team, j)])
                    break
        elif isinstance(f, tuple) and f[0] == "model":
            self.set_model(f[1], step)

    def on_inputs_changed(self):
        """Controle conectado/desconectado: atualiza quem usa o quê nos painéis."""
        self.draw_ui()

    def on_start(self):
        colors = {pid: self.color(pid) for pid in PALETTES}
        if self.mode == "training" and not self.training_teams:
            # IAs recebem cores livres, sem alterar a paleta escolhida pelos humanos.
            used = {colors[p] for p in self.humans()}
            free = [c for _, c in COLOR_PALETTE if c not in used]
            random.shuffle(free)
            for pid in self.active_player_ids():
                if not self.is_ai(pid):
                    continue
                colors[pid] = free.pop()
        elif self.mode == "rinzler":
            colors[2] = T.ORANGE
            self.model_idx[2] = 1
        self.controller.match_target = self.match_target
        self.controller.ai_count = self.ai_count
        self.controller.ai_level = self.ai_level
        self.controller.trail_fade_sec = self.trail_fade_sec
        self.controller.training_player_count = self.training_player_count
        self.controller.training_human_count = self.training_human_count
        self.controller.training_teams = self.training_teams
        self.controller.advanced_config = self.advanced_config
        if not self.advanced_config:
            for key in ("shrinking_arena", "lightning_round", "collect_items", "lives"):
                self.modifiers[key] = False
        if self.mode == "rinzler":
            for key in ("shrinking_arena", "lightning_round", "collect_items", "lives"):
                self.modifiers[key] = False
        if self.modifiers["collect_items"] or self.modifiers["lives"]:
            self.modifiers["fading_trail"] = True
        self.controller.modifiers = dict(self.modifiers)
        self.controller.start_game(
            self.mode, colors, dict(self.model_idx), self.map_idx
        )

    # ---- animação
    def step_demo(self, dt):
        self.menu_race.advance(dt)


class GameArena(tk.Frame):
    """Arena de jogo com spawns seguros longe dos obstáculos, botão de menu e efeitos visuais."""

    def __init__(self, parent, controller):
        super().__init__(parent, bg=BG_COLOR)
        self.controller = controller
        self.root = parent
        self.sound = controller.sound
        self.pack(fill=tk.BOTH, expand=True)

        self.width = controller.screen_width
        self.height = controller.screen_height

        # Canvas otimizado
        self.canvas = tk.Canvas(
            self,
            width=self.width,
            height=self.height,
            bg=BG_COLOR,
            highlightthickness=0,
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Inicializar sistema de efeitos visuais
        self.fx = Effects(self.canvas)

        # Desenhar grade de fundo
        self.draw_grid()

        self.chrome = ArenaChrome(self.canvas, self.width, self.height, self.toggle_pause)
        self.ui_scale = self.chrome.scale
        self.bike_scale = 1.4
        self.arena_rect = self.chrome.rect
        self.border_id = self.chrome.edges[-1]
        self.pause_button = self.chrome.pause_button
        self.hit_stop = 0.0

        # Estados do jogo
        self.running = False
        self.paused = False
        self.game_over = False
        self.counting = False
        self.final_duel = False
        self.finalists = ()
        self.match_complete = False
        self.elimination_order = []
        # Limites jogáveis em células (iguais aos de is_free) e faixas de portal do mapa atual
        left, top, right, bottom = self.chrome.initial_rect
        self.cell_bounds = (
            math.ceil((left + WALL_GAP) / CELL),
            math.floor((right - WALL_GAP) / CELL),
            math.ceil((top + WALL_GAP) / CELL),
            math.floor((bottom - WALL_GAP) / CELL),
        )
        self.base_cell_bounds = self.cell_bounds
        self.portals_h, self.portals_v = [], []
        self.riders = {}
        self.occupied_cells = set()
        self.tick_ms = TICK_START_MS
        self.after_id = None  # loop de animação (não pode ser cancelado entre rodadas)
        self.restart_cooldown_id = None
        self.escape_after_id = None
        self.next_round_text_id = None
        self.round_ready_at = 0.0
        self.last_frame_time = time.time()
        self.anim_t = 0.0
        self.acc = 0.0  # tempo (ms) acumulado desde o último passo da simulação
        self.pause_keys = []  # itens do menu de pausa (vazio = menu fechado)
        self.pause_focus = 0
        self.pause_confirm = None  # item que está pedindo confirmação
        self.pause_boxes, self.pause_texts = [], []
        self.collectible_cell = None
        self.collectible_id = None
        self.lives_remaining = {}
        self.tick_min_ms = TICK_MIN_MS

        # Vincular teclas globais
        self.winfo_toplevel().bind("<KeyPress>", self.on_key_press)

        self.init_round()
        self.start_animation_loop()

    def destroy_arena(self):
        for attr in ("after_id", "restart_cooldown_id", "escape_after_id"):
            if getattr(self, attr):
                self.root.after_cancel(getattr(self, attr))
                setattr(self, attr, None)

    def draw_grid(self):
        """Grade fina a cada 4 células e linhas principais (que pulsam) a cada 16."""
        step = CELL * 4
        for i, x in enumerate(range(0, self.width, step)):
            self.canvas.create_line(
                x,
                0,
                x,
                self.height,
                fill=GRID_COLOR,
                tags="grid_major" if i % 4 == 0 else "grid",
            )
        for i, y in enumerate(range(0, self.height, step)):
            self.canvas.create_line(
                0,
                y,
                self.width,
                y,
                fill=GRID_COLOR,
                tags="grid_major" if i % 4 == 0 else "grid",
            )

    def update_hud(self):
        mode = self.controller.game_mode
        training_team = mode == "training" and self.controller.training_teams
        if self.final_duel:
            active_p = list(self.finalists)
        elif mode in ("1v1", "training", "rinzler"):
            active_p = (
                [1, 2]
                if mode in ("1v1", "rinzler")
                else list(
                    range(
                        1,
                        (
                            5
                            if training_team
                            else self.controller.training_player_count + 1
                        ),
                    )
                )
            )
        else:
            active_p = [1, 2, 3, 4]
        info = f"ALVO {self.controller.match_target} / {self.map_name}"
        if mode == "training":
            info += f" / IA {dict(AI_LEVELS)[self.controller.ai_level]}"
        if self.controller.modifiers["shrinking_arena"]:
            info += " / ARENA ENCOLHENDO"
        if self.controller.modifiers["fading_trail"]:
            info += f" / RASTRO {self.controller.trail_fade_sec:g}s"
        if self.controller.modifiers["lightning_round"]:
            info += " / RELÂMPAGO"
        self.chrome.hud(active_p, self.controller, self.riders, self.lives_remaining, info)

    def is_team_mode(self):
        return self.controller.game_mode == "team2v2" or (
            self.controller.game_mode == "training" and self.controller.training_teams
        )

    @staticmethod
    def team_for_player(pid):
        return 1 if pid in (1, 3) else 2

    def on_inputs_changed(self):
        self.update_hud()
        if self.paused and self.pause_keys:
            owner = self.pause_owner
            if owner and not self.controller.pads.is_connected(owner - 1):
                self.pause_owner = None  # o dono caiu: qualquer controle assume a pausa
            # refaz os itens LIBERAR CONTROLE n conforme quem está desconectado agora
            base = [k for k in self.pause_keys if not isinstance(k, tuple)]
            self.pause_keys = base[:1] + [("release", i) for i in self.lost_pads()] + base[1:]
            self.pause_focus, self.pause_confirm = 0, None
            self.draw_pause()
        elif self.game_over and self.victory_buttons:
            self.draw_victory_hint()

    def on_input_source_changed(self):
        """Trocou entre teclado e controle: só as dicas na tela mudam."""
        if self.paused and self.pause_keys:
            self.draw_pause_hint()
        elif self.game_over and self.victory_buttons:
            self.draw_victory_hint()

    def wrap_cell(self, cell):
        """Travessia estilo Pac-Man: uma célula fora da arena, na altura (ou largura) de uma abertura
        na parede, reaparece do lado oposto. Qualquer outra célula volta igual."""
        if self.controller.modifiers["shrinking_arena"]:
            return cell
        x, y = cell
        x0, x1, y0, y1 = self.cell_bounds
        if (x < x0 or x > x1) and y0 <= y <= y1:
            if any(lo <= y <= hi for lo, hi in self.portals_h):
                return (x0 + (x - x1 - 1) if x > x1 else x1 - (x0 - x - 1), y)
        elif (y < y0 or y > y1) and x0 <= x <= x1:
            if any(lo <= x <= hi for lo, hi in self.portals_v):
                return (x, y0 + (y - y1 - 1) if y > y1 else y1 - (y0 - y - 1))
        return cell

    def is_free(self, cell):
        """Método exigido pelo módulo ai.py para verificar células livres."""
        cell = self.wrap_cell(
            cell
        )  # atravessar uma abertura vale como estar do outro lado
        x0, x1, y0, y1 = self.current_cell_bounds()
        if not (x0 <= cell[0] <= x1 and y0 <= cell[1] <= y1):
            return False
        return cell not in self.occupied_cells

    def current_cell_bounds(self):
        x0, x1, y0, y1 = self.base_cell_bounds
        if not self.controller.modifiers["shrinking_arena"]:
            return self.base_cell_bounds
        steps = max(
            0,
            int((self.sim_time - SHRINK_START_SEC) // SHRINK_STEP_SEC),
        )
        max_steps = min((x1 - x0) // 3, (y1 - y0) // 3)
        inset = min(steps, max_steps)
        return x0 + inset, x1 - inset, y0 + inset, y1 - inset

    def update_shrinking_arena(self, dt=0.0, snap=False):
        x0, x1, y0, y1 = self.current_cell_bounds()
        target = (x0 * CELL - WALL_GAP, y0 * CELL - WALL_GAP,
                  x1 * CELL + WALL_GAP, y1 * CELL + WALL_GAP)
        bx0, bx1, by0, by1 = self.base_cell_bounds
        maximum = min((bx1 - bx0) // 3, (by1 - by0) // 3)
        warning = (self.controller.modifiers["shrinking_arena"]
                   and self.sim_time >= SHRINK_START_SEC - 2 and x0 - bx0 < maximum)
        if warning and self.running and self.sim_time >= self.next_shrink_beep:
            self.sound.play("beep")
            self.next_shrink_beep = self.sim_time + 1
        self.chrome.update_rect(target, dt, self.anim_t, warning, snap)
        self.arena_rect = self.chrome.rect

    def spawn_collectible(self):
        if self.collectible_id is not None:
            self.canvas.delete(self.collectible_id)
        x0, x1, y0, y1 = self.current_cell_bounds()
        for _ in range(3000):
            cell = (random.randint(x0 + 2, x1 - 2), random.randint(y0 + 2, y1 - 2))
            if self.is_free(cell):
                self.create_collectible(cell)
                return
        free_cells = [
            (x, y)
            for x in range(x0 + 2, x1 - 1)
            for y in range(y0 + 2, y1 - 1)
            if self.is_free((x, y))
        ]
        if free_cells:
            self.create_collectible(random.choice(free_cells))
        else:
            self.collectible_cell = None
            self.collectible_id = None

    def create_collectible(self, cell):
        self.collectible_cell = cell
        px, py = cell[0] * CELL, cell[1] * CELL
        self.collectible_id = self.canvas.create_polygon(
            px,
            py - 9,
            px + 7,
            py,
            px,
            py + 9,
            px - 7,
            py,
            fill="#FFFF55",
            outline="#FFFFFF",
            width=2,
            tags=("game_obj", "collectible"),
        )

    def finish_collection_match(self, champion):
        self.game_over = True
        self.running = False
        self.match_complete = True
        self.update_hud()
        self.sound.play("match_win")
        self.sound.set_music_track("victory")
        self.show_match_victory(champion)
        cooldown_seconds = ROUND_RESTART_COOLDOWN_MS / 1000
        self.victory_buttons[0].configure(
            state="disabled", text=f"AGUARDE {cooldown_seconds:g}s"
        )
        self.round_ready_at = time.monotonic() + cooldown_seconds
        self.update_victory_selection()
        self.restart_cooldown_id = self.root.after(
            ROUND_RESTART_COOLDOWN_MS, self.finish_round_cooldown
        )

    def init_round(self):
        if self.game_over and time.monotonic() < self.round_ready_at:
            return
        if self.restart_cooldown_id:
            self.root.after_cancel(self.restart_cooldown_id)
            self.restart_cooldown_id = None
        self.sound.stop_crowd()
        self.next_round_text_id = None
        self.acc = 0.0
        self.hit_stop = 0.0
        self.next_shrink_beep = SHRINK_START_SEC - 2
        self.sim_time = 0.0  # tempo de jogo da rodada (só avança com a simulação; a pausa não conta)
        self.canvas.delete("pause_obj")
        self.pause_keys, self.pause_confirm = [], None

        # Remove botões da tela de campeão e zera o placar se a partida já terminou
        for btn in getattr(self, "victory_buttons", []):
            btn.destroy()
        self.victory_buttons = []
        self.victory_selection = 0
        if self.match_complete:
            self.controller.scores = {1: 0, 2: 0, 3: 0, 4: 0}
            self.final_duel = False
            self.finalists = ()
            self.match_complete = False
        elif (
            max(self.controller.scores.values()) >= self.controller.match_target
            and not self.final_duel
        ):
            self.controller.scores = {1: 0, 2: 0, 3: 0, 4: 0}

        self.canvas.delete("game_obj")
        self.fx.reset()
        self.collectible_cell = None
        self.collectible_id = None
        self.game_over = False
        self.paused = False
        self.running = False
        self.counting = False
        lightning = self.controller.modifiers["lightning_round"]
        self.tick_min_ms = max(
            1, int(TICK_MIN_MS * LIGHTNING_TICK_FACTOR) if lightning else TICK_MIN_MS
        )
        self.tick_ms = (
            max(1, int(TICK_START_MS * LIGHTNING_TICK_FACTOR))
            if lightning
            else TICK_START_MS
        )
        self.update_shrinking_arena(snap=True)
        self.occupied_cells = set()
        if not self.final_duel:
            self.elimination_order = []

        mode = self.controller.game_mode
        if self.final_duel:
            active_ids = list(self.finalists)
        elif mode == "training":
            count = (
                4
                if self.controller.training_teams
                else self.controller.training_player_count
            )
            active_ids = list(range(1, count + 1))
        elif mode in ("1v1", "rinzler"):
            active_ids = [1, 2]
        else:
            active_ids = [1, 2, 3, 4]
        self.lives_remaining = {
            pid: (2 if self.controller.modifiers["lives"] else 1) for pid in active_ids
        }
        if mode == "training":  # IA troca de moto a cada rodada
            for pid in active_ids:
                if pid <= self.controller.training_human_count:
                    continue
                self.controller.models[pid] = random.randrange(len(BIKES))

        # Criar obstáculos do mapa na arena primeiro
        self.create_obstacles()
        self.update_hud()

        # Spawns seguros nas laterais da arena (longe do centro onde ficam os obstáculos)
        bx0, bx1, by0, by1 = self.base_cell_bounds
        min_cx, max_cx = bx0 + 3, bx1 - 3
        min_cy, max_cy = by0 + 3, by1 - 3
        cx_grid = (self.width // 2) // CELL
        cy_grid = (self.height // 2) // CELL

        configs = {
            1: {
                "cell": (min_cx + 10, cy_grid),
                "dir": (1, 0),
            },  # Esquerda, movendo-se para a direita
            2: {
                "cell": (max_cx - 10, cy_grid),
                "dir": (-1, 0),
            },  # Direita, movendo-se para a esquerda
            3: {
                "cell": (cx_grid, min_cy + 10),
                "dir": (0, 1),
            },  # Topo, movendo-se para baixo
            4: {
                "cell": (cx_grid, max_cy - 10),
                "dir": (0, -1),
            },  # Base, movendo-se para cima
        }

        self.riders = {}
        for pid in active_ids:
            cfg = configs[pid]
            cell = cfg["cell"]
            d = cfg["dir"]
            color = self.controller.colors[pid]
            model = self.controller.models[pid]

            px, py = cell[0] * CELL, cell[1] * CELL
            color = CYCLES[model].tint(color)
            halo, glow, core = self.new_trail_items(color, px, py)

            rider = Rider(pid, cell, d, color, model)
            rider.line_halo = halo
            rider.line_glow = glow
            rider.line_core = core
            if (
                self.controller.modifiers["fading_trail"]
                or self.controller.modifiers["collect_items"]
                or self.controller.modifiers["lives"]
            ):
                rider.trail_life = self.controller.trail_fade_sec
            rider.lives = self.lives_remaining[pid]
            rider.bike = draw_bike(
                self.canvas, px, py, d, color, model, scale=self.bike_scale, tags="game_obj"
            )
            self.create_head_spark(rider, px, py)
            control = (
                "RINZLER"
                if mode == "rinzler" and pid == 2
                else (
                    "IA"
                    if mode == "training" and pid > self.controller.training_human_count
                    else self.controller.input_label(pid)
                )
            )
            hint_text = f"P{pid} • {control}"
            shadow = self.canvas.create_text(
                px,
                py - 20,
                text=hint_text,
                font=("Courier", 9, "bold"),
                fill=BG_COLOR,
                tags="game_obj",
                state="hidden",
            )
            label = self.canvas.create_text(
                px,
                py - 21,
                text=hint_text,
                font=("Courier", 9, "bold"),
                fill=color,
                tags="game_obj",
                state="hidden",
            )
            rider.hint_ids = (shadow, label)
            if mode == "training" and pid > self.controller.training_human_count:
                rider.is_ai = True
            elif mode == "rinzler" and pid == 2:
                rider.is_ai = True
                rider.is_rinzler = True
                rider.next_boost_at = RINZLER_BOOST_COOLDOWN_SEC

            self.riders[pid] = rider
            self.occupied_cells.add(cell)

        self.update_hud()
        if self.controller.modifiers["collect_items"]:
            self.spawn_collectible()

        start_segments = (
            start_prompt(
                "INICIA",
                before=f"X1 DECISIVO: P{self.finalists[0]} VS P{self.finalists[1]}  •  ",
            )
            if self.final_duel
            else start_prompt("PARA INICIAR A RODADA")
        )
        draw_round_start_prompt(
            self.canvas,
            self.width // 2,
            self.height // 2,
            start_segments,
            "round_start_prompt",
        )
        map_lbl = self.canvas.create_text(
            self.width // 2,
            self.height // 2 - 45,
            text=f"MAPA: {self.map_name}",
            font=("Courier", 16, "bold"),
            fill=BG_COLOR,
            tags="game_obj",
        )
        self.fx.text_in(map_lbl, "#FFFFFF", 0.6)
        self.fx.fade([(map_lbl, "#FFFFFF")], 0.6, delay=2.0)

    def create_obstacles(self):
        idx = self.controller.map_idx
        if idx == RANDOM_MAP:
            idx = random.randrange(len(MAPS))  # sorteia a cada rodada
        self.map_name, rects = MAPS[idx][:2]
        x0, x1, y0, y1 = self.base_cell_bounds
        left, top = x0 * CELL - WALL_GAP, y0 * CELL - WALL_GAP
        w, h = (x1 - x0) * CELL + WALL_GAP * 2, (y1 - y0) * CELL + WALL_GAP * 2
        self.setup_portals(map_options(MAPS[idx]), left, top, w, h)
        for fx1, fy1, fx2, fy2 in rects:
            x1, y1, x2, y2 = (
                left + fx1 * w,
                top + fy1 * h,
                left + fx2 * w,
                top + fy2 * h,
            )
            self.canvas.create_rectangle(
                x1 - 3,
                y1 - 3,
                x2 + 3,
                y2 + 3,
                outline=blend(BG_COLOR, CYAN, 0.18),
                width=6,
                tags="game_obj",
            )
            self.canvas.create_rectangle(
                x1,
                y1,
                x2,
                y2,
                outline=blend(BG_COLOR, CYAN, 0.7),
                fill="#04121a",
                width=2,
                tags="game_obj",
            )
            # Bloqueia toda célula cujo ponto fique a menos de OBSTACLE_GAP px do bloco
            # (antes a última coluna/linha deixava a moto encostar no obstáculo).
            g = OBSTACLE_GAP
            for cx_coord in range(
                math.ceil((x1 - g) / CELL), math.floor((x2 + g) / CELL) + 1
            ):
                for cy_coord in range(
                    math.ceil((y1 - g) / CELL), math.floor((y2 + g) / CELL) + 1
                ):
                    self.occupied_cells.add((cx_coord, cy_coord))
        self.canvas.tag_raise(
            "hud"
        )  # as aberturas de cima não podem cobrir o texto do HUD

    def setup_portals(self, opts, left, top, w, h):
        """Aberturas na parede (travessia estilo Pac-Man): guarda as faixas em células e desenha a abertura."""
        x0, x1, y0, y1 = self.cell_bounds
        right, bottom = left + w, top + h
        self.portals_h, self.portals_v = [], []
        for f1, f2 in opts.get("wrap_h", ()):
            ya, yb = top + f1 * h, top + f2 * h
            self.portals_h.append(
                (max(y0, math.ceil(ya / CELL)), min(y1, math.floor(yb / CELL)))
            )
            self.draw_portal(left, ya, left, yb)
            self.draw_portal(right, ya, right, yb)
        for f1, f2 in opts.get("wrap_v", ()):
            xa, xb = left + f1 * w, left + f2 * w
            self.portals_v.append(
                (max(x0, math.ceil(xa / CELL)), min(x1, math.floor(xb / CELL)))
            )
            self.draw_portal(xa, top, xb, top)
            self.draw_portal(xa, bottom, xb, bottom)

    def draw_portal(self, ax, ay, bx, by):
        """Abre um trecho da borda: apaga a parede ali e marca as pontas e o vão com luz."""
        cv, col = self.canvas, PORTAL_COLOR
        vertical = ax == bx
        if vertical:
            cv.create_rectangle(
                ax - 10, ay, ax + 10, by, fill=BG_COLOR, outline="", tags="game_obj"
            )
        else:
            cv.create_rectangle(
                ax, ay - 10, bx, ay + 10, fill=BG_COLOR, outline="", tags="game_obj"
            )
        cv.create_line(
            ax,
            ay,
            bx,
            by,
            fill=blend(BG_COLOR, col, 0.3),
            width=10,
            tags=("game_obj", "portal_glow"),
        )
        cv.create_line(ax, ay, bx, by, fill=col, width=2, dash=(6, 6), tags="game_obj")
        for px, py in ((ax, ay), (bx, by)):
            if vertical:
                cv.create_line(
                    px - 12, py, px + 12, py, fill="#FFFFFF", width=3, tags="game_obj"
                )
            else:
                cv.create_line(
                    px, py - 12, px, py + 12, fill="#FFFFFF", width=3, tags="game_obj"
                )

    # ---- menu de pausa
    PAUSE_KEYS = ("resume", "music", "sfx", "restart", "menu", "quit")

    def toggle_pause(self):
        self.close_pause() if self.paused else self.open_pause()

    def on_escape(self):
        if (
            self.victory_buttons
        ):  # tela de campeão: ESC volta ao menu, como o B do controle
            self.controller.show_menu()
        else:
            self.toggle_pause()

    def restart_match(self):
        self.controller.scores = {1: 0, 2: 0, 3: 0, 4: 0}
        self.final_duel = False
        self.finalists = ()
        self.match_complete = False
        self.round_ready_at = 0.0
        self.init_round()
        self.update_hud()

    def pause_label(self, key):
        if isinstance(key, tuple):
            return f"LIBERAR CONTROLE {key[1] + 1}"
        if key == "music":
            return "MÚSICA"
        if key == "sfx":
            return "EFEITOS"
        return {
            "resume": "CONTINUAR",
            "restart": "REINICIAR PARTIDA",
            "menu": "MENU PRINCIPAL",
            "quit": "SAIR DO JOGO",
        }[key]

    def lost_pads(self):
        """Vagas de controle desconectadas (e ainda não liberadas) que valem jogadores."""
        pads = self.controller.pads
        return [
            i
            for i in range(self.controller.num_pads())
            if not pads.is_connected(i) and not pads.is_released(i)
        ]

    def open_pause(self, owner=None):
        """owner = jogador cujo controle abriu a pausa: só esse controle navega (o teclado sempre pode).
        None = qualquer controle (pausa aberta pelo teclado ou por um controle que caiu)."""
        if self.paused or self.victory_buttons or self.escape_after_id:
            return
        self.paused = True
        self.pause_owner = owner
        self.chrome.pause_visible(False)
        keys = [k for k in self.PAUSE_KEYS if k != "music" or self.sound.music_supported]
        self.pause_keys = keys[:1] + [("release", i) for i in self.lost_pads()] + keys[1:]
        self.pause_focus, self.pause_confirm = 0, None
        self.fx.shake_amt = 0.0  # o efeitos congelam: não deixa a tela "tremida" parada
        self.canvas.scan_dragto(0, 0, gain=1)
        self.sound.play("menu_select")
        self.sound.set_music_track("pause")
        self.draw_pause()

    def close_pause(self):
        if not self.paused:
            return
        self.paused = False
        self.pause_keys, self.pause_confirm = [], None
        self.canvas.delete("pause_obj")
        self.chrome.pause_visible(True)
        self.sound.play("menu_select")
        self.sound.set_music_track("game")

    def draw_pause(self):
        cv, cx, cy = self.canvas, self.width // 2, self.height // 2
        gap = 9 if self.height >= 620 else 6
        item_h = min(
            54,
            max(
                30,
                (self.height - 32 - 166 - gap * (len(self.pause_keys) - 1))
                // len(self.pause_keys),
            ),
        )
        pw = min(620, self.width - 56)
        ph = 166 + len(self.pause_keys) * item_h + (len(self.pause_keys) - 1) * gap
        top = cy - ph // 2
        cv.delete("pause_obj")
        cv.create_rectangle(
            0,
            0,
            self.width,
            self.height,
            fill="#000000",
            stipple="gray75",
            outline="",
            tags="pause_obj",
        )
        cv.create_rectangle(
            cx - pw / 2 - 2,
            top,
            cx + pw / 2 + 2,
            top + ph,
            fill="#05050d",
            outline="#164052",
            width=2,
            tags="pause_obj",
        )
        cv.create_text(
            cx - pw / 2 + 34,
            top + 35,
            anchor="w",
            text=f"PAUSA • JOGADOR {self.pause_owner}" if self.pause_owner else "PAUSA",
            font=("Courier", 24, "bold"),
            fill=self.controller.colors.get(self.pause_owner, CYAN),
            tags="pause_obj",
        )
        cv.create_text(
            cx - pw / 2 + 36,
            top + 68,
            anchor="w",
            text="Ajuste o jogo ou escolha para onde seguir.",
            font=("Courier", 10),
            fill="#6A8AAA",
            tags="pause_obj",
        )
        cv.create_line(
            cx - pw / 2 + 28,
            top + 88,
            cx + pw / 2 - 28,
            top + 88,
            fill="#163044",
            tags="pause_obj",
        )
        self.pause_boxes = []
        self.pause_texts = []
        y = top + 102
        for i in range(len(self.pause_keys)):
            tag = f"pause_item{i}"
            self.pause_boxes.append(
                cv.create_rectangle(
                    cx - pw / 2 + 30,
                    y,
                    cx + pw / 2 - 30,
                    y + item_h,
                    fill="#08111c",
                    outline="#142637",
                    width=1,
                    tags=("pause_obj", tag),
                )
            )
            self.pause_texts.append(())
            cv.tag_bind(tag, "<Button-1>", lambda e, i=i: self.pause_click(i))
            cv.tag_bind(tag, "<Enter>", lambda e, i=i: self.pause_set_focus(i))
            y += item_h + gap
        self.pause_hint_pos = (cx, top + ph - 24)
        self.pause_refresh()

    def pause_refresh(self):
        """Atualiza cores e textos dos itens (sem recriar, para o mouse não perder o hover)."""
        for i, key in enumerate(self.pause_keys):
            sel = i == self.pause_focus
            confirming = self.pause_confirm == key
            tag = f"pause_item{i}"
            self.canvas.itemconfig(
                self.pause_boxes[i],
                fill="#102333" if sel else "#08111c",
                outline="#FF5267" if confirming else CYAN if sel else "#142637",
                width=2 if sel else 1,
            )
            for item in self.pause_texts[i]:
                self.canvas.delete(item)
            x1, y1, x2, y2 = self.canvas.coords(self.pause_boxes[i])
            cy = (y1 + y2) / 2
            if confirming and isinstance(key, tuple):
                label = f"LIBERAR CONTROLE {key[1] + 1}?"
                detail = f"{INPUT.confirm_name()} confirma   •   {INPUT.back_name()} cancela"
            elif confirming:
                label = {
                    "restart": "CONFIRMAR REINÍCIO?",
                    "menu": "VOLTAR AO MENU?",
                    "quit": "SAIR DO JOGO?",
                }[key]
                detail = (
                    f"{INPUT.confirm_name()} confirma   •   {INPUT.back_name()} cancela"
                )
            else:
                label = self.pause_label(key)
                if key in ("music", "sfx"):
                    value = (
                        self.sound.music_level
                        if key == "music"
                        else self.sound.sfx_level
                    )
                    detail = f"{round(value * 100):d}%"
                elif isinstance(key, tuple):
                    detail = "Qualquer controle novo assume o jogador"
                else:
                    detail = {
                        "resume": "Retomar a rodada",
                        "restart": "Começar esta partida de novo",
                        "menu": "Sair da partida e voltar aos modos",
                        "quit": "Fechar o jogo",
                    }[key]
            accent = "#FF5267" if confirming else CYAN if sel else "#9BB0C8"
            self.canvas.create_rectangle(
                x1 + 1,
                y1 + 8,
                x1 + 4,
                y2 - 8,
                fill=accent if sel or confirming else "#08111c",
                outline="",
                tags=("pause_obj", tag),
            )
            label_id = self.canvas.create_text(
                x1 + 22,
                cy,
                anchor="w",
                text=label,
                font=("Courier", 12 if y2 - y1 >= 48 else 10, "bold"),
                fill="#FFFFFF" if sel or confirming else "#8899AA",
                tags=("pause_obj", tag),
            )
            detail_id = self.canvas.create_text(
                x2 - 18,
                cy,
                anchor="e",
                text=detail,
                font=("Courier", 9 if y2 - y1 >= 42 else 8),
                fill=accent,
                tags=("pause_obj", tag),
            )
            self.pause_texts[i] = (label_id, detail_id)
        self.draw_pause_hint()

    def draw_pause_hint(self):
        """Dicas do rodapé da pausa: mudam com o item em foco e com o dispositivo em uso."""
        self.canvas.delete("pause_hint")
        pos = getattr(self, "pause_hint_pos", None)
        if not pos or not self.pause_keys:
            return
        key = self.pause_keys[self.pause_focus]
        kind = "volume" if key in ("music", "sfx") else "button"
        draw_control_prompt(
            self.canvas,
            pos[0],
            pos[1],
            pause_hints(kind, self.pause_confirm == key),
            ("Courier", 9),
            "#4A6A88",
            ("pause_obj", "pause_hint"),
        )

    def pause_set_focus(self, i):
        if i != self.pause_focus and 0 <= i < len(self.pause_keys):
            self.sound.play("menu_move")
            self.pause_focus, self.pause_confirm = i, None
            self.pause_refresh()

    def pause_move(self, step):
        self.pause_focus = (self.pause_focus + step) % len(self.pause_keys)
        self.pause_confirm = None
        self.sound.play("menu_move")
        self.pause_refresh()

    def pause_click(self, i):
        self.pause_set_focus(i)
        self.pause_activate()

    def pause_adjust(self, step):
        """← → / LB RB: muda o volume do item selecionado."""
        key, s = self.pause_keys[self.pause_focus], self.sound
        delta = (
            step * 0.1 if s.backend == "pygame" else step
        )  # sem pygame não há volume: só liga/desliga
        if key == "music":
            s.set_music_level(round(s.music_level + delta, 2))
        elif key == "sfx":
            s.set_sfx_level(round(s.sfx_level + delta, 2))
            s.play("menu_move")
        else:
            return
        self.pause_refresh()

    def pause_activate(self):
        key, s = self.pause_keys[self.pause_focus], self.sound
        s.play("menu_select")
        if key == "resume":
            self.close_pause()
        elif key == "music":  # ENTER / A num volume = mudo / volume cheio
            s.set_music_level(0.0 if s.music_level > 0 else 1.0)
            self.pause_refresh()
        elif key == "sfx":
            s.set_sfx_level(0.0 if s.sfx_level > 0 else 1.0)
            s.play("menu_move")
            self.pause_refresh()
        elif self.pause_confirm != key:  # ações que perdem a partida pedem confirmação
            self.pause_confirm = key
            s.play("menu_move")
            self.pause_refresh()
        elif isinstance(key, tuple):  # LIBERAR CONTROLE n (já confirmado)
            self.controller.release_pad(key[1])  # avisa on_inputs_changed, que refaz a lista
        elif key == "restart":
            self.close_pause()
            self.restart_match()
        elif key == "menu":
            self.controller.show_menu()
        else:
            self.controller.quit_game()

    def pause_key(self, keysym):
        if keysym in ("Up", "Down"):
            self.pause_move(1 if keysym == "Down" else -1)
        elif keysym in ("Left", "Right"):
            self.pause_adjust(1 if keysym == "Right" else -1)
        elif keysym == "Return":
            self.pause_activate()
        elif keysym == "BackSpace":
            self.pause_back()
        elif keysym.lower() == "p":
            self.close_pause()

    def pause_back(self):
        """B / BACKSPACE: cancela o pedido de confirmação; sem nada para cancelar, continua a partida."""
        if self.pause_confirm:
            self.pause_confirm = None
            self.sound.play("menu_move")
            self.pause_refresh()
        else:
            self.close_pause()

    def pause_pad(self, kind, value):
        if kind == "dir":
            dx, dy = value
            if dy:
                self.pause_move(dy)
            elif dx:
                self.pause_adjust(dx)
        elif kind == "button":
            if value == "a":
                self.pause_activate()
            elif value in ("lb", "rb"):
                self.pause_adjust(-1 if value == "lb" else 1)
            elif value == "b":
                self.pause_back()
            elif value in ("start", "back"):
                self.close_pause()

    def start_countdown(self):
        """Contagem 3-2-1-GO antes da largada."""
        self.counting = True
        self.canvas.delete("round_start_prompt")
        self.canvas.delete("next_round_prompt")
        cx, cy = self.width // 2, self.height // 2

        def show(n):
            self.sound.play("beep")
            self.fx.popup(n, cx, cy, "#00FFFF", life=0.7)

        for i, n in enumerate(("3", "2", "1")):
            self.fx.after(i * 0.7, lambda n=n: show(n))
        self.fx.after(2.1, self.go)

    def go(self):
        self.counting = False
        self.running = True
        self.sound.play("go")
        for rider in self.riders.values():
            rider.hint_until = self.sim_time + 3.0
            self.fx.ring(rider.cell[0] * CELL, rider.cell[1] * CELL, rider.color, max_r=45, dur=.8)
            for item in rider.hint_ids:
                self.canvas.itemconfig(item, state="normal")
        self.fx.popup("GO!", self.width // 2, self.height // 2, "#FFFF00", life=0.8)
        self.acc = 0.0

    def press_start(self):
        """ESPAÇO (ou botão A): inicia a rodada ou vai para a próxima."""
        if not self.running and not self.game_over and not self.counting:
            self.start_countdown()
        elif self.game_over:
            self.init_round()

    def queue_turn(self, pid, nd):
        if not self.running or self.paused or pid not in self.riders:
            return
        r = self.riders[pid]
        if not r.is_ai and r.alive and len(r.queue) < 2:
            r.queue.append(nd)

    def should_end_round(self, survivors):
        if self.is_team_mode() and not self.final_duel:
            team_one_alive = any(pid in survivors for pid in (1, 3))
            team_two_alive = any(pid in survivors for pid in (2, 4))
            return not team_one_alive or not team_two_alive
        return len(survivors) <= 1

    def on_key_press(self, event):
        if self.game_over and self.victory_buttons:
            if event.keysym in ("Left", "Right", "Up", "Down"):
                self.select_victory_option(
                    1 if event.keysym in ("Right", "Down") else -1
                )
            elif event.keysym in ("Return", "space"):
                self.activate_victory_option()
            elif event.keysym in ("Escape", "BackSpace"):
                self.controller.show_menu()
            return
        if (
            self.paused
        ):  # menu de pausa aberto: as teclas navegam o menu, não viram a moto
            if self.pause_keys:
                self.pause_key(event.keysym)
            return
        if event.keysym == "space":
            self.press_start()
            return

        if event.keysym.lower() == "p":
            self.toggle_pause()
            return

        # Mapeamento de teclas unificado usando KEY_LOOKUP do config.py
        key_lower = event.keysym.lower()
        if key_lower in KEY_LOOKUP:
            layout, nd = KEY_LOOKUP[key_lower]
            pid = self.controller.keys_player(layout)
            if pid:
                self.queue_turn(pid, nd)

    def on_pad(self, pid, kind, value):
        """Controle: direcional/analógico vira a moto, A inicia, START ou BACK abrem o menu de pausa."""
        if self.paused:
            if getattr(self, "pause_owner", None) in (None, pid):
                self.pause_pad(kind, value)
            return
        if self.game_over and self.victory_buttons:
            if kind == "dir":
                step = value[0] if value[0] else value[1]
                if step:
                    self.select_victory_option(step)
            elif kind == "button":
                if value in ("lb", "rb"):
                    self.select_victory_option(-1 if value == "lb" else 1)
                elif value in ("a", "start"):
                    self.activate_victory_option()
                elif value in ("b", "back"):
                    self.controller.show_menu()
            return

        if kind == "dir":
            self.queue_turn(pid, value)
        elif value == "a":
            self.press_start()
        elif value == "start":
            if self.running or self.counting:
                self.open_pause(pid)
            else:
                self.press_start()
        elif value == "back":
            self.open_pause(pid)

    def game_tick(self):
        """Um passo da simulação (chamado por advance_sim, em passo fixo de tick_ms)."""
        if not self.running or self.paused:
            return
        self.sim_time += self.tick_ms / 1000
        self.update_shrinking_arena()

        # Toda IA pode perseguir adversários; Rinzler mantém prioridade no P1.
        for r in self.riders.values():
            if r.is_ai and r.alive:
                level = "extreme" if r.is_rinzler else self.controller.ai_level
                ai.decide(self, r, level=level, target_pid=1 if r.is_rinzler else None)

        rinzler_boost_step = False
        rinzler = next(
            (r for r in self.riders.values() if r.is_rinzler and r.alive), None
        )
        if rinzler:
            if self.sim_time >= rinzler.next_boost_at:
                rinzler.boost_until = self.sim_time + RINZLER_BOOST_DURATION_SEC
                rinzler.next_boost_at = self.sim_time + RINZLER_BOOST_COOLDOWN_SEC
                rinzler.next_boost_step = self.sim_time + RINZLER_BOOST_INTERVAL_SEC
                self.fx.popup(
                    "BOOST",
                    rinzler.cell[0] * CELL,
                    rinzler.cell[1] * CELL - 24,
                    "#FF2020",
                    life=0.55,
                    size=24,
                )
            if (
                self.sim_time < rinzler.boost_until
                and self.sim_time >= rinzler.next_boost_step
            ):
                rinzler_boost_step = True
                rinzler.next_boost_step += RINZLER_BOOST_INTERVAL_SEC

        # Processar filas de comandos de direção
        for r in self.riders.values():
            if not r.alive:
                continue
            r.turned = False
            while r.queue:
                nd = r.queue.pop(0)
                if nd != r.dir and (nd[0] != -r.dir[0] or nd[1] != -r.dir[1]):
                    r.dir = nd
                    r.turned = True
                    self.sound.play("turn")
                    break

        self.expire_trails()  # modificador: apaga a cauda dos rastros efêmeros

        # Atualizar posições dos corredores
        moves = {
            pid: self.wrap_cell((r.cell[0] + r.dir[0], r.cell[1] + r.dir[1]))
            for pid, r in self.riders.items()
            if r.alive
        }
        targets = list(moves.values())
        # Duas motos entrando na mesma célula no mesmo tick: ambas batem (antes P1 sempre vencia)
        crashed_now = [
            pid
            for pid, c in moves.items()
            if not self.is_free(c) or targets.count(c) > 1
        ]
        for pid, nxt_cell in moves.items():
            if pid not in crashed_now:
                self.advance_rider(self.riders[pid], nxt_cell)

        collection_winner = None
        if (
            self.collectible_cell is not None
            and self.controller.modifiers["collect_items"]
        ):
            for pid, nxt_cell in moves.items():
                if pid in crashed_now or nxt_cell != self.collectible_cell:
                    continue
                score_id = self.team_for_player(pid) if self.is_team_mode() else pid
                self.controller.scores[score_id] += 1
                if self.controller.scores[score_id] >= self.controller.match_target:
                    collection_winner = score_id
                else:
                    self.spawn_collectible()
                    self.update_hud()
                break

        if (
            rinzler_boost_step
            and rinzler is not None
            and rinzler.alive
            and rinzler.pid not in crashed_now
        ):
            extra_cell = self.wrap_cell(
                (rinzler.cell[0] + rinzler.dir[0], rinzler.cell[1] + rinzler.dir[1])
            )
            if self.is_free(extra_cell):
                self.advance_rider(rinzler, extra_cell)
            else:
                crashed_now.append(rinzler.pid)

        # Tratar colisões e atualizar gráficos
        for pid, r in self.riders.items():
            if pid in crashed_now and r.alive:
                r.alive = False
                for item in r.hint_ids:
                    self.canvas.itemconfig(item, state="hidden")
                px, py = r.cell[0] * CELL, r.cell[1] * CELL
                # Rastro do derrotado se desfaz e libera o espaço na arena
                cells = set(r.cells)
                for it in (r.line_halo, r.line_glow, r.line_core):
                    self.canvas.coords(
                        it, *r.trail
                    )  # o rastro termina exatamente onde a moto bateu
                if r.is_rinzler:
                    self.elimination_order.append(pid)
                    self.begin_rinzler_escape(r, cells)
                    continue
                self.lives_remaining[pid] = max(0, self.lives_remaining.get(pid, 1) - 1)
                r.lives = self.lives_remaining[pid]
                will_respawn = (
                    self.controller.modifiers["lives"] and self.lives_remaining[pid] > 0
                )
                if not will_respawn:
                    self.elimination_order.append(pid)
                for it in r.bike:
                    self.canvas.delete(it)
                x0, x1, y0, y1 = self.current_cell_bounds()
                target_cell = moves[pid]
                wall = (
                    "left" if target_cell[0] < x0
                    else "right" if target_cell[0] > x1
                    else "top" if target_cell[1] < y0
                    else "bottom" if target_cell[1] > y1
                    else None
                )
                self.fx.derez(
                    px, py, r.color, r.dir, scale=self.bike_scale, wall=wall
                )  # de-resolução: pixels seguem a direção da moto
                self.hit_stop = .07
                self.fx.shake(10.0)
                self.sound.play("bike_impact")
                self.sound.play("bike_derez")
                self.sound.play("pilot_scream")
                colors = [tint for tint, _ in T.glow_layers(r.color, 3)]
                pieces = [(list(piece["trail"]), list(zip(piece["items"], colors))) for piece in r.old]
                pieces.append((list(r.trail), list(zip((r.line_halo, r.line_glow, r.line_core), colors))))
                self.fx.dissolve_trail(
                    pieces, DISSOLVE_SEC, DISSOLVE_DELAY,
                    on_done=lambda c=cells: self.occupied_cells.difference_update(c),
                )
                if will_respawn:
                    self.respawn_rider(r)

        if crashed_now:
            self.sound.play("crowd_gasp")
            self.update_hud()

        if collection_winner is not None:
            self.finish_collection_match(collection_winner)
            return

        # Verificar fim de rodada
        survivors = [pid for pid, r in self.riders.items() if r.alive]
        if self.should_end_round(survivors):
            self.sound.stop_crowd()
            self.game_over = True
            self.running = False
            self.render_riders(1.0)
            self.handle_round_over(survivors)

    def advance_rider(self, rider, next_cell):
        wrapped = (
            abs(next_cell[0] - rider.cell[0]) + abs(next_cell[1] - rider.cell[1]) > 1
        )
        if wrapped:
            self.cross_portal(rider, next_cell)
        else:
            rider.prev_cell, rider.cell = rider.cell, next_cell
            head = [next_cell[0] * CELL, next_cell[1] * CELL]
            if rider.turned:
                rider.trail.extend(head)
                if rider.trail_life:
                    rider.vidx.append(rider.steps)
            else:
                rider.trail[-2:] = head
        rider.steps += 1
        rider.cells.add(next_cell)
        self.occupied_cells.add(next_cell)
        if rider.trail_life:
            rider.path.append((self.sim_time, next_cell))
        rider.turned = False

    def respawn_rider(self, rider):
        x0, x1, y0, y1 = self.current_cell_bounds()
        occupied = [
            other.cell
            for other in self.riders.values()
            if other.alive and other.pid != rider.pid
        ]
        candidates = []
        for _ in range(5000):
            cell = (random.randint(x0 + 2, x1 - 2), random.randint(y0 + 2, y1 - 2))
            if (
                cell != self.collectible_cell
                and self.is_free(cell)
                and all(
                    abs(cell[0] - ox) + abs(cell[1] - oy) >= 12 for ox, oy in occupied
                )
            ):
                candidates.append(cell)
                break
        if not candidates:
            self.lives_remaining[rider.pid] = 0
            rider.lives = 0
            self.elimination_order.append(rider.pid)
            return

        cell = candidates[0]
        direction = random.choice(DIRS)
        px, py = cell[0] * CELL, cell[1] * CELL
        rider.alive = True
        rider.cell = cell
        rider.prev_cell = cell
        rider.dir = direction
        rider.queue.clear()
        ai.reset(rider)
        rider.turned = False
        rider.trail = [px, py, px, py]
        rider.cells = {cell}
        rider.path = deque([(self.sim_time, cell)])
        rider.vidx = [0]
        rider.steps = 0
        rider.tail = 0
        rider.old = deque()
        rider.cur_first = 0
        rider.lives = self.lives_remaining[rider.pid]
        rider.line_halo, rider.line_glow, rider.line_core = self.new_trail_items(
            rider.color, px, py
        )
        rider.bike = draw_bike(
            self.canvas,
            px,
            py,
            direction,
            rider.color,
            rider.model,
            scale=self.bike_scale,
            tags="game_obj",
        )
        self.occupied_cells.add(cell)
        self.create_head_spark(rider, px, py)
        for item in rider.hint_ids:
            self.canvas.itemconfig(item, state="hidden")

    def expire_trails(self):
        """RASTRO EFÊMERO: some com os trechos mais velhos que `trail_life`, a partir da cauda.

        Libera as células (a moto e a IA podem passar por ali de novo) e encurta a linha desenhada:
        os vértices que a cauda já ultrapassou saem de `trail` e o primeiro ponto vira a nova cauda.
        """
        for r in self.riders.values():
            if not r.alive or not r.trail_life:
                continue
            limit = self.sim_time - r.trail_life
            moved = False
            while len(r.path) > 1 and r.path[0][0] <= limit:
                _, cell = r.path.popleft()
                r.cells.discard(cell)
                self.occupied_cells.discard(cell)
                r.tail += 1
                moved = True
            if not moved:
                continue
            # peças antigas (de antes de um portal) que a cauda já passou por inteiro somem
            while r.old and r.old[0]["last"] < r.tail:
                for it in r.old.popleft()["items"]:
                    self.canvas.delete(it)
            piece = (
                r.old[0] if r.old else None
            )  # a cauda está na peça mais antiga que sobrou
            trail, vidx = (
                (piece["trail"], piece["vidx"]) if piece else (r.trail, r.vidx)
            )
            while len(vidx) > 1 and vidx[1] <= r.tail:
                del trail[0:2]
                del vidx[0]
            vidx[0] = r.tail
            tx, ty = r.path[0][1]
            trail[0:2] = [tx * CELL, ty * CELL]
            if (
                piece
            ):  # a peça atual é redesenhada todo quadro; as antigas só quando mudam
                for it in piece["items"]:
                    self.canvas.coords(it, *trail)

    def new_trail_items(self, color, x, y):
        """Cria as três linhas (halo, brilho, núcleo) de uma peça nova do rastro."""
        return tuple(
            self.canvas.create_line(
                x, y, x, y, fill=tint, width=width, capstyle=tk.ROUND, tags="game_obj"
            )
            for tint, width in T.glow_layers(color, 3)
        )

    def create_head_spark(self, rider, x, y):
        rider.spark_ids = [self.canvas.create_polygon(
            x, y, x, y, x, y, x, y, fill=color, outline="", tags="game_obj")
            for color in (T.blend(rider.color, BG_COLOR, .45), T.CORE)]
        rider.bike.extend(rider.spark_ids)
        self.move_head_spark(rider, x, y)

    def move_head_spark(self, rider, x, y):
        for item, radius in zip(rider.spark_ids, (4, 1.6)):
            self.canvas.coords(item, x + radius, y, x, y + radius,
                               x - radius, y, x, y - radius)

    def trail_fade_pairs(self, r):
        """(item, cor) de todas as peças do rastro (antigas + atual), para dissolver ao morrer."""
        sets = [p["items"] for p in r.old] + [(r.line_halo, r.line_glow, r.line_core)]
        pairs = []
        colors = [tint for tint, _ in T.glow_layers(r.color, 3)]
        for items in sets:
            pairs.extend(zip(items, colors))
        return pairs

    def cross_portal(self, r, entry):
        """Travessia de uma abertura: a linha atual vira uma peça fixa que vai até a parede,
        e uma peça nova começa logo fora da parede oposta, onde a moto reaparece."""
        dx, dy = r.dir
        out = [(r.cell[0] + dx) * CELL, (r.cell[1] + dy) * CELL]
        if r.turned:  # virou na última célula: ela é um vértice e a linha sai dali
            r.trail.extend(out)
            r.vidx.append(r.steps)
        else:
            r.trail[-2:] = out
        items = (r.line_halo, r.line_glow, r.line_core)
        for it in items:
            self.canvas.coords(it, *r.trail)
        r.old.append(
            {
                "trail": r.trail,
                "vidx": r.vidx,
                "items": items,
                "first": r.cur_first,
                "last": r.steps,
            }
        )
        vx, vy = (entry[0] - dx) * CELL, (entry[1] - dy) * CELL
        r.trail = [vx, vy, entry[0] * CELL, entry[1] * CELL]
        r.cur_first = r.steps + 1
        r.vidx = [r.cur_first]
        r.line_halo, r.line_glow, r.line_core = self.new_trail_items(r.color, vx, vy)
        r.prev_cell, r.cell = (entry[0] - dx, entry[1] - dy), entry
        for (
            o
        ) in (
            self.riders.values()
        ):  # as linhas novas nascem por cima: devolve as motos ao topo
            if o.alive:
                for it in o.bike:
                    self.canvas.tag_raise(it)

    def begin_rinzler_escape(self, rider, cells):
        """Rinzler abandona a arena em alta velocidade em vez de se desintegrar."""
        for item in rider.hint_ids:
            self.canvas.delete(item)
        self.fx.fade(
            self.trail_fade_pairs(rider),
            0.65,
            on_done=lambda: self.occupied_cells.difference_update(cells),
        )

        x, y = rider.cell[0] * CELL, rider.cell[1] * CELL
        x0, x1, y0, y1 = self.cell_bounds
        exits = (
            (rider.cell[0] - x0, (-1, 0)),
            (x1 - rider.cell[0], (1, 0)),
            (rider.cell[1] - y0, (0, -1)),
            (y1 - rider.cell[1], (0, 1)),
        )
        _, direction = min(exits, key=lambda exit_path: exit_path[0])
        dx, dy = direction
        edge_distance = min(
            abs((x0 * CELL) - x) if dx < 0 else float("inf"),
            abs((x1 * CELL) - x) if dx > 0 else float("inf"),
            abs((y0 * CELL) - y) if dy < 0 else float("inf"),
            abs((y1 * CELL) - y) if dy > 0 else float("inf"),
        )
        distance = edge_distance + 110
        duration = max(0.55, distance / 680)
        escape_line = self.canvas.create_line(
            x - dx * 24,
            y - dy * 24,
            x,
            y,
            fill=rider.color,
            width=4,
            capstyle=tk.ROUND,
            tags="game_obj",
        )
        started = time.monotonic()

        def animate():
            elapsed = time.monotonic() - started
            progress = min(1.0, elapsed / duration)
            travel = distance * (progress**0.75)
            px, py = x + dx * travel, y + dy * travel
            move_bike(
                self.canvas,
                rider.bike,
                rider.model,
                px,
                py,
                direction,
                scale=self.bike_scale,
                elapsed=self.anim_t + elapsed,
            )
            self.canvas.coords(escape_line, x, y, px, py)
            self.move_head_spark(rider, px, py)
            self.canvas.itemconfig(
                escape_line, fill=blend(rider.color, BG_COLOR, progress)
            )
            if progress >= 1.0:
                for item in rider.bike:
                    self.canvas.delete(item)
                self.canvas.delete(escape_line)
                self.escape_after_id = None
                if self.controller.game_mode == "rinzler" and self.match_complete:
                    self.finish_rinzler_match(1)
                return
            self.escape_after_id = self.root.after(16, animate)

        self.escape_after_id = self.root.after(16, animate)

    def advance_sim(self, dt):
        """Passo fixo: roda quantos ticks couberem no tempo decorrido (independe da granularidade do timer do Windows)."""
        if not self.running or self.paused or self.hit_stop > 0:
            return
        self.tick_ms = max(
            self.tick_min_ms, self.tick_ms - TICK_RAMP * dt
        )  # TICK_RAMP = ms a menos por segundo
        self.acc += dt * 1000
        steps = 0
        while self.acc >= self.tick_ms and self.running and steps < 4:
            self.acc -= self.tick_ms
            self.game_tick()
            steps += 1
            if self.hit_stop > 0:
                self.acc = 0.0
                break
        if steps == 4:  # engasgo grande: descarta o atraso em vez de correr atrás dele
            self.acc = 0.0

    def render_riders(self, alpha=None):
        """Desenha cada moto entre o tick anterior e o atual (alpha 0..1), então o movimento é contínuo."""
        if alpha is None:
            alpha = min(1.0, self.acc / self.tick_ms)
        for r in self.riders.values():
            if not r.alive:
                continue
            px = (r.prev_cell[0] + (r.cell[0] - r.prev_cell[0]) * alpha) * CELL
            py = (r.prev_cell[1] + (r.cell[1] - r.prev_cell[1]) * alpha) * CELL
            pts = r.trail[:-2] + [px, py]
            for it in (r.line_halo, r.line_glow, r.line_core):
                self.canvas.coords(it, *pts)
            move_bike(
                self.canvas,
                r.bike,
                r.model,
                px,
                py,
                r.dir,
                scale=self.bike_scale,
                elapsed=self.sim_time + self.acc / 1000,
            )
            self.move_head_spark(r, px, py)

    def start_animation_loop(self):
        """Loop contínuo de renderização gráfica e efeitos visuais a ~60 FPS."""
        now = time.time()
        dt = now - self.last_frame_time
        self.last_frame_time = now
        self.anim_t += dt

        # Borda e textos de instrução pulsando
        g = 0.5 + 0.5 * math.sin(self.anim_t * 3)
        self.canvas.itemconfig(
            "blink", fill=blend(BG_COLOR, "#00FFFF", 0.35 + 0.65 * g)
        )
        self.canvas.itemconfig("grid_major", fill=blend(GRID_COLOR, GRID_PULSE, g))
        self.canvas.itemconfig(
            "portal_glow",
            fill=blend(
                blend(BG_COLOR, PORTAL_COLOR, 0.15), PORTAL_COLOR, 0.2 + 0.25 * g
            ),
        )

        now_mono = self.sim_time
        for rider in self.riders.values():
            if not rider.hint_ids:
                continue
            px, py = rider.cell[0] * CELL, rider.cell[1] * CELL
            self.canvas.coords(rider.hint_ids[0], px, py - 20)
            self.canvas.coords(rider.hint_ids[1], px, py - 21)
            if rider.hint_until and now_mono >= rider.hint_until:
                for item in rider.hint_ids:
                    self.canvas.itemconfig(item, state="hidden")
                rider.hint_until = 0.0

        effect_dt = min(dt, .1)
        if not self.paused and self.hit_stop > 0:
            frozen = min(effect_dt, self.hit_stop)
            self.hit_stop = max(0, self.hit_stop - frozen)
            effect_dt -= frozen
        self.advance_sim(effect_dt)
        self.update_shrinking_arena(0 if self.paused else effect_dt)
        if self.running and not self.paused:
            self.render_riders()
        if not self.paused:  # com o menu aberto, partículas e contagem congelam junto
            self.fx.update(0 if self.hit_stop > 0 else effect_dt)
        self.chrome.raise_layers()
        self.after_id = self.root.after(FRAME_MS, self.start_animation_loop)

    def handle_round_over(self, survivors):
        self.round_ready_at = time.monotonic() + ROUND_RESTART_COOLDOWN_MS / 1000
        mode = self.controller.game_mode
        winner_text = ""
        winner_color = "#FFFF00"
        match_won = False
        round_won = False
        champion = None

        if mode == "rinzler" and survivors == [1]:
            self.controller.scores[1] = self.controller.match_target
            self.match_complete = True
            self.update_hud()
            self.sound.play("round_win")
            self.sound.play("crowd_cheer")
            return
        if mode == "rinzler" and survivors == [2]:
            self.controller.scores[2] = self.controller.match_target
            self.match_complete = True
            self.update_hud()
            self.sound.play("round_win")
            self.finish_rinzler_match(2)
            return

        if self.is_team_mode():
            if self.final_duel:
                if len(survivors) == 1:
                    champion = 1 if survivors[0] in (1, 3) else 2
                    match_won = True
                    self.match_complete = True
                    winner_color = self.controller.colors[champion]
                else:
                    winner_text = "EMPATE NO X1! PREPARE-SE PARA OUTRO DUELO"
            else:
                t1_alive = 1 in survivors or 3 in survivors
                t2_alive = 2 in survivors or 4 in survivors
                if t1_alive and not t2_alive:
                    round_won = True
                    champion = 1
                    winner_color = self.controller.colors[1]
                elif t2_alive and not t1_alive:
                    round_won = True
                    champion = 2
                    winner_color = self.controller.colors[2]
                else:
                    winner_text = "EMPATE TÁTICO!"

                if round_won:
                    if self.controller.modifiers["collect_items"]:
                        round_won = False
                        winner_text = f"EQUIPE {champion} SOBREVIVEU À RODADA!"
                    else:
                        self.controller.scores[champion] += 1
                        winner_text = f"EQUIPE {champion} VENCEU A RODADA!"
        else:
            if len(survivors) == 1:
                champion = survivors[0]
                round_won = not self.controller.modifiers["collect_items"]
                if round_won:
                    self.controller.scores[champion] += 1
                    winner_text = f"PLAYER {champion} VENCEU A RODADA!"
                else:
                    winner_text = f"PLAYER {champion} SOBREVIVEU À RODADA!"
                winner_color = self.riders[champion].color
            else:
                winner_text = "EMPATE MÚTUO!"

        self.update_hud()
        self.sound.play("round_win")
        if round_won:
            self.sound.play("crowd_cheer")

        target = self.controller.match_target
        cooldown_seconds = ROUND_RESTART_COOLDOWN_MS / 1000

        if mode == "team2v2" and not self.final_duel and round_won:
            if self.controller.scores[champion] >= target:
                winner_team = (1, 3) if champion == 1 else (2, 4)
                loser_team = (2, 4) if champion == 1 else (1, 3)
                winner_rider = next(pid for pid in survivors if pid in winner_team)
                loser_rider = next(
                    (
                        pid
                        for pid in reversed(self.elimination_order)
                        if pid in loser_team
                    ),
                    loser_team[0],
                )
                self.finalists = (winner_rider, loser_rider)
                self.final_duel = True
                winner_text = f"X1 DECISIVO: P{winner_rider} VS P{loser_rider}"
                self.update_hud()
        elif not self.final_duel:
            for pid, score in self.controller.scores.items():
                if score >= target:
                    champion = pid
                    match_won = True
                    break

        if match_won:
            self.sound.play("match_win")
            self.sound.set_music_track("victory")
            self.show_match_victory(champion)
            self.victory_buttons[0].configure(
                state="disabled", text=f"AGUARDE {cooldown_seconds:g}s"
            )
            self.update_victory_selection()
        else:
            cx, cy = self.width // 2, self.height // 2
            t = self.canvas.create_text(
                cx,
                cy - 30,
                text=winner_text,
                font=("Courier", 26, "bold"),
                fill=BG_COLOR,
                tags="game_obj",
            )
            self.fx.text_in(t, winner_color, 0.6)
            self.fx.ring(cx, cy - 30, winner_color, max_r=260, dur=0.7)
            if round_won:
                self.launch_fireworks(winner_color, 4, gap=0.25)
            self.next_round_text_id = self.canvas.create_text(
                cx,
                cy + 25,
                text=f"AGUARDE {cooldown_seconds:g}s PARA A PRÓXIMA RODADA",
                font=("Courier", 15),
                fill="#FFFFFF",
                tags=("game_obj", "blink"),
            )
            if self.final_duel:
                self.canvas.itemconfig(
                    self.next_round_text_id,
                    text=f"AGUARDE • X1 ENTRE P{self.finalists[0]} E P{self.finalists[1]}",
                )
        self.restart_cooldown_id = self.root.after(
            ROUND_RESTART_COOLDOWN_MS, self.finish_round_cooldown
        )

    def finish_rinzler_match(self, champion):
        self.rinzler_champion = champion
        self.sound.play("match_win")
        self.sound.set_music_track("victory")
        self.show_match_victory(champion)
        cooldown_seconds = ROUND_RESTART_COOLDOWN_MS / 1000
        self.victory_buttons[0].configure(
            state="disabled", text=f"AGUARDE {cooldown_seconds:g}s"
        )
        self.round_ready_at = time.monotonic() + cooldown_seconds
        self.update_victory_selection()
        self.restart_cooldown_id = self.root.after(
            ROUND_RESTART_COOLDOWN_MS, self.finish_round_cooldown
        )

    def launch_fireworks(self, color, count, gap):
        """Fogos estilo Grade sobre a arena, um a cada ~gap segundos, com estouro sonoro."""
        bm = BORDER_MARGIN
        for i in range(count):
            x = random.randint(bm + 120, self.width - bm - 120)
            y = random.randint(bm + 130, int(self.height * 0.55))
            c = random.choice((color, color, "#FFFFFF"))
            delay = i * gap * random.uniform(0.7, 1.3)
            self.fx.after(
                delay,
                lambda x=x, y=y, c=c: self.fx.firework(
                    x, y, c, size=random.uniform(120, 190)
                ),
            )
            self.fx.after(delay + 0.35, lambda: self.sound.play("firework"))

    def finish_round_cooldown(self):
        self.restart_cooldown_id = None
        if not self.game_over:
            return
        if self.next_round_text_id is not None:
            self.canvas.delete(self.next_round_text_id)
            self.next_round_text_id = None
            prompt = (
                start_prompt("INICIA O X1 DECISIVO")
                if self.final_duel
                else start_prompt("PARA A PRÓXIMA RODADA")
            )
            draw_round_start_prompt(
                self.canvas,
                self.width // 2,
                self.height // 2 + 25,
                prompt,
                "next_round_prompt",
            )
        if self.victory_buttons:
            label = (
                "CONTINUAR PERSEGUIÇÃO"
                if self.controller.game_mode == "rinzler"
                and getattr(self, "rinzler_champion", None) == 1
                else "REVANCHE"
            )
            self.victory_buttons[0].configure(state="normal", text=label)
            self.update_victory_selection()

    def draw_victory_hint(self):
        self.canvas.delete("victory_hint")
        draw_control_prompt(
            self.canvas,
            self.width // 2,
            self.height // 2 + 144,
            victory_hints(),
            ("Courier", 9, "bold"),
            "#6A8AAA",
            ("game_obj", "victory_hint"),
        )

    def update_victory_selection(self):
        if not self.victory_buttons:
            return
        for index, button in enumerate(self.victory_buttons):
            selected = index == self.victory_selection
            disabled = str(button.cget("state")) == "disabled"
            button.configure(
                relief="flat",
                bg="#00FFFF" if selected and not disabled else "#08111c",
                fg="#030308" if selected and not disabled else "#71869A",
                activebackground="#66FFFF",
                activeforeground="#030308",
                highlightthickness=2,
                highlightbackground=CYAN if selected else "#183247",
                highlightcolor=CYAN if selected else "#183247",
            )

    def select_victory_option(self, step):
        if not self.victory_buttons:
            return
        candidate = self.victory_selection
        for _ in self.victory_buttons:
            candidate = (candidate + step) % len(self.victory_buttons)
            if str(self.victory_buttons[candidate].cget("state")) != "disabled":
                self.victory_selection = candidate
                break
        self.sound.play("menu_move")
        self.update_victory_selection()

    def activate_victory_option(self):
        if not self.victory_buttons:
            return
        button = self.victory_buttons[self.victory_selection]
        if str(button.cget("state")) != "disabled":
            self.sound.play("menu_select")
            button.invoke()

    def show_match_victory(self, champion):
        self.canvas.delete("game_obj")
        col = self.controller.colors.get(champion, "#00FFFF")

        if self.controller.game_mode == "rinzler":
            if champion == 1:
                title_text = "RINZLER ESCAPOU — POR ENQUANTO"
                score_text = "VOCÊ VENCEU O DUELO. A PERSEGUIÇÃO AINDA NÃO ACABOU."
            else:
                title_text = "RINZLER VENCEU"
                score_text = "SUA TRILHA TERMINA AQUI... POR ENQUANTO."
        elif self.is_team_mode():
            title_text = f"CAMPEÃ DA PARTIDA: EQUIPE {champion}"
            score_text = (
                f"PLACAR FINAL: EQUIPE 1 ({self.controller.scores[1]})  •  "
                f"EQUIPE 2 ({self.controller.scores[2]})"
            )
        else:
            title_text = f"CAMPEÃO DA PARTIDA: PLAYER {champion}"
            score_text = (
                f"PLACAR FINAL: P1 ({self.controller.scores[1]})  •  "
                f"P2 ({self.controller.scores[2]})  •  P3 ({self.controller.scores[3]})  •  "
                f"P4 ({self.controller.scores[4]})"
            )
        title = self.canvas.create_text(
            self.width // 2,
            self.height // 2 - 80,
            text=title_text,
            font=("Courier", 32, "bold"),
            fill=BG_COLOR,
            tags="game_obj",
        )
        self.fx.text_in(title, col, 0.8)
        self.canvas.create_text(
            self.width // 2,
            self.height // 2 - 20,
            text=score_text,
            font=("Courier", 16),
            fill="#FFFFFF",
            tags="game_obj",
        )
        self.draw_victory_hint()

        self.launch_fireworks(col, 14, gap=0.3)  # festa na cor do campeão

        continue_chase = self.controller.game_mode == "rinzler" and champion == 1
        btn_rematch = tk.Button(
            self,
            text="CONTINUAR PERSEGUIÇÃO" if continue_chase else "REVANCHE",
            font=("Courier", 13, "bold"),
            fg="#030308",
            bg="#00FFFF",
            activebackground="#008888",
            activeforeground="#FFFFFF",
            width=20,
            relief="flat",
            cursor="hand2",
            bd=0,
            highlightthickness=2,
            highlightbackground="#183247",
            command=(
                (lambda: self.controller.start_chase(from_duel=True))
                if continue_chase
                else self.init_round
            ),
        )
        btn_rematch.place(
            x=self.width // 2 - 250, y=self.height // 2 + 70, width=230, height=50
        )

        btn_menu = tk.Button(
            self,
            text="MENU PRINCIPAL",
            font=("Courier", 13, "bold"),
            fg="#FFFFFF",
            bg="#FF0055",
            activebackground="#880022",
            activeforeground="#FFFFFF",
            width=20,
            relief="flat",
            cursor="hand2",
            bd=0,
            highlightthickness=2,
            highlightbackground="#183247",
            command=self.controller.show_menu,
        )
        btn_menu.place(
            x=self.width // 2 + 20, y=self.height // 2 + 70, width=230, height=50
        )
        self.victory_buttons = [btn_rematch, btn_menu]
        self.victory_selection = 0
        self.update_victory_selection()


if __name__ == "__main__":
    root = tk.Tk()
    app = LightCycleGame(root)
    root.mainloop()

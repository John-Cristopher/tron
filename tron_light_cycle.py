import tkinter as tk
import time
import math
import random
from collections import deque

# Importação dos módulos do projeto
from config import (
    BG_COLOR, GRID_COLOR, CELL, BORDER_MARGIN, MATCH_TARGET, CYAN, NEON, PALETTES, MAPS, RANDOM_MAP,
    KEY_LOOKUP, FRAME_MS, TICK_START_MS, TICK_MIN_MS, TICK_RAMP, DISSOLVE_DELAY, DISSOLVE_SEC, blend
)
from effects import Effects, BIKES, draw_bike, move_bike
from sound import SoundManager
import ai

DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]


class Rider:
    """Representa uma moto (jogador ou IA) na arena, estruturada para integração com o módulo ai.py[cite: 1]."""
    def __init__(self, pid, cell, direction, color, model=0):
        self.pid = pid
        self.cell = cell          # Posicionamento em coordenadas de célula da grade
        self.dir = direction      # Direção atual (dx, dy)
        self.alive = True
        self.queue = []           # Fila de comandos de direção (input buffer)
        self.color = color
        self.model = model        # Índice em effects.BIKES
        self.trail = [cell[0] * CELL, cell[1] * CELL, cell[0] * CELL, cell[1] * CELL]
        self.line_glow = None
        self.line_core = None
        self.bike = []            # Itens do canvas que desenham a moto
        self.is_ai = False


class LightCycleGame:
    """Controlador principal do jogo, gerenciando telas, placares, áudio e estados globais[cite: 4, 5]."""
    def __init__(self, root):
        self.root = root
        self.root.title("TRON: LIGHT CYCLE ULTIMATE")
        self.root.attributes("-fullscreen", True)
        self.root.configure(bg=BG_COLOR)

        # Inicializar gerenciador de som[cite: 4]
        self.sound = SoundManager()
        self.sound.start_music()

        # Obter resolução real da tela
        self.screen_width = root.winfo_screenwidth()
        self.screen_height = root.winfo_screenheight()

        # Atalhos globais
        self.root.bind("<Escape>", lambda e: self.quit_game())
        self.root.bind("r", lambda e: self.reset_match())
        self.root.bind("R", lambda e: self.reset_match())

        # Placar global da partida
        self.scores = {1: 0, 2: 0, 3: 0, 4: 0}
        self.match_target = MATCH_TARGET

        # Configurações padrão de jogo (o menu lembra a última escolha)
        self.game_mode = "1v1"  # "1v1", "ffa4", "team2v2", "training"
        self.colors = {pid: pal[0][1] for pid, pal in PALETTES.items()}
        self.models = {1: 0, 2: 1, 3: 2, 4: 1}
        self.map_idx = 0

        self.current_frame = None
        self.show_menu()

    def quit_game(self):
        self.sound.shutdown()
        self.root.destroy()

    def clear_screen(self):
        if self.current_frame:
            if hasattr(self.current_frame, "destroy_arena"):
                self.current_frame.destroy_arena()
            self.current_frame.destroy()

    def show_menu(self):
        self.sound.play("select")
        self.clear_screen()
        self.current_frame = MainMenu(self.root, self)

    def start_game(self, mode, color_config, model_config, map_idx):
        self.sound.play("select")
        self.game_mode = mode
        self.map_idx = map_idx
        self.colors.update(color_config)
        self.models.update(model_config)
        self.scores = {1: 0, 2: 0, 3: 0, 4: 0}
        self.clear_screen()
        self.current_frame = GameArena(self.root, self)

    def reset_match(self):
        self.sound.play("select")
        self.scores = {1: 0, 2: 0, 3: 0, 4: 0}
        if isinstance(self.current_frame, GameArena):
            self.current_frame.init_round()
            self.current_frame.update_hud()


class MainMenu(tk.Frame):
    """Menu animado desenhado em canvas: cards de modo, cor e modelo de moto por corredor."""
    # (chave, título, descrição, ícone: [(pid, offset x, offset y, direção)])
    MODES = [
        ("1v1", "1 VS 1", "Duelo clássico", [(1, -8, 0, (1, 0)), (2, 8, 0, (-1, 0))]),
        ("ffa4", "TODOS x TODOS", "4 jogadores, cada um por si",
         [(1, -8, 0, (1, 0)), (2, 8, 0, (-1, 0)), (3, 0, -8, (0, 1)), (4, 0, 8, (0, -1))]),
        ("team2v2", "EQUIPES 2v2", "P1+P3 vs P2+P4",
         [(1, -8, -7, (1, 0)), (3, -8, 7, (1, 0)), (2, 8, -7, (-1, 0)), (4, 8, 7, (-1, 0))]),
        ("training", "TREINO", "Você contra a IA", [(1, -8, 0, (1, 0)), (2, 8, 0, (-1, 0))]),
    ]
    PLAYERS = {1: ("PLAYER 1", "W A S D"), 2: ("PLAYER 2", "SETAS"), 3: ("PLAYER 3", "U H J K"), 4: ("PLAYER 4", "NUMPAD")}

    def __init__(self, parent, controller):
        super().__init__(parent, bg=BG_COLOR)
        self.controller = controller
        self.pack(fill=tk.BOTH, expand=True)
        self.W, self.H = controller.screen_width, controller.screen_height

        self.cv = tk.Canvas(self, width=self.W, height=self.H, bg=BG_COLOR, highlightthickness=0)
        self.cv.pack(fill=tk.BOTH, expand=True)
        self.fx = Effects(self.cv)

        self.mode = controller.game_mode
        self.color_idx = {p: next((i for i, (_, c) in enumerate(pal) if c == controller.colors[p]), 0)
                          for p, pal in PALETTES.items()}
        self.model_idx = dict(controller.models)
        self.map_idx = controller.map_idx
        self.t = 0.0
        self.last = time.time()
        self.after_id = None
        self.sel_card = None
        self.preview_glows = []

        self.draw_background()
        self.draw_title()
        self.draw_ui()
        self.winfo_toplevel().bind("<KeyPress>", self.on_key)
        self.loop()

    def destroy(self):
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None
        super().destroy()

    def color(self, pid):
        return PALETTES[pid][self.color_idx[pid]][1]

    def is_ai(self, pid):
        return self.mode == "training" and pid == 2

    # ---- desenho
    def draw_background(self):
        for x in range(0, self.W, 40):
            self.cv.create_line(x, 0, x, self.H, fill=GRID_COLOR, tags="bg")
        for y in range(0, self.H, 40):
            self.cv.create_line(0, y, self.W, y, fill=GRID_COLOR, tags="bg")
        # Motos de demonstração andando pelo fundo
        self.demo = []
        for col in NEON[:4]:
            x = random.randrange(2, self.W // 40 - 2) * 40
            y = random.randrange(2, self.H // 40 - 2) * 40
            dim, model = blend(col, BG_COLOR, 0.55), random.randrange(len(BIKES))
            self.demo.append({
                "x": x, "y": y, "d": random.choice(DIRS), "pts": deque([(x, y), (x, y)], maxlen=90), "model": model,
                "line": self.cv.create_line(x, y, x, y, fill=dim, width=3, tags="bg"),
                "bike": draw_bike(self.cv, x, y, (1, 0), dim, model, 1.3, tags="bg"),
            })

    def draw_title(self):
        cx, ty = self.W // 2, int(self.H * 0.11)
        f = ("Courier", 72, "bold")
        self.title_glow = [self.cv.create_text(cx + dx, ty + dy, text="TRON", font=f, fill=BG_COLOR)
                           for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3))]
        self.cv.create_text(cx, ty, text="TRON", font=f, fill="#E8FFFF")
        self.title_line = self.cv.create_line(cx, ty + 42, cx, ty + 42, fill=CYAN, width=2)
        sub = self.cv.create_text(cx, ty + 64, text="L I G H T   C Y C L E   U L T I M A T E",
                                  font=("Courier", 14, "bold"), fill=BG_COLOR)
        self.fx.text_in(sub, CYAN, 1.2)
        hint = self.cv.create_text(cx, self.H - 18, text="ENTER inicia   •   ← → troca o modo   •   ESC sai",
                                   font=("Courier", 10), fill=BG_COLOR)
        self.fx.text_in(hint, "#4A6A88", 2.0)

    def clickable(self, tag, rect, cmd):
        """Hover (borda mais grossa + cursor de mão) e clique para itens com a mesma tag."""
        w = float(self.cv.itemcget(rect, "width"))
        self.cv.tag_bind(tag, "<Button-1>", lambda e: cmd())
        self.cv.tag_bind(tag, "<Enter>", lambda e: (self.cv.itemconfig(rect, width=w + 2), self.cv.config(cursor="hand2")))
        self.cv.tag_bind(tag, "<Leave>", lambda e: (self.cv.itemconfig(rect, width=w), self.cv.config(cursor="")))

    def draw_ui(self):
        self.cv.delete("ui")
        self.cv.config(cursor="")
        self.preview_glows = []
        self.draw_modes()
        self.draw_map_selector()
        self.draw_players()
        self.draw_buttons()

    def draw_modes(self):
        cv, n = self.cv, len(self.MODES)
        cw, ch, gap = min(270, (self.W - 80) // n - 20), 130, 20
        y0 = int(self.H * 0.24)
        x0 = self.W // 2 - (n * cw + (n - 1) * gap) // 2
        cv.create_text(self.W // 2, y0 - 16, text="MODO DE JOGO", font=("Courier", 12, "bold"), fill="#5A7A99", tags="ui")
        self.card_pos = {}
        for i, (key, title, desc, icon) in enumerate(self.MODES):
            x, tag, sel = x0 + i * (cw + gap), f"mode_{key}", key == self.mode
            mx = x + cw / 2
            self.card_pos[key] = (mx, y0 + ch / 2)
            rect = cv.create_rectangle(x, y0, x + cw, y0 + ch, fill="#0b1426" if sel else "#06060f",
                                       outline=CYAN if sel else "#1a2a44", width=3 if sel else 2, tags=("ui", tag))
            if sel:
                self.sel_card = rect
            for pid, ox, oy, d in icon:
                col = "#778899" if key == "training" and pid == 2 else self.color(pid)
                draw_bike(cv, mx + ox, y0 + 38 + oy, d, col, self.model_idx[pid], 0.9, tags=("ui", tag))
            cv.create_text(mx, y0 + 82, text=title, font=("Courier", 14, "bold"),
                           fill="#FFFFFF" if sel else "#8899AA", tags=("ui", tag))
            cv.create_text(mx, y0 + 106, text=desc, font=("Courier", 10), fill="#6A8AAA", tags=("ui", tag))
            self.clickable(tag, rect, lambda k=key: self.set_mode(k))

    def draw_map_selector(self):
        cv, cx = self.cv, self.W // 2
        my = (int(self.H * 0.24) + 130 + int(self.H * 0.5)) // 2   # entre os cards de modo e os painéis
        name = "ALEATÓRIO" if self.map_idx == RANDOM_MAP else MAPS[self.map_idx][0]
        cv.create_text(cx - 60, my, text=f"MAPA: {name}", font=("Courier", 13, "bold"), fill="#FFFFFF", tags="ui")

        # Miniatura do mapa
        x1, y1, x2, y2 = cx + 85, my - 18, cx + 149, my + 18
        cv.create_rectangle(x1, y1, x2, y2, fill=BG_COLOR, outline=CYAN, width=1, tags="ui")
        if self.map_idx == RANDOM_MAP:
            cv.create_text((x1 + x2) / 2, my, text="?", font=("Courier", 16, "bold"), fill=CYAN, tags="ui")
        else:
            for a, b, c, d in MAPS[self.map_idx][1]:
                cv.create_rectangle(x1 + a * 64, y1 + b * 36, x1 + c * 64, y1 + d * 36,
                                    fill="#2a6a99", outline="", tags="ui")

        for step, ax in ((-1, cx - 230), (1, cx + 185)):
            tag = f"map_{step}"
            r = cv.create_rectangle(ax - 14, my - 13, ax + 14, my + 13, fill="#0b1426", outline=CYAN, width=1, tags=("ui", tag))
            cv.create_text(ax, my, text="<" if step < 0 else ">", font=("Courier", 13, "bold"), fill=CYAN, tags=("ui", tag))
            self.clickable(tag, r, lambda s=step: self.set_map(s))

    def draw_players(self):
        cv = self.cv
        ids = [1, 2] if self.mode in ("1v1", "training") else [1, 2, 3, 4]
        pw, ph, gap = 250, 250, 24
        y0 = int(self.H * 0.5)
        x0 = self.W // 2 - (len(ids) * pw + (len(ids) - 1) * gap) // 2
        for i, pid in enumerate(ids):
            x = x0 + i * (pw + gap)
            cx, col = x + pw / 2, self.color(pid)
            name, keys = ("IA", "COMPUTADOR") if self.is_ai(pid) else self.PLAYERS[pid]

            cv.create_rectangle(x, y0, x + pw, y0 + ph, fill="#05050c", outline=blend(col, BG_COLOR, 0.6), width=2, tags="ui")
            cv.create_line(x, y0 + 20, x, y0, x + 20, y0, fill=col, width=3, tags="ui")
            cv.create_line(x + pw - 20, y0 + ph, x + pw, y0 + ph, x + pw, y0 + ph - 20, fill=col, width=3, tags="ui")
            cv.create_text(cx, y0 + 22, text=name, font=("Courier", 14, "bold"), fill=col, tags="ui")
            cv.create_text(cx, y0 + 44, text=keys, font=("Courier", 10), fill="#6A8AAA", tags="ui")

            # Prévia da moto com rastro pulsante
            py = y0 + 100
            glow = cv.create_line(x + 16, py, cx - 10, py, fill=col, width=7, capstyle=tk.ROUND, tags="ui")
            cv.create_line(x + 16, py, cx - 10, py, fill="#FFFFFF", width=2, capstyle=tk.ROUND, tags="ui")
            draw_bike(cv, cx + 50, py, (1, 0), col, self.model_idx[pid], 3, tags="ui")
            self.preview_glows.append(glow)

            # Amostras de cor (sem código hex: só o nome)
            pal = PALETTES[pid]
            for j, (_, c) in enumerate(pal):
                sx, sy, tag = cx + (j - (len(pal) - 1) / 2) * 38, y0 + 158, f"sw_{pid}_{j}"
                ring = cv.create_oval(sx - 15, sy - 15, sx + 15, sy + 15, fill=BG_COLOR,
                                      outline="#FFFFFF" if j == self.color_idx[pid] else "#1a2a44", width=2, tags=("ui", tag))
                cv.create_oval(sx - 10, sy - 10, sx + 10, sy + 10, fill=c, outline="", tags=("ui", tag))
                self.clickable(tag, ring, lambda p=pid, j=j, sx=sx, sy=sy: self.set_color(p, j, sx, sy))
            cv.create_text(cx, y0 + 188, text=pal[self.color_idx[pid]][0], font=("Courier", 11, "bold"), fill=col, tags="ui")

            # Seletor de modelo
            my = y0 + 222
            cv.create_text(cx, my, text=BIKES[self.model_idx[pid]][0], font=("Courier", 12, "bold"), fill="#FFFFFF", tags="ui")
            for step, ax in ((-1, cx - 95), (1, cx + 95)):
                tag = f"mdl_{pid}_{step}"
                r = cv.create_rectangle(ax - 14, my - 13, ax + 14, my + 13, fill="#0b1426", outline=col, width=1, tags=("ui", tag))
                cv.create_text(ax, my, text="<" if step < 0 else ">", font=("Courier", 13, "bold"), fill=col, tags=("ui", tag))
                self.clickable(tag, r, lambda p=pid, s=step: self.set_model(p, s))

    def draw_buttons(self):
        cv, cx, by = self.cv, self.W // 2, int(self.H * 0.9)
        for tag, x, w, text, fill, fg, cmd in (
            ("btn_start", cx - 110, 260, "INICIAR PARTIDA", CYAN, BG_COLOR, self.on_start),
            ("btn_exit", cx + 120, 160, "SAIR", BG_COLOR, "#FF0055", self.controller.quit_game),
        ):
            r = cv.create_rectangle(x - w / 2, by - 24, x + w / 2, by + 24, fill=fill,
                                    outline=fg if fill == BG_COLOR else fill, width=2, tags=("ui", tag))
            cv.create_text(x, by, text=text, font=("Courier", 15, "bold"), fill=fg, tags=("ui", tag))
            self.clickable(tag, r, cmd)

    # ---- interação
    def set_mode(self, key):
        self.mode = key
        self.controller.sound.play("move")
        self.draw_ui()
        x, y = self.card_pos[key]
        self.fx.ring(x, y, CYAN, max_r=120, dur=0.45)

    def set_color(self, pid, j, sx, sy):
        self.color_idx[pid] = j
        self.controller.sound.play("move")
        self.draw_ui()
        self.fx.ring(sx, sy, self.color(pid), max_r=34, dur=0.35)

    def set_model(self, pid, step):
        self.model_idx[pid] = (self.model_idx[pid] + step) % len(BIKES)
        self.controller.sound.play("move")
        self.draw_ui()

    def set_map(self, step):
        self.map_idx = (self.map_idx + step) % (len(MAPS) + 1)
        self.controller.sound.play("move")
        self.draw_ui()

    def on_key(self, event):
        if event.keysym == "Return":
            self.on_start()
        elif event.keysym in ("Left", "Right"):
            keys = [m[0] for m in self.MODES]
            i = keys.index(self.mode) + (1 if event.keysym == "Right" else -1)
            self.set_mode(keys[i % len(keys)])

    def on_start(self):
        colors = {pid: self.color(pid) for pid in PALETTES}
        self.controller.start_game(self.mode, colors, dict(self.model_idx), self.map_idx)

    # ---- animação
    def step_demo(self):
        for c in self.demo:
            if c["x"] % 40 == 0 and c["y"] % 40 == 0:
                def inside(d):
                    return 40 <= c["x"] + d[0] * 40 <= self.W - 40 and 40 <= c["y"] + d[1] * 40 <= self.H - 40
                if random.random() < 0.18 or not inside(c["d"]):
                    back = (-c["d"][0], -c["d"][1])
                    c["d"] = random.choice([d for d in DIRS if d != back and inside(d)])
            c["x"] += c["d"][0] * 4
            c["y"] += c["d"][1] * 4
            c["pts"].append((c["x"], c["y"]))
            self.cv.coords(c["line"], *[v for p in c["pts"] for v in p])
            move_bike(self.cv, c["bike"], c["model"], c["x"], c["y"], c["d"], 1.3)

    def loop(self):
        now = time.time()
        dt, self.last = now - self.last, now
        self.t += dt
        self.step_demo()

        g = 0.5 + 0.5 * math.sin(self.t * 2.2)
        for it in self.title_glow:
            self.cv.itemconfig(it, fill=blend(BG_COLOR, CYAN, 0.25 + 0.45 * g))
        half = min(1.0, self.t / 0.8) * 260
        cx = self.W // 2
        y = self.cv.coords(self.title_line)[1]
        self.cv.coords(self.title_line, cx - half, y, cx + half, y)
        if self.sel_card:
            self.cv.itemconfig(self.sel_card, outline=blend(CYAN, "#FFFFFF", 0.5 * g))
        for glow in self.preview_glows:
            self.cv.itemconfig(glow, width=6 + 4 * g)

        self.fx.update(dt)
        self.after_id = self.after(FRAME_MS, self.loop)


class GameArena(tk.Frame):
    """Arena de jogo com spawns seguros longe dos obstáculos, botão de menu e efeitos visuais[cite: 3, 5]."""
    def __init__(self, parent, controller):
        super().__init__(parent, bg=BG_COLOR)
        self.controller = controller
        self.root = parent
        self.sound = controller.sound
        self.pack(fill=tk.BOTH, expand=True)

        self.width = controller.screen_width
        self.height = controller.screen_height

        # Canvas otimizado[cite: 3]
        self.canvas = tk.Canvas(self, width=self.width, height=self.height, bg=BG_COLOR, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Inicializar sistema de efeitos visuais[cite: 3]
        self.fx = Effects(self.canvas)

        # Desenhar grade de fundo[cite: 2]
        self.draw_grid()

        # Desenhar bordas luminosas perfeitamente alinhadas
        bm = BORDER_MARGIN
        self.border_id = self.canvas.create_rectangle(bm, bm + 30, self.width - bm, self.height - bm, outline="#00FFFF", width=4, tags="arena_static")
        self.canvas.create_rectangle(bm - 4, bm + 26, self.width - bm + 4, self.height - bm + 4, outline="#004466", width=2, tags="arena_static")

        # HUD Superior
        self.hud_text = self.canvas.create_text(self.width // 2, 20, text="", font=("Courier", 13, "bold"), fill="#00FFFF", tags="hud")

        # Botões de interface na arena (incluindo o botão MENU)
        btn_menu = tk.Button(self, text="MENU", font=("Courier", 9, "bold"), fg="#FFFFFF", bg="#331133",
                             activebackground="#663366", activeforeground="#FF00FF", relief="flat", cursor="hand2", command=self.controller.show_menu)
        btn_menu.place(x=self.width - 330, y=8, width=90, height=24)

        btn_pause = tk.Button(self, text="PAUSAR (P)", font=("Courier", 9, "bold"), fg="#FFFFFF", bg="#111133",
                              activebackground="#333366", activeforeground="#00FFFF", relief="flat", cursor="hand2", command=self.toggle_pause)
        btn_pause.place(x=self.width - 230, y=8, width=100, height=24)

        btn_reset = tk.Button(self, text="RESET (R)", font=("Courier", 9, "bold"), fg="#FFFFFF", bg="#331111",
                              activebackground="#663333", activeforeground="#FF0055", relief="flat", cursor="hand2", command=self.controller.reset_match)
        btn_reset.place(x=self.width - 120, y=8, width=100, height=24)

        # Estados do jogo
        self.running = False
        self.paused = False
        self.game_over = False
        self.counting = False
        self.riders = {}
        self.occupied_cells = set()
        self.tick_ms = TICK_START_MS
        self.after_id = None       # loop de animação (não pode ser cancelado entre rodadas)
        self.tick_id = None        # loop de lógica do jogo
        self.last_frame_time = time.time()
        self.anim_t = 0.0

        # Vincular teclas globais[cite: 2]
        self.winfo_toplevel().bind("<KeyPress>", self.on_key_press)

        self.init_round()
        self.start_animation_loop()

    def destroy_arena(self):
        for attr in ("after_id", "tick_id"):
            if getattr(self, attr):
                self.root.after_cancel(getattr(self, attr))
                setattr(self, attr, None)

    def draw_grid(self):
        step = 60
        for x in range(0, self.width, step):
            self.canvas.create_line(x, 0, x, self.height, fill=GRID_COLOR, width=1, tags="grid")
        for y in range(0, self.height, step):
            self.canvas.create_line(0, y, self.width, y, fill=GRID_COLOR, width=1, tags="grid")

    def update_hud(self):
        scores = self.controller.scores
        mode = self.controller.game_mode
        if mode == "team2v2":
            t1 = scores[1] + scores[3]
            t2 = scores[2] + scores[4]
            txt = f"EQUIPE 1 (P1+P3): {t1}   |   EQUIPE 2 (P2+P4): {t2}   (Alvo: {self.controller.match_target})"
        else:
            active_p = [1, 2] if mode in ["1v1", "training"] else [1, 2, 3, 4]
            txt = "   |   ".join([f"P{p}: {scores[p]}" for p in active_p])
            txt += f"   (Alvo: {self.controller.match_target})"
        txt += f"   |   MAPA: {self.map_name}"
        self.canvas.itemconfig(self.hud_text, text=txt)

    def is_free(self, cell):
        """Método exigido pelo módulo ai.py para verificar células livres[cite: 1]."""
        cx, cy = cell
        # Primeira/última célula estritamente dentro das paredes (nunca sobre a linha)
        min_cx = BORDER_MARGIN // CELL + 1
        max_cx = (self.width - BORDER_MARGIN - 1) // CELL
        min_cy = (BORDER_MARGIN + 30) // CELL + 1
        max_cy = (self.height - BORDER_MARGIN - 1) // CELL

        if not (min_cx <= cx <= max_cx and min_cy <= cy <= max_cy):
            return False
        return cell not in self.occupied_cells

    def init_round(self):
        if self.tick_id:
            self.root.after_cancel(self.tick_id)
            self.tick_id = None

        # Remove botões da tela de campeão e zera o placar se a partida já terminou
        for btn in getattr(self, "victory_buttons", []):
            btn.destroy()
        self.victory_buttons = []
        if max(self.controller.scores.values()) >= self.controller.match_target:
            self.controller.scores = {1: 0, 2: 0, 3: 0, 4: 0}

        self.canvas.delete("game_obj")
        self.fx.reset()
        self.game_over = False
        self.paused = False
        self.running = False
        self.counting = False
        self.tick_ms = TICK_START_MS
        self.occupied_cells = set()

        mode = self.controller.game_mode
        active_ids = [1, 2] if mode in ["1v1", "training"] else [1, 2, 3, 4]

        # Criar obstáculos do mapa na arena primeiro
        self.create_obstacles()
        self.update_hud()

        # Spawns seguros nas laterais da arena (longe do centro onde ficam os obstáculos)
        min_cx = (BORDER_MARGIN + 40) // CELL
        max_cx = (self.width - BORDER_MARGIN - 40) // CELL
        min_cy = (BORDER_MARGIN + 70) // CELL
        max_cy = (self.height - BORDER_MARGIN - 40) // CELL
        cx_grid = (self.width // 2) // CELL
        cy_grid = (self.height // 2) // CELL

        configs = {
            1: {"cell": (min_cx + 10, cy_grid), "dir": (1, 0)},       # Esquerda, movendo-se para a direita
            2: {"cell": (max_cx - 10, cy_grid), "dir": (-1, 0)},      # Direita, movendo-se para a esquerda
            3: {"cell": (cx_grid, min_cy + 10), "dir": (0, 1)},       # Topo, movendo-se para baixo
            4: {"cell": (cx_grid, max_cy - 10), "dir": (0, -1)}       # Base, movendo-se para cima
        }

        self.riders = {}
        for pid in active_ids:
            cfg = configs[pid]
            cell = cfg["cell"]
            d = cfg["dir"]
            color = self.controller.colors[pid]
            model = self.controller.models[pid]

            px, py = cell[0] * CELL, cell[1] * CELL
            glow = self.canvas.create_line(px, py, px, py, fill=color, width=5, capstyle=tk.ROUND, tags="game_obj")
            core = self.canvas.create_line(px, py, px, py, fill="#FFFFFF", width=2, capstyle=tk.ROUND, tags="game_obj")

            rider = Rider(pid, cell, d, color, model)
            rider.line_glow = glow
            rider.line_core = core
            rider.bike = draw_bike(self.canvas, px, py, d, color, model, tags="game_obj")
            if mode == "training" and pid == 2:
                rider.is_ai = True

            self.riders[pid] = rider
            self.occupied_cells.add(cell)

        self.msg_id = self.canvas.create_text(
            self.width // 2, self.height // 2,
            text="PRESSIONE ESPAÇO PARA INICIAR A RODADA",
            font=("Courier", 20, "bold"), fill="#00FFFF", tags=("game_obj", "blink")
        )
        map_lbl = self.canvas.create_text(self.width // 2, self.height // 2 - 45, text=f"MAPA: {self.map_name}",
                                          font=("Courier", 16, "bold"), fill=BG_COLOR, tags="game_obj")
        self.fx.text_in(map_lbl, "#FFFFFF", 0.6)

    def create_obstacles(self):
        idx = self.controller.map_idx
        if idx == RANDOM_MAP:
            idx = random.randrange(len(MAPS))   # sorteia a cada rodada
        self.map_name, rects = MAPS[idx]
        bm = BORDER_MARGIN
        left, top = bm, bm + 30
        w, h = self.width - 2 * bm, self.height - top - bm
        for fx1, fy1, fx2, fy2 in rects:
            x1, y1, x2, y2 = left + fx1 * w, top + fy1 * h, left + fx2 * w, top + fy2 * h
            self.canvas.create_rectangle(x1, y1, x2, y2, outline="#004466", fill="#0a0a22", width=2, tags="game_obj")
            for cx_coord in range(int(x1) // CELL, int(x2) // CELL + 1):
                for cy_coord in range(int(y1) // CELL, int(y2) // CELL + 1):
                    self.occupied_cells.add((cx_coord, cy_coord))

    def toggle_pause(self):
        if self.running:
            self.paused = not self.paused
            self.sound.play("pause")
            if self.paused:
                self.pause_msg = self.canvas.create_text(
                    self.width // 2, self.height // 2, text="JOGO PAUSADO",
                    font=("Courier", 26, "bold"), fill="#FFAA00", tags="pause_obj"
                )
            else:
                self.canvas.delete("pause_obj")
                if not self.tick_id:   # o tick parou ao pausar; retoma sem duplicar o loop
                    self.game_tick()

    def start_countdown(self):
        """Contagem 3-2-1-GO antes da largada."""
        self.counting = True
        self.canvas.delete(self.msg_id)
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
        self.fx.popup("GO!", self.width // 2, self.height // 2, "#FFFF00", life=0.8)
        self.game_tick()

    def on_key_press(self, event):
        if event.keysym == "space":
            if not self.running and not self.game_over and not self.counting:
                self.start_countdown()
            elif self.game_over:
                self.init_round()
            return

        if event.keysym.lower() == "p":
            self.toggle_pause()
            return

        if not self.running or self.paused:
            return

        # Mapeamento de teclas unificado usando KEY_LOOKUP do config.py[cite: 2]
        key_lower = event.keysym.lower()
        if key_lower in KEY_LOOKUP:
            pid, nd = KEY_LOOKUP[key_lower]
            if pid in self.riders:
                r = self.riders[pid]
                if not r.is_ai and r.alive:
                    if len(r.queue) < 2:
                        r.queue.append(nd)

    def game_tick(self):
        """Lógica executada a cada passo de simulação do jogo."""
        self.tick_id = None
        if not self.running or self.paused:
            return

        self.tick_ms = max(TICK_MIN_MS, self.tick_ms - TICK_RAMP)

        # Executar IA se o modo treinamento estiver ativo usando ai.decide[cite: 1]
        for pid, r in self.riders.items():
            if r.is_ai and r.alive:
                ai.decide(self, r, level="normal")

        # Processar filas de comandos de direção
        for r in self.riders.values():
            if not r.alive:
                continue
            while r.queue:
                nd = r.queue.pop(0)
                if nd[0] != -r.dir[0] or nd[1] != -r.dir[1]:
                    r.dir = nd
                    self.sound.play("turn")
                    break

        # Atualizar posições dos corredores
        crashed_now = []
        for pid, r in self.riders.items():
            if not r.alive:
                continue
            nxt_cell = (r.cell[0] + r.dir[0], r.cell[1] + r.dir[1])

            if not self.is_free(nxt_cell):
                crashed_now.append(pid)
            else:
                r.cell = nxt_cell
                r.trail.extend([nxt_cell[0] * CELL, nxt_cell[1] * CELL])
                self.occupied_cells.add(nxt_cell)

        # Tratar colisões e atualizar gráficos
        for pid, r in self.riders.items():
            if pid in crashed_now and r.alive:
                r.alive = False
                for it in r.bike:
                    self.canvas.delete(it)
                px, py = r.cell[0] * CELL, r.cell[1] * CELL
                self.fx.explode(px, py, r.color)
                self.fx.ring(px, py, r.color)
                self.fx.shake(8.0)
                self.sound.play("crash")
                # Rastro do derrotado se desfaz e libera o espaço na arena
                cells = {(r.trail[i] // CELL, r.trail[i + 1] // CELL) for i in range(0, len(r.trail), 2)}
                self.fx.fade([(r.line_glow, r.color), (r.line_core, "#FFFFFF")], DISSOLVE_SEC, DISSOLVE_DELAY,
                             on_done=lambda c=cells: self.occupied_cells.difference_update(c))
            elif r.alive:
                self.canvas.coords(r.line_glow, *r.trail)
                self.canvas.coords(r.line_core, *r.trail)
                px, py = r.cell[0] * CELL, r.cell[1] * CELL
                move_bike(self.canvas, r.bike, r.model, px, py, r.dir)

        # Verificar fim de rodada
        survivors = [pid for pid, r in self.riders.items() if r.alive]
        if len(survivors) <= 1 or len(crashed_now) == len(self.riders):
            self.game_over = True
            self.running = False
            self.handle_round_over(survivors)
            return

        self.tick_id = self.root.after(int(self.tick_ms), self.game_tick)

    def start_animation_loop(self):
        """Loop contínuo de renderização gráfica e efeitos visuais a ~60 FPS[cite: 3]."""
        now = time.time()
        dt = now - self.last_frame_time
        self.last_frame_time = now
        self.anim_t += dt

        # Borda e textos de instrução pulsando
        g = 0.5 + 0.5 * math.sin(self.anim_t * 3)
        self.canvas.itemconfig(self.border_id, outline=blend("#0088AA", "#00FFFF", g))
        self.canvas.itemconfig("blink", fill=blend(BG_COLOR, "#00FFFF", 0.35 + 0.65 * g))

        self.fx.update(dt)
        self.after_id = self.root.after(FRAME_MS, self.start_animation_loop)

    def handle_round_over(self, survivors):
        mode = self.controller.game_mode
        winner_text = ""
        winner_color = "#FFFF00"
        match_won = False

        if mode == "team2v2":
            t1_alive = 1 in survivors or 3 in survivors
            t2_alive = 2 in survivors or 4 in survivors
            if t1_alive and not t2_alive:
                self.controller.scores[1] += 1
                winner_text = "EQUIPE 1 VENCEU A RODADA!"
            elif t2_alive and not t1_alive:
                self.controller.scores[2] += 1
                winner_text = "EQUIPE 2 VENCEU A RODADA!"
            else:
                winner_text = "EMPATE TÁTICO!"
        else:
            if len(survivors) == 1:
                winner = survivors[0]
                self.controller.scores[winner] += 1
                winner_text = f"PLAYER {winner} VENCEU A RODADA!"
                winner_color = self.riders[winner].color
            else:
                winner_text = "EMPATE MÚTUO!"

        self.update_hud()
        self.sound.play("round_win")

        target = self.controller.match_target
        champion = None
        for pid, score in self.controller.scores.items():
            if score >= target:
                champion = pid
                match_won = True
                break

        if match_won:
            self.sound.play("match_win")
            self.show_match_victory(champion)
        else:
            cx, cy = self.width // 2, self.height // 2
            t = self.canvas.create_text(cx, cy - 30, text=winner_text, font=("Courier", 26, "bold"), fill=BG_COLOR, tags="game_obj")
            self.fx.text_in(t, winner_color, 0.6)
            self.fx.ring(cx, cy - 30, winner_color, max_r=260, dur=0.7)
            self.canvas.create_text(cx, cy + 25, text="PRESSIONE ESPAÇO PARA A PRÓXIMA RODADA", font=("Courier", 15), fill="#FFFFFF", tags=("game_obj", "blink"))

    def show_match_victory(self, champion):
        self.canvas.delete("game_obj")
        col = self.controller.colors.get(champion, "#00FFFF")

        title = self.canvas.create_text(self.width // 2, self.height // 2 - 80, text=f"CAMPEÃO DA PARTIDA: PLAYER {champion}", font=("Courier", 32, "bold"), fill=BG_COLOR, tags="game_obj")
        self.fx.text_in(title, col, 0.8)
        self.canvas.create_text(self.width // 2, self.height // 2 - 20, text=f"Placar Final: P1({self.controller.scores[1]}) | P2({self.controller.scores[2]}) | P3({self.controller.scores[3]}) | P4({self.controller.scores[4]})", font=("Courier", 16), fill="#FFFFFF", tags="game_obj")

        # Fogos de artifício na cor do campeão
        t = [0.0, 0.0]
        bm = BORDER_MARGIN

        def fireworks(dt):
            t[0] += dt
            t[1] += dt
            if t[1] >= 0.3:
                t[1] = 0.0
                x = random.randint(bm + 80, self.width - bm - 80)
                y = random.randint(bm + 110, self.height - bm - 80)
                c = random.choice((col, col, "#FFFFFF"))
                self.fx.explode(x, y, c, n=35)
                self.fx.ring(x, y, c, max_r=80, dur=0.5)
            return t[0] < 4.0
        self.fx.task(fireworks)

        btn_rematch = tk.Button(self, text="REVANCHE", font=("Courier", 13, "bold"), fg="#030308", bg="#00FFFF",
                                activebackground="#008888", activeforeground="#FFFFFF", width=16, relief="flat", cursor="hand2", command=self.init_round)
        btn_rematch.place(x=self.width // 2 - 180, y=self.height // 2 + 50, width=170, height=40)

        btn_menu = tk.Button(self, text="MENU PRINCIPAL", font=("Courier", 13, "bold"), fg="#FFFFFF", bg="#FF0055",
                             activebackground="#880022", activeforeground="#FFFFFF", width=16, relief="flat", cursor="hand2", command=self.controller.show_menu)
        btn_menu.place(x=self.width // 2 + 10, y=self.height // 2 + 50, width=170, height=40)
        self.victory_buttons = [btn_rematch, btn_menu]


if __name__ == "__main__":
    root = tk.Tk()
    app = LightCycleGame(root)
    root.mainloop()

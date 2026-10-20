import tkinter as tk
from tkinter import font
import time

# Importação dos módulos do projeto
from config import (
    BG_COLOR, GRID_COLOR, CELL, BORDER_MARGIN, MATCH_TARGET, 
    KEY_LOOKUP, FRAME_MS, TICK_START_MS, TICK_MIN_MS, TICK_RAMP
)
from effects import Effects
from sound import SoundManager
import ai

class Rider:
    """Representa uma moto (jogador ou IA) na arena, estruturada para integração com o módulo ai.py[cite: 1]."""
    def __init__(self, pid, cell, direction, color):
        self.pid = pid
        self.cell = cell          # Posicionamento em coordenadas de célula da grade
        self.dir = direction      # Direção atual (dx, dy)
        self.alive = True
        self.queue = []           # Fila de comandos de direção (input buffer)
        self.color = color
        self.trail = [cell[0] * CELL, cell[1] * CELL, cell[0] * CELL, cell[1] * CELL]
        self.line_glow = None
        self.line_core = None
        self.head = None
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
        
        # Configurações padrão de jogo
        self.game_mode = "1v1"  # "1v1", "ffa4", "team2v2", "training"
        self.colors = {
            1: "#00FFFF",  # Azul Ciano[cite: 2]
            2: "#FF0055",  # Vermelho Neon[cite: 2]
            3: "#00FF66",  # Verde Neon
            4: "#FFAA00"   # Laranja Neon
        }
        
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

    def start_game(self, mode, color_config):
        self.sound.play("select")
        self.game_mode = mode
        self.colors.update(color_config)
        self.clear_screen()
        self.current_frame = GameArena(self.root, self)

    def reset_match(self):
        self.sound.play("select")
        self.scores = {1: 0, 2: 0, 3: 0, 4: 0}
        if isinstance(self.current_frame, GameArena):
            self.current_frame.init_round()
            self.current_frame.update_hud()


class MainMenu(tk.Frame):
    """Menu principal com seleção dinâmica de opções de corredores conforme o modo de jogo."""
    def __init__(self, parent, controller):
        super().__init__(parent, bg=BG_COLOR)
        self.controller = controller
        self.pack(fill=tk.BOTH, expand=True)
        
        title_font = font.Font(family="Courier", size=28, weight="bold")
        sub_font = font.Font(family="Courier", size=12)
        btn_font = font.Font(family="Courier", size=13, weight="bold")
        
        lbl_title = tk.Label(self, text="TRON: LIGHT CYCLE ULTIMATE", font=title_font, fg="#00FFFF", bg=BG_COLOR)
        lbl_title.pack(pady=20)
        
        main_container = tk.Frame(self, bg=BG_COLOR)
        main_container.pack(pady=5)
        
        # --- Seleção de Modo de Jogo ---
        mode_frame = tk.LabelFrame(main_container, text=" MODO DE JOGO ", font=sub_font, fg="#00FFFF", bg=BG_COLOR, bd=2, relief="groove")
        mode_frame.grid(row=0, column=0, columnspan=2, padx=15, pady=5, ipadx=15, ipady=5)
        
        self.mode_var = tk.StringVar(value="1v1")
        self.mode_var.trace_add("write", lambda *args: self.update_player_visibility())
        
        modes = [
            ("1v1 Clássico (P1 vs P2)", "1v1"),
            ("Todos contra Todos (4 Jogadores FFA)", "ffa4"),
            ("Batalha em Equipe (2v2 - P1+P3 vs P2+P4)", "team2v2"),
            ("Modo Treinamento (vs IA)", "training")
        ]
        for text, val in modes:
            rb = tk.Radiobutton(mode_frame, text=text, variable=self.mode_var, value=val,
                                font=sub_font, fg="#FFFFFF", bg=BG_COLOR, selectcolor="#111133",
                                activebackground=BG_COLOR, activeforeground="#00FFFF", cursor="hand2")
            rb.pack(anchor="w", padx=15, pady=2)
            
        # --- Seleção de Cores ---
        self.colors_container = tk.Frame(main_container, bg=BG_COLOR)
        self.colors_container.grid(row=1, column=0, columnspan=2, pady=5)
        
        self.color_vars = {}
        self.player_frames = {}
        
        players_config = [
            (1, "PLAYER 1 (WASD)", "#00FFFF", ["#00FFFF", "#0088FF", "#00FFDD"]),
            (2, "PLAYER 2 (SETAS)", "#FF0055", ["#FF0055", "#FF0000", "#FF44AA"]),
            (3, "PLAYER 3 (UHJK)", "#00FF66", ["#00FF66", "#88FF00", "#00FFBB"]),
            (4, "PLAYER 4 (NUMPAD)", "#FFAA00", ["#FFAA00", "#FFCC00", "#FF6600"])
        ]
        
        for p_id, p_label, default_col, col_list in players_config:
            p_frame = tk.LabelFrame(self.colors_container, text=f" {p_label} ", font=("Courier", 10, "bold"), fg=default_col, bg=BG_COLOR, bd=1, relief="groove")
            p_frame.pack(side=tk.LEFT, padx=6, ipadx=6, ipady=2)
            
            self.player_frames[p_id] = p_frame
            self.color_vars[p_id] = tk.StringVar(value=default_col)
            for col in col_list:
                rb = tk.Radiobutton(p_frame, text=col, variable=self.color_vars[p_id], value=col,
                                    font=("Courier", 9), fg=col, bg=BG_COLOR, selectcolor="#111122",
                                    activebackground=BG_COLOR, activeforeground=col, cursor="hand2")
                rb.pack(anchor="w", pady=1)

        # Atualizar visibilidade inicial de P3 e P4
        self.update_player_visibility()

        # Botões de Ação
        btn_frame = tk.Frame(self, bg=BG_COLOR)
        btn_frame.pack(pady=15)
        
        btn_start = tk.Button(btn_frame, text="INICIAR PARTIDA", font=btn_font, fg="#030308", bg="#00FFFF",
                              activebackground="#008888", activeforeground="#FFFFFF", width=18, relief="flat",
                              cursor="hand2", command=self.on_start)
        btn_start.pack(side=tk.LEFT, padx=15)
        
        btn_exit = tk.Button(btn_frame, text="SAIR", font=btn_font, fg="#FFFFFF", bg="#FF0055",
                             activebackground="#880022", activeforeground="#FFFFFF", width=12, relief="flat",
                             cursor="hand2", command=controller.quit_game)
        btn_exit.pack(side=tk.LEFT, padx=15)

    def update_player_visibility(self):
        """Mostra ou oculta os seletores de P3 e P4 com base no modo selecionado."""
        mode = self.mode_var.get()
        if mode in ["1v1", "training"]:
            self.player_frames[3].pack_forget()
            self.player_frames[4].pack_forget()
        else:
            # Reorganiza a exibição para incluir P3 e P4
            self.player_frames[3].pack(side=tk.LEFT, padx=6, ipadx=6, ipady=2)
            self.player_frames[4].pack(side=tk.LEFT, padx=6, ipadx=6, ipady=2)

    def on_start(self):
        mode = self.mode_var.get()
        color_config = {pid: var.get() for pid, var in self.color_vars.items()}
        self.controller.start_game(mode, color_config)


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
        self.canvas.create_rectangle(bm, bm + 30, self.width - bm, self.height - bm, outline="#00FFFF", width=4, tags="arena_static")
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
        self.riders = {}
        self.occupied_cells = set()
        self.tick_ms = TICK_START_MS
        self.after_id = None
        self.last_frame_time = time.time()
        
        # Vincular teclas globais[cite: 2]
        self.winfo_toplevel().bind("<KeyPress>", self.on_key_press)
        
        self.init_round()
        self.start_animation_loop()

    def destroy_arena(self):
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None

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
        self.canvas.itemconfig(self.hud_text, text=txt)

    def is_free(self, cell):
        """Método exigido pelo módulo ai.py para verificar células livres[cite: 1]."""
        cx, cy = cell
        min_cx = BORDER_MARGIN // CELL
        max_cx = (self.width - BORDER_MARGIN) // CELL
        min_cy = (BORDER_MARGIN + 30) // CELL
        max_cy = (self.height - BORDER_MARGIN) // CELL
        
        if not (min_cx <= cx <= max_cx and min_cy <= cy <= max_cy):
            return False
        return cell not in self.occupied_cells

    def init_round(self):
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None
            
        self.canvas.delete("game_obj")
        self.fx.reset()
        self.game_over = False
        self.paused = False
        self.running = False
        self.tick_ms = TICK_START_MS
        self.occupied_cells = set()
        self.update_hud()
        
        mode = self.controller.game_mode
        active_ids = [1, 2] if mode in ["1v1", "training"] else [1, 2, 3, 4]
        
        # Criar obstáculos centrais na arena primeiro
        self.create_obstacles()
        
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
            
            px, py = cell[0] * CELL, cell[1] * CELL
            glow = self.canvas.create_line(px, py, px, py, fill=color, width=5, capstyle=tk.ROUND, tags="game_obj")
            core = self.canvas.create_line(px, py, px, py, fill="#FFFFFF", width=2, capstyle=tk.ROUND, tags="game_obj")
            head = self.canvas.create_oval(px-3, py-3, px+3, py+3, fill="#FFFFFF", outline=color, width=2, tags="game_obj")
            
            rider = Rider(pid, cell, d, color)
            rider.line_glow = glow
            rider.line_core = core
            rider.head = head
            if mode == "training" and pid == 2:
                rider.is_ai = True
            
            self.riders[pid] = rider
            self.occupied_cells.add(cell)
            
        self.msg_id = self.canvas.create_text(
            self.width // 2, self.height // 2,
            text="PRESSIONE ESPAÇO PARA INICIAR A RODADA",
            font=("Courier", 20, "bold"), fill="#00FFFF", tags="game_obj"
        )

    def create_obstacles(self):
        cx, cy = self.width // 2, self.height // 2
        obs = [
            (cx - 120, cy - 20, cx + 120, cy + 20),
            (cx - 20, cy - 120, cx + 20, cy + 120)
        ]
        for x1, y1, x2, y2 in obs:
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

    def on_key_press(self, event):
        if event.keysym == "space":
            if not self.running and not self.game_over:
                self.canvas.delete(self.msg_id)
                self.running = True
                self.sound.play("go")
                self.game_tick()
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
                self.canvas.delete(r.head)
                px, py = r.cell[0] * CELL, r.cell[1] * CELL
                self.fx.explode(px, py, r.color)
                self.fx.ring(px, py, r.color)
                self.fx.shake(8.0)
                self.sound.play("crash")
            elif r.alive:
                self.canvas.coords(r.line_glow, *r.trail)
                self.canvas.coords(r.line_core, *r.trail)
                px, py = r.cell[0] * CELL, r.cell[1] * CELL
                self.canvas.coords(r.head, px-3, py-3, px+3, py+3)
                
        # Verificar fim de rodada
        survivors = [pid for pid, r in self.riders.items() if r.alive]
        if len(survivors) <= 1 or len(crashed_now) == len(self.riders):
            self.game_over = True
            self.running = False
            self.handle_round_over(survivors)
            return
            
        self.root.after(int(self.tick_ms), self.game_tick)

    def start_animation_loop(self):
        """Loop contínuo de renderização gráfica e efeitos visuais a ~60 FPS[cite: 3]."""
        now = time.time()
        dt = now - self.last_frame_time
        self.last_frame_time = now
        
        self.fx.update(dt)
        self.after_id = self.root.after(FRAME_MS, self.start_animation_loop)

    def handle_round_over(self, survivors):
        mode = self.controller.game_mode
        winner_text = ""
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
            self.canvas.create_text(self.width // 2, self.height // 2 - 30, text=winner_text, font=("Courier", 26, "bold"), fill="#FFFF00", tags="game_obj")
            self.canvas.create_text(self.width // 2, self.height // 2 + 25, text="PRESSIONE ESPAÇO PARA A PRÓXIMA RODADA", font=("Courier", 15), fill="#FFFFFF", tags="game_obj")

    def show_match_victory(self, champion):
        self.canvas.delete("game_obj")
        col = self.controller.colors.get(champion, "#00FFFF")
        
        self.canvas.create_text(self.width // 2, self.height // 2 - 80, text=f"CAMPEÃO DA PARTIDA: PLAYER {champion}", font=("Courier", 32, "bold"), fill=col, tags="game_obj")
        self.canvas.create_text(self.width // 2, self.height // 2 - 20, text=f"Placar Final: P1({self.controller.scores[1]}) | P2({self.controller.scores[2]}) | P3({self.controller.scores[3]}) | P4({self.controller.scores[4]})", font=("Courier", 16), fill="#FFFFFF", tags="game_obj")
        
        btn_rematch = tk.Button(self, text="REVANCHE", font=("Courier", 13, "bold"), fg="#030308", bg="#00FFFF",
                                activebackground="#008888", activeforeground="#FFFFFF", width=16, relief="flat", cursor="hand2", command=self.init_round)
        btn_rematch.place(x=self.width // 2 - 180, y=self.height // 2 + 50, width=170, height=40)
        
        btn_menu = tk.Button(self, text="MENU PRINCIPAL", font=("Courier", 13, "bold"), fg="#FFFFFF", bg="#FF0055",
                             activebackground="#880022", activeforeground="#FFFFFF", width=16, relief="flat", cursor="hand2", command=self.controller.show_menu)
        btn_menu.place(x=self.width // 2 + 10, y=self.height // 2 + 50, width=170, height=40)


if __name__ == "__main__":
    root = tk.Tk()
    app = LightCycleGame(root)
    root.mainloop()
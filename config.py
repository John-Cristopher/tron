"""Constantes, atalhos de teclado e utilidades de cor compartilhadas."""

BG_COLOR = "#030308"
GRID_COLOR = "#0a0a1a"
GRID_PULSE = "#14143a"
CYAN = "#00FFFF"
RED = "#FF0055"
NEON = ["#00FFFF", "#FF0055", "#00FF66", "#FFAA00", "#FF44AA", "#8844FF"]

CELL = 8                 # tamanho de cada célula da arena (px)
BORDER_MARGIN = 35
TOP_BAR = 60
MATCH_TARGET = 5

FRAME_MS = 15            # renderização (~60 FPS)
TICK_START_MS = 30       # intervalo da lógica no início da rodada
TICK_MIN_MS = 17         # limite de velocidade
TICK_RAMP = 0.3          # ms a menos por segundo (o jogo vai acelerando)
TURN_QUEUE_MAX = 2       # curvas "guardadas" por jogador (input buffer)
DISSOLVE_DELAY = 0.5     # tempo até o rastro do jogador morto começar a sumir
DISSOLVE_SEC = 0.9

# Paletas por jogador: (nome exibido no menu, cor)
PALETTES = {
    1: [("CIANO", "#00FFFF"), ("AZUL", "#0088FF"), ("TURQUESA", "#00FFDD"), ("GELO", "#C8F0FF")],
    2: [("VERMELHO", "#FF0055"), ("CARMIM", "#FF2020"), ("ROSA", "#FF44AA"), ("MAGENTA", "#FF00FF")],
    3: [("VERDE", "#00FF66"), ("LIMA", "#88FF00"), ("MENTA", "#00FFBB"), ("JADE", "#00CC77")],
    4: [("LARANJA", "#FFAA00"), ("OURO", "#FFDD00"), ("FOGO", "#FF6600"), ("VIOLETA", "#AA55FF")],
}

# Mapas: (nome, obstáculos (x1, y1, x2, y2) em frações da área interna da arena).
# Mantêm livre a saída dos spawns: linha do meio (P1/P2) e coluna do meio (P3/P4).
MAPS = [
    ("CRUZ", [(0.435, 0.48, 0.565, 0.52), (0.489, 0.38, 0.511, 0.62)]),
    ("PILARES", [(x, y, x + 0.05, y + 0.09) for x in (0.2, 0.75) for y in (0.2, 0.71)]
                + [(0.475, 0.455, 0.525, 0.545)]),
    ("CORREDORES", [(0.15, 0.28, 0.44, 0.31), (0.56, 0.28, 0.85, 0.31),
                    (0.15, 0.69, 0.44, 0.72), (0.56, 0.69, 0.85, 0.72)]),
    ("FORTALEZA", [(0.35, 0.30, 0.46, 0.32), (0.54, 0.30, 0.65, 0.32),      # muro de cima
                   (0.35, 0.68, 0.46, 0.70), (0.54, 0.68, 0.65, 0.70),      # muro de baixo
                   (0.35, 0.30, 0.362, 0.43), (0.35, 0.57, 0.362, 0.70),    # muro esquerdo
                   (0.638, 0.30, 0.65, 0.43), (0.638, 0.57, 0.65, 0.70)]),  # muro direito
]
RANDOM_MAP = len(MAPS)   # índice extra no seletor = sorteia um mapa a cada rodada

KEYMAP = {
    1: {"w": (0, -1), "s": (0, 1), "a": (-1, 0), "d": (1, 0)},
    2: {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)},
    3: {"u": (0, -1), "j": (0, 1), "h": (-1, 0), "k": (1, 0)},
    4: {"kp_8": (0, -1), "kp_2": (0, 1), "kp_4": (-1, 0), "kp_6": (1, 0),
        "kp_up": (0, -1), "kp_down": (0, 1), "kp_left": (-1, 0), "kp_right": (1, 0),
        "8": (0, -1), "2": (0, 1), "4": (-1, 0), "6": (1, 0)},
}
KEY_LOOKUP = {k: (pid, d) for pid, m in KEYMAP.items() for k, d in m.items()}


def _rgb(c):
    return int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)


def blend(a, b, t):
    """Mistura duas cores hex: t=0 -> a, t=1 -> b (usado para simular brilho/fade)."""
    t = max(0.0, min(1.0, t))
    ra, ga, ba = _rgb(a)
    rb, gb, bb = _rgb(b)
    return "#%02x%02x%02x" % (int(ra + (rb - ra) * t), int(ga + (gb - ga) * t), int(ba + (bb - ba) * t))
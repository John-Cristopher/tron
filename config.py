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
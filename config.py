"""Constantes, atalhos de teclado e utilidades de cor compartilhadas."""

from theme import BACKGROUND as BG_COLOR, GRID as GRID_COLOR, GRID_BRIGHT as GRID_PULSE
from theme import CYAN, RED, GREEN, ORANGE, PURPLE, CORE, PLAYER_PALETTE, blend

NEON = [CYAN, RED, GREEN, ORANGE, CORE, PURPLE]

CELL = 8  # tamanho de cada célula da arena (px)
BORDER_MARGIN = 35
MATCH_TARGET = 5

FRAME_MS = 15  # renderização (~60 FPS)
TICK_START_MS = 30  # intervalo da lógica no início da rodada
TICK_MIN_MS = 25  # limite de velocidade
TICK_RAMP = 0.3  # ms a menos por segundo (o jogo vai acelerando)
TURN_QUEUE_MAX = 2  # curvas "guardadas" por jogador (input buffer)
DISSOLVE_DELAY = 0.5  # tempo até o rastro do jogador morto começar a sumir
DISSOLVE_SEC = 0.9
ROUND_RESTART_COOLDOWN_MS = 2000

# Modificadores (ativáveis na configuração da partida)
TRAIL_FADE_OPTIONS = (3.0, 5.0, 8.0)
TRAIL_FADE_SEC = 8.0  # padrão do rastro efêmero; a pausa não conta
LIGHTNING_TICK_FACTOR = 0.7
SHRINK_START_SEC = 8.0
SHRINK_STEP_SEC = 0.5

PORTAL_COLOR = "#C060FF"  # cor das aberturas na parede (mapas com travessia estilo Pac-Man)

# Menus de seleção (modo de jogo e configuração): o fundo da plateia fica desfocado e mais escuro.
MENU_BLUR_RADIUS = 6.0  # força do desfoque, em px numa tela de 1920 de largura (0 = sem desfoque; precisa do Pillow)
MENU_DIM = 0.35  # quanto escurecer o fundo: 0 = nada, 1 = preto
MENU_BLUR_SEC = 0.45  # duração da transição ao entrar/sair dos menus de seleção

# Paleta universal: qualquer jogador pode escolher qualquer cor, independente do controle.
MAX_PLAYERS = 4
COLOR_PALETTE = list(PLAYER_PALETTE)
PALETTES = {pid: COLOR_PALETTE for pid in range(1, MAX_PLAYERS + 1)}

# Mapas: (nome, obstáculos (x1, y1, x2, y2) em frações da área interna da arena).
# Mantêm livre a saída dos spawns: linha do meio (P1/P2) e coluna do meio (P3/P4).
MAPS = [
    ("CRUZ", [(0.435, 0.48, 0.565, 0.52), (0.489, 0.38, 0.511, 0.62)]),
    (
        "PILARES",
        [(x, y, x + 0.05, y + 0.09) for x in (0.2, 0.75) for y in (0.2, 0.71)]
        + [(0.475, 0.455, 0.525, 0.545)],
    ),
    (
        "CORREDORES",
        [
            (0.15, 0.28, 0.44, 0.31),
            (0.56, 0.28, 0.85, 0.31),
            (0.15, 0.69, 0.44, 0.72),
            (0.56, 0.69, 0.85, 0.72),
        ],
    ),
    (
        "FORTALEZA",
        [
            (0.35, 0.30, 0.46, 0.32),
            (0.54, 0.30, 0.65, 0.32),  # muro de cima
            (0.35, 0.68, 0.46, 0.70),
            (0.54, 0.68, 0.65, 0.70),  # muro de baixo
            (0.35, 0.30, 0.362, 0.43),
            (0.35, 0.57, 0.362, 0.70),  # muro esquerdo
            (0.638, 0.30, 0.65, 0.43),
            (0.638, 0.57, 0.65, 0.70),
        ],
    ),  # muro direito
    # --- mapas extras (limpos, para não atrapalhar o jogo) ---
    # Um 3º item opcional ativa a travessia estilo Pac-Man: a parede fica aberta nas faixas indicadas
    # e quem atravessa reaparece do lado oposto.
    #   "wrap_h": [(y1, y2)]  -> abertura nas paredes ESQUERDA e DIREITA (faixa de altura, em fração)
    #   "wrap_v": [(x1, x2)]  -> abertura nas paredes de CIMA e de BAIXO (faixa de largura, em fração)
    ("TÚNEL", [(0.45, 0.45, 0.55, 0.55)], {"wrap_h": [(0.42, 0.58)]}),
    (
        "TOROIDE",
        [(x, y, x + 0.04, y + 0.08) for x in (0.22, 0.74) for y in (0.26, 0.66)],
        {"wrap_h": [(0.42, 0.58)], "wrap_v": [(0.44, 0.56)]},
    ),
    (
        "COLUNAS",
        [
            (0.30, 0.18, 0.315, 0.42),
            (0.30, 0.58, 0.315, 0.82),
            (0.685, 0.18, 0.70, 0.42),
            (0.685, 0.58, 0.70, 0.82),
        ],
    ),
    (
        "CATAVENTO",
        [
            (0.20, 0.25, 0.42, 0.28),
            (0.72, 0.22, 0.75, 0.44),
            (0.58, 0.72, 0.80, 0.75),
            (0.25, 0.56, 0.28, 0.78),
        ],
    ),
    ("ABERTO", [(0.47, 0.44, 0.53, 0.56)]),
]


def map_options(m):
    """Opções extras de um mapa (o 3º item da tupla), ou {} se não houver."""
    return m[2] if len(m) > 2 else {}


AI_LEVELS = [
    ("easy", "FÁCIL"),
    ("normal", "NORMAL"),
    ("hard", "DIFÍCIL"),
    ("extreme", "EXTREMO"),
]  # chaves de ai.LEVELS

RINZLER_BOOST_COOLDOWN_SEC = 8.0
RINZLER_BOOST_DURATION_SEC = 1.4
RINZLER_BOOST_INTERVAL_SEC = 0.28

RANDOM_MAP = len(MAPS)  # índice extra no seletor = sorteia um mapa a cada rodada

# Esquemas de teclado, na ordem em que viram jogadores. Os controles conectados ocupam os
# primeiros jogadores e os teclados ficam com o resto (ex.: 1 controle -> P1; WASD -> P2...).
KEY_LAYOUTS = [
    ("W A S D", {"w": (0, -1), "s": (0, 1), "a": (-1, 0), "d": (1, 0)}),
    ("SETAS", {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}),
    ("U H J K", {"u": (0, -1), "j": (0, 1), "h": (-1, 0), "k": (1, 0)}),
    (
        "NUMPAD",
        {
            "kp_8": (0, -1),
            "kp_2": (0, 1),
            "kp_4": (-1, 0),
            "kp_6": (1, 0),
            "kp_up": (0, -1),
            "kp_down": (0, 1),
            "kp_left": (-1, 0),
            "kp_right": (1, 0),
            "8": (0, -1),
            "2": (0, 1),
            "4": (-1, 0),
            "6": (1, 0),
        },
    ),
]
# tecla -> (índice do esquema de teclado, direção)
KEY_LOOKUP = {k: (i, d) for i, (_, m) in enumerate(KEY_LAYOUTS) for k, d in m.items()}



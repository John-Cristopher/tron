"""Efeitos visuais: partículas, ondas de choque, tremor de tela, fades e textos animados."""
import math
import random

from config import BG_COLOR, blend


def _sym(half):
    """Espelha meio contorno (do nariz até a cauda, lado y<0) para formar o polígono inteiro."""
    return half + [(x, -y) for x, y in reversed(half) if y]


# Modelos de moto vistos de cima: (nome, carenagem, cockpit), apontando para +x com a ponta do rastro na origem
BIKES = [
    ("CLASSICA", _sym([(3, 0), (0, -3), (-5, -4), (-17, -4), (-21, -2), (-21, 0)]),
                 _sym([(-3, 0), (-6, -2), (-12, -2), (-12, 0)])),
    ("INTERCEPTOR", _sym([(6, 0), (-4, -2.5), (-11, -6), (-20, -7), (-16, -3), (-21, 0)]),
                    _sym([(-1, 0), (-5, -1.5), (-11, -1.5), (-11, 0)])),
    ("TITAN", _sym([(2, 0), (1, -4), (-3, -6), (-19, -6), (-23, -4), (-23, 0)]),
              _sym([(-4, 0), (-6, -3), (-14, -3), (-16, 0)])),
]


def bike_points(shape, x, y, d, scale=1.0):
    """Gira o contorno para a direção d=(dx, dy) e posiciona em (x, y)."""
    dx, dy = d
    pts = []
    for sx, sy in shape:
        sx, sy = sx * scale, sy * scale
        pts += [x + sx * dx - sy * dy, y + sx * dy + sy * dx]
    return pts


def draw_bike(cv, x, y, d, color, model=0, scale=1.0, tags=()):
    _, body, canopy = BIKES[model]
    b = cv.create_polygon(bike_points(body, x, y, d, scale), fill=blend(color, BG_COLOR, 0.6), outline=color,
                          width=max(1, round(scale * 1.5)), joinstyle="round", tags=tags)
    c = cv.create_polygon(bike_points(canopy, x, y, d, scale), fill=blend(color, "#FFFFFF", 0.65), outline="", tags=tags)
    return [b, c]


def move_bike(cv, items, model, x, y, d, scale=1.0):
    for it, shape in zip(items, BIKES[model][1:]):
        cv.coords(it, *bike_points(shape, x, y, d, scale))


class Effects:
    def __init__(self, canvas):
        self.cv = canvas
        canvas.configure(confine=False)   # permite "empurrar" a visão do canvas (screen shake)
        canvas.scan_mark(0, 0)
        self.reset()

    def reset(self):
        """Chamado a cada rodada (os itens já foram apagados do canvas)."""
        self.particles, self.tasks, self.shake_amt = [], [], 0.0
        self.cv.scan_dragto(0, 0, gain=1)

    # ---- criação de efeitos
    def task(self, fn):
        """fn(dt) roda a cada frame; retorne False para encerrar."""
        self.tasks.append(fn)

    def after(self, secs, fn):
        t = [0.0]

        def run(dt):
            t[0] += dt
            if t[0] >= secs:
                fn()
                return False
        self.tasks.append(run)

    def shake(self, amount):
        self.shake_amt = max(self.shake_amt, amount)

    def explode(self, x, y, color, n=55):
        for _ in range(n):
            ang, spd = random.uniform(0, math.tau), random.uniform(80, 460)
            col = random.choice((color, color, "#FFFFFF"))
            life = random.uniform(0.5, 1.1)
            item = self.cv.create_oval(x, y, x, y, fill=col, outline="", tags="game_obj")
            self.particles.append({"id": item, "x": x, "y": y, "color": col, "life": life, "max": life,
                                   "vx": math.cos(ang) * spd, "vy": math.sin(ang) * spd})

    def ring(self, x, y, color, max_r=140, dur=0.55):
        item = self.cv.create_oval(x, y, x, y, outline=color, width=4, tags="game_obj")
        t = [0.0]

        def run(dt):
            t[0] += dt
            k = t[0] / dur
            if k >= 1:
                self.cv.delete(item)
                return False
            r = max_r * (1 - (1 - k) ** 2)
            self.cv.coords(item, x - r, y - r, x + r, y + r)
            self.cv.itemconfig(item, outline=blend(color, BG_COLOR, k), width=max(1, int(5 * (1 - k))))
        self.tasks.append(run)

    def popup(self, text, x, y, color, life=0.9, size=110, shrink=0.55):
        """Texto grande que encolhe e some (contagem regressiva, GO!)."""
        item = self.cv.create_text(x, y, text=text, fill=color, font=("Courier", size, "bold"), tags="game_obj")
        t = [0.0]

        def run(dt):
            t[0] += dt
            k = t[0] / life
            if k >= 1:
                self.cv.delete(item)
                return False
            self.cv.itemconfig(item, fill=blend(color, BG_COLOR, k * k),
                               font=("Courier", int(size * (1 - shrink * k)), "bold"))
        self.tasks.append(run)

    def text_in(self, item, color, dur=0.5):
        """Fade-in de um texto já criado."""
        t = [0.0]

        def run(dt):
            t[0] += dt
            k = min(1.0, t[0] / dur)
            self.cv.itemconfig(item, fill=blend(BG_COLOR, color, k))
            if k >= 1:
                return False
        self.tasks.append(run)

    def fade(self, pairs, dur, delay=0.0, on_done=None):
        """Dissolve itens [(id, cor)] até o fundo e depois os apaga."""
        t = [-delay]

        def run(dt):
            t[0] += dt
            if t[0] < 0:
                return
            k = min(1.0, t[0] / dur)
            for it, c in pairs:
                self.cv.itemconfig(it, fill=blend(c, BG_COLOR, k))
            if k >= 1:
                for it, _ in pairs:
                    self.cv.delete(it)
                if on_done:
                    on_done()
                return False
        self.tasks.append(run)

    # ---- atualização por frame
    def update(self, dt):
        f = 0.92 ** (dt * 60)
        alive = []
        for p in self.particles:
            p["life"] -= dt
            if p["life"] <= 0:
                self.cv.delete(p["id"])
                continue
            p["vx"] *= f
            p["vy"] *= f
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            k = p["life"] / p["max"]
            r = 1 + 3 * k
            self.cv.coords(p["id"], p["x"] - r, p["y"] - r, p["x"] + r, p["y"] + r)
            self.cv.itemconfig(p["id"], fill=blend(p["color"], BG_COLOR, 1 - k))
            alive.append(p)
        self.particles = alive

        self.tasks = [t for t in self.tasks if t(dt) is not False]

        if self.shake_amt > 0.4:
            a = self.shake_amt
            self.cv.scan_dragto(int(random.uniform(-a, a)), int(random.uniform(-a, a)), gain=1)
            self.shake_amt *= 0.86 ** (dt * 60)
        elif self.shake_amt > 0:
            self.shake_amt = 0.0
            self.cv.scan_dragto(0, 0, gain=1)
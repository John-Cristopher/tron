"""
derez.py - Animação de "deresolução" estilo Tron: Legacy para Tkinter Canvas.

Por que o derez antigo parecia líquido?
  Curvas suaves + partículas redondas + um bolo roxo no centro leem como tinta.
  O derez do filme é o oposto: fragmentos ANGULARES (cubos e cacos) com faces
  escuras e arestas claras, tamanhos hierárquicos (poucos grandes, muitos
  pequenos), uma varredura de luz que "desmonta" o corpo e um anel de luz no chão.

Camadas desta animação (tudo com itens reaproveitados, sem alocar por frame):
  1. scan   - linha de luz varre o veículo do nariz à cauda
  2. cubes  - o corpo vira uma grade de cubos que se soltam em cascata
  3. flash  - clarão curto
  4. shards - poucos cacos longos e rápidos
  5. sparks - riscos de luz curtos, alinhados à velocidade
  6. rings  - onda de choque fina (e um segundo anel mais tardio)

Uso:
    from derez import Derez
    derez = Derez(canvas, bg="#02060A")

    # na morte de uma moto (esconda o sprite dela nesse momento):
    derez.spawn(x, y, color="#B79CFF", heading=angulo_rad, length=34, width=12)

    # a cada frame do jogo:
    derez.update(dt)           # dt em segundos

Para o modo Top Gear (vista traseira), passe gravity=900 e heading=-pi/2
(os cacos sobem e caem) e use `power` maior para o Rinzler.
"""

import math
import random

from theme import blend as mix


def _ease_out(t):
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    return 1 - (1 - t) ** 3


class _P:
    """Partícula/elemento de efeito. Um objeto por item do pool."""

    __slots__ = (
        "kind",
        "item",
        "active",
        "x",
        "y",
        "vx",
        "vy",
        "rot",
        "vrot",
        "size",
        "t",
        "delay",
        "life",
        "color",
        "hot",
        "gravity",
        "drag",
        "last",
        "a",
        "b",
        "c",
        "d",
    )

    def __init__(self, kind, item):
        self.kind, self.item, self.active = kind, item, False
        self.last = None


class Derez:
    def __init__(
        self,
        canvas,
        bg="#02060A",
        cubes=256,
        shards=36,
        sparks=90,
        rings=4,
        flashes=3,
        scans=3,
        tag="derez",
    ):
        self.c = canvas
        self.bg = bg
        self.tag = tag
        self.pools = {}
        mk = canvas.create_polygon
        hidden = dict(state="hidden", tags=tag)

        self.pools["cube"] = [
            _P(
                "cube",
                mk(0, 0, 0, 0, 0, 0, 0, 0, fill=bg, outline=bg, width=1, **hidden),
            )
            for _ in range(cubes)
        ]
        self.pools["shard"] = [
            _P("shard", mk(0, 0, 0, 0, 0, 0, fill=bg, outline=bg, width=1, **hidden))
            for _ in range(shards)
        ]
        self.pools["spark"] = [
            _P(
                "spark",
                canvas.create_line(
                    0, 0, 0, 0, fill=bg, width=2, capstyle="butt", **hidden
                ),
            )
            for _ in range(sparks)
        ]
        self.pools["ring"] = [
            _P("ring", canvas.create_oval(0, 0, 0, 0, outline=bg, width=2, **hidden))
            for _ in range(rings)
        ]
        self.pools["flash"] = [
            _P("flash", canvas.create_oval(0, 0, 0, 0, fill=bg, outline="", **hidden))
            for _ in range(flashes)
        ]
        self.pools["scan"] = [
            _P("scan", canvas.create_line(0, 0, 0, 0, fill=bg, width=3, **hidden))
            for _ in range(scans)
        ]
        self._all = [p for pool in self.pools.values() for p in pool]

    # ------------------------------------------------------------ API
    @property
    def busy(self):
        return any(p.active for p in self._all)

    def clear(self):
        for p in self._all:
            self._kill(p)

    def spawn(
        self,
        x,
        y,
        color="#B79CFF",
        heading=0.0,
        length=34.0,
        width=12.0,
        power=1.0,
        gravity=0.0,
        hot="#FFFFFF",
        wall=None,
    ):
        """Fragmentos seguem heading em um cone frontal; os pulsos são radiais."""
        c = self.c
        if wall is not None:
            inset = max(14.0, width)
            if wall == "left":
                x += inset
                fx, fy = 1.0, -1.0
            elif wall == "right":
                x -= inset
                fx, fy = -1.0, -1.0
            elif wall == "top":
                y += inset
                fx, fy = (-1.0 if math.cos(heading) < 0 else 1.0), 1.0
            elif wall == "bottom":
                y -= inset
                fx, fy = (-1.0 if math.cos(heading) < 0 else 1.0), -1.0
            else:
                raise ValueError(f"Unknown wall side: {wall}")
            heading = math.atan2(fy, fx)
        fx, fy = math.cos(heading), math.sin(heading)
        px, py = -fy, fx
        rnd = random.random
        available = {kind: (p for p in pool if not p.active)
                     for kind, pool in self.pools.items()}

        def take(kind):
            p = next(available[kind], None)
            if p is not None:
                p.active = True
                p.t = 0.0
                p.last = None
                p.color, p.hot, p.gravity = color, hot, gravity
            return p

        def velocity(speed, spread):
            forward = speed * power * 0.45
            lateral = (rnd() * 2 - 1) * forward * spread
            return fx * forward + px * lateral, fy * forward + py * lateral

        # 1) scan: varre do nariz (+) até a cauda (-)
        p = take("scan")
        if p:
            p.x, p.y, p.a, p.b, p.c, p.d = x, y, fx, fy, length, width
            p.delay, p.life = 0.0, 0.24

        # 2) cubos: grade cobrindo o corpo, soltos em cascata nariz -> cauda
        # Limita a grade do sprite grande para reservar voxels da ejeção.
        cs = max(5.0, math.sqrt(length * width / 96))
        cols = max(4, int(length / cs))
        rows = max(2, int(width / cs))
        for i in range(cols):
            for j in range(rows):
                u = (i + 0.5) / cols - 0.5  # -0.5 (cauda) .. +0.5 (nariz)
                v = (j + 0.5) / rows - 0.5
                if (u * 2) ** 4 + (v * 2) ** 2 > 1.0:  # recorta cantos (silhueta)
                    continue
                p = take("cube")
                if not p:
                    break
                p.x = x + fx * u * length + px * v * width
                p.y = y + fy * u * length + py * v * width
                p.vx, p.vy = velocity(210 + rnd() * 310, .60)
                p.rot = rnd() * math.tau
                p.vrot = (rnd() - 0.5) * 12
                p.size = (cs * 0.5) * (0.8 + rnd() * 0.5)
                p.delay = (0.5 - u) * 0.24 + rnd() * 0.04  # cascata
                p.life = 0.7 + rnd() * 0.9
                p.drag = 2.0
        # Uma nuvem densa de cubinhos e poucos fragmentos grandes acompanha
        # o impulso da moto, sem emitir partículas na direção contrária.
        for _ in range(96):
            p = take("cube")
            if not p:
                break
            u, v = rnd() - .5, rnd() - .5
            v *= math.sqrt(max(0, 1 - (u * 2)**4))
            p.x = x + fx * u * length + px * v * width
            p.y = y + fy * u * length + py * v * width
            p.vx, p.vy = velocity(200 + rnd() * 260, .72)
            p.rot, p.vrot = rnd() * math.tau, (rnd() - 0.5) * 18
            p.size = 3.4 + rnd() * 2.4 if rnd() < .10 else 1.2 + rnd() * 1.6
            p.delay = .04 + (.5 - u) * .24 + rnd() * .03
            p.life, p.drag = .65 + rnd() * .85, 1.8

        # 3) flash
        p = take("flash")
        if p:
            p.x, p.y, p.size = x, y, length * 0.9
            p.delay, p.life = 0.10, 0.14

        # 4) cacos longos e rápidos
        for _ in range(14):
            p = take("shard")
            if not p:
                break
            p.x, p.y = x, y
            p.vx, p.vy = velocity(280 + rnd() * 280, .48)
            p.rot, p.vrot = rnd() * math.tau, (rnd() - 0.5) * 10
            p.size = 7 + rnd() * 14
            p.delay, p.life, p.drag = 0.12 + rnd() * 0.12, 0.5 + rnd() * 0.6, 2.0

        # 5) faíscas (riscos curtos alinhados à velocidade)
        for _ in range(48):
            p = take("spark")
            if not p:
                break
            p.x, p.y = x, y
            p.vx, p.vy = velocity(300 + rnd() * 260, .65)
            p.size = .025 + rnd() * .035  # fator de comprimento (s)
            p.delay, p.life, p.drag = 0.10 + rnd() * 0.22, 0.2 + rnd() * 0.4, 3.0

        # 6) anéis de onda de choque
        p = take("ring")
        if p:
            p.x, p.y, p.size = x, y, length * 2.4
            p.delay, p.life = 0.12, 0.70
            p.a = 3
            p.b = .24 if gravity else 1.0
        p = take("ring")
        if p:
            p.x, p.y, p.size = x, y, length * 1.5
            p.delay, p.life = 0.30, 0.55
            p.a = 1
            p.b = .24 if gravity else 1.0

        c.tag_raise(self.tag)

    def update(self, dt):
        # Subpassos preservam o tempo real quando o Canvas perde um quadro.
        remaining = max(0.0, dt)
        while remaining > .05:
            self._update_step(.05)
            remaining -= .05
        self._update_step(remaining)

    def _update_step(self, dt):
        for p in self._all:
            if not p.active:
                continue
            p.t += dt
            k = p.kind
            if k == "scan":
                self._upd_scan(p)
                continue
            if p.t < p.delay:
                if k == "cube":  # ainda "faz parte" do corpo
                    self._draw_cube(p, 0.0, hold=True)
                continue
            q = (p.t - p.delay) / p.life
            if q >= 1.0:
                self._kill(p)
                continue
            if k == "ring":
                self._upd_ring(p, q)
            elif k == "flash":
                self._upd_flash(p, q)
            else:
                drag = max(0.0, 1.0 - p.drag * dt)
                p.vx *= drag
                p.vy *= drag
                p.vy += p.gravity * dt
                p.x += p.vx * dt
                p.y += p.vy * dt
                if k == "cube":
                    p.rot += p.vrot * dt
                    self._draw_cube(p, q)
                elif k == "shard":
                    p.rot += p.vrot * dt
                    self._draw_shard(p, q)
                else:
                    self._draw_spark(p, q)

    # ------------------------------------------------------------ internos
    def _kill(self, p):
        p.active = False
        self.c.itemconfig(p.item, state="hidden")

    def _col(self, p, q):
        """branco-quente -> cor -> fundo."""
        if q < 0.12:
            return mix(p.hot, p.color, q / 0.12)
        return mix(p.color, self.bg, ((q - 0.12) / 0.88) ** 1.4)

    def _set(self, p, **kw):
        key = tuple(sorted(kw.items()))
        if key != p.last:
            p.last = key
            self.c.itemconfig(p.item, state="normal", **kw)

    def _draw_cube(self, p, q, hold=False):
        s = p.size * (1.0 - 0.45 * q)
        ca, sa = math.cos(p.rot), math.sin(p.rot)
        pts = []
        # Silhueta hexagonal e três arestas internas: um cubo, não um confete.
        vertices = ((-.87*s, -.5*s), (0, -s), (.87*s, -.5*s),
                    (.87*s, .5*s), (0, s), (-.87*s, .5*s))
        for ox, oy in (*vertices, vertices[0], (0, 0), vertices[2],
                       (0, 0), vertices[4], (0, 0), vertices[0]):
            pts += (p.x + ox * ca - oy * sa, p.y + ox * sa + oy * ca)
        self.c.coords(p.item, *pts)
        edge = p.color if hold else self._col(p, q)
        # face escura + aresta clara = aparência facetada (não "líquida")
        self._set(p, outline=edge, fill=mix(self.bg, edge, 0.16))

    def _draw_shard(self, p, q):
        ca, sa = math.cos(p.rot), math.sin(p.rot)
        s = p.size * (1.0 - 0.3 * q)
        tri = ((s, 0), (-s * 0.5, s * 0.22), (-s * 0.35, -s * 0.22))
        pts = []
        for ox, oy in tri:
            pts += (p.x + ox * ca - oy * sa, p.y + ox * sa + oy * ca)
        self.c.coords(p.item, *pts)
        edge = self._col(p, q)
        self._set(p, outline=edge, fill=mix(self.bg, edge, 0.25))

    def _draw_spark(self, p, q):
        vx, vy = p.vx * p.size, p.vy * p.size
        self.c.coords(p.item, p.x - vx, p.y - vy, p.x, p.y)
        self._set(p, fill=self._col(p, q * 0.8))

    def _upd_ring(self, p, q):
        r = p.size * _ease_out(q)
        self.c.coords(p.item, p.x - r, p.y - r * p.b, p.x + r, p.y + r * p.b)
        self._set(
            p, outline=mix(p.hot, self.bg, q**0.7), width=max(1, int(p.a * (1 - q)))
        )

    def _upd_flash(self, p, q):
        r = p.size * (0.4 + 0.6 * _ease_out(q))
        self.c.coords(p.item, p.x - r, p.y - r, p.x + r, p.y + r)
        self._set(p, fill=mix(p.hot, self.bg, q))

    def _upd_scan(self, p):
        q = p.t / p.life
        if q >= 1.0:
            self._kill(p)
            return
        fx, fy, length, width = p.a, p.b, p.c, p.d
        px, py = -fy, fx
        pos = (0.5 - q) * length  # nariz -> cauda
        cx, cy = p.x + fx * pos, p.y + fy * pos
        hw = width * 0.9
        self.c.coords(p.item, cx - px * hw, cy - py * hw, cx + px * hw, cy + py * hw)
        self._set(p, fill=mix(p.hot, p.color, q), width=3)

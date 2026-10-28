"""Efeitos visuais: partículas, ondas de choque, tremor de tela, fades e textos animados."""

import math
import random

from config import BG_COLOR, blend
from derez import Derez


from sprites_topview import CYCLES

BIKES = [(cycle.name,) for cycle in CYCLES]

_GOLDEN_RATIO = (1 + math.sqrt(5)) / 2
_INV_GOLDEN_RATIO = 1 / _GOLDEN_RATIO
_CUBE_VERTICES = tuple(
    (x, y, z)
    for x in (-1, 1)
    for y in (-1, 1)
    for z in (-1, 1)
)
_DODECAHEDRON_VERTICES = _CUBE_VERTICES + tuple(
    vertex
    for zero_axis in range(3)
    for small_sign in (-1, 1)
    for large_sign in (-1, 1)
    for vertex in [
        tuple(
            0 if axis == zero_axis
            else small_sign * _INV_GOLDEN_RATIO
            if axis == (zero_axis + 1) % 3
            else large_sign * _GOLDEN_RATIO
            for axis in range(3)
        )
    ]
)


def _wireframe(name):
    if name == "octahedron":
        vertices = (
            (1, 0, 0), (-1, 0, 0), (0, 1, 0),
            (0, -1, 0), (0, 0, 1), (0, 0, -1),
        )
        edges = tuple(
            (a, b)
            for a in range(len(vertices))
            for b in range(a + 1, len(vertices))
            if sum((vertices[a][i] - vertices[b][i]) ** 2 for i in range(3)) == 2
        )
        return vertices, edges
    if name == "stellated_octahedron":
        vertices = _CUBE_VERTICES
        edges = tuple(
            (a, b)
            for a in range(len(vertices))
            for b in range(a + 1, len(vertices))
            if sum(vertices[a][i] != vertices[b][i] for i in range(3)) == 2
        )
        return vertices, edges
    if name == "dodecahedron":
        vertices = _DODECAHEDRON_VERTICES
        distances = [
            sum((vertices[a][i] - vertices[b][i]) ** 2 for i in range(3))
            for a in range(len(vertices))
            for b in range(a + 1, len(vertices))
        ]
        edge_length = min(distances)
        edges = tuple(
            (a, b)
            for a in range(len(vertices))
            for b in range(a + 1, len(vertices))
            if math.isclose(
                sum((vertices[a][i] - vertices[b][i]) ** 2 for i in range(3)),
                edge_length,
                rel_tol=1e-9,
            )
        )
        return vertices, edges
    raise ValueError(f"Unknown firework shape: {name}")


class Effects:
    def __init__(self, canvas):
        self.cv = canvas
        canvas.configure(
            confine=False
        )  # permite "empurrar" a visão do canvas (screen shake)
        canvas.scan_mark(0, 0)
        self.voxels = Derez(canvas, bg=BG_COLOR, cubes=640, shards=56, sparks=192,
                            rings=8, flashes=4, scans=4)
        self.reset()

    def reset(self):
        """Chamado a cada rodada (os itens já foram apagados do canvas)."""
        self.particles, self.tasks, self.shake_amt = [], [], 0.0
        self.voxels.clear()
        self.cv.scan_dragto(0, 0, gain=1)

    # ---- criação de efeitos
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

    def explode(self, x, y, color, n=55, tags="game_obj"):
        for _ in range(n):
            ang, spd = random.uniform(0, math.tau), random.uniform(80, 460)
            col = random.choice((color, color, "#FFFFFF"))
            life = random.uniform(0.5, 1.1)
            item = self.cv.create_rectangle(
                x, y, x, y, fill=col, outline="", tags=tags
            )  # "derezz": cubos
            self.particles.append(
                {
                    "id": item,
                    "x": x,
                    "y": y,
                    "color": col,
                    "life": life,
                    "max": life,
                    "vx": math.cos(ang) * spd,
                    "vy": math.sin(ang) * spd,
                }
            )

    def derez(self, x, y, color, d, scale=1.0, tags="game_obj", wall=None):
        """Varredura, cubos facetados e estilhaços em um pool persistente."""
        self.voxels.spawn(
            x,
            y,
            color=color,
            heading=math.atan2(d[1], d[0]),
            wall=wall,
            length=34 * scale,
            width=14 * scale,
            power=scale,
        )
        self.voxels.update(0)

    def dissolve_trail(self, pieces, dur, delay=0.0, on_done=None):
        """Apaga da cabeça à cauda, respeitando as quebras dos portais.

        pieces: [(coordenadas cauda->cabeça, [(item, cor), ...]), ...],
        da peça mais antiga à atual. Não conecta as saídas de um portal.
        """
        paths = []
        for coords, pairs in pieces:
            points = list(zip(coords[::2], coords[1::2]))
            segments = [math.dist(a, b) for a, b in zip(points, points[1:])]
            paths.append((points, segments, sum(segments), tuple(pairs)))
        total = sum(path[2] for path in paths)
        elapsed = [-delay]

        def run(dt):
            elapsed[0] += dt
            if elapsed[0] < 0:
                return
            q = min(1.0, elapsed[0] / max(.001, dur))
            remaining = total * (1 - q)
            for points, segments, length, pairs in paths:
                visible = min(length, max(0, remaining))
                remaining -= length
                if visible <= 0 or len(points) < 2:
                    for item, _ in pairs:
                        self.cv.itemconfig(item, state="hidden")
                    continue
                coords = list(points[0])
                left = visible
                for a, b, distance in zip(points, points[1:], segments):
                    if distance > left:
                        k = left / distance
                        coords.extend((a[0] + (b[0] - a[0]) * k,
                                       a[1] + (b[1] - a[1]) * k))
                        break
                    coords.extend(b)
                    left -= distance
                for item, color in pairs:
                    self.cv.coords(item, *coords)
                    self.cv.itemconfig(item, fill=blend(color, BG_COLOR, q * .4))
            if q >= 1:
                for _, _, _, pairs in paths:
                    for item, _ in pairs:
                        self.cv.delete(item)
                if on_done:
                    on_done()
                return False

        self.tasks.append(run)

    def ring(self, x, y, color, max_r=140, dur=0.55, tags="game_obj"):
        item = self.cv.create_oval(x, y, x, y, outline=color, width=4, tags=tags)
        t = [0.0]

        def run(dt):
            t[0] += dt
            k = t[0] / dur
            if k >= 1:
                self.cv.delete(item)
                return False
            r = max_r * (1 - (1 - k) ** 2)
            self.cv.coords(item, x - r, y - r, x + r, y + r)
            self.cv.itemconfig(
                item, outline=blend(color, BG_COLOR, k), width=max(1, int(5 * (1 - k)))
            )

        self.tasks.append(run)

    def firework(self, x, y, color, size=150, rise=160, tags="game_obj"):
        """Fogos no estilo da Grade: um risco de luz sobe e explode em raios retos que caem e somem."""
        tail = self.cv.create_line(
            x, y + rise, x, y + rise, fill=color, width=2, tags=tags
        )
        rays, geometry, t, n = [], [], [0.0], 18
        burst_started = [False]
        shape = (
            random.choice(
                ("octahedron", "dodecahedron", "stellated_octahedron")
            )
            if random.random() < 0.4
            else None
        )
        vertices, edges = _wireframe(shape) if shape else ((), ())

        def run(dt):
            t[0] += dt
            if t[0] < 0.35:
                hy = y + rise * (1 - t[0] / 0.35) ** 2
                self.cv.coords(tail, x, min(y + rise, hy + 45), x, hy)
                return
            if not burst_started[0]:
                burst_started[0] = True
                self.cv.delete(tail)
                if shape:
                    geometry.extend(
                        self.cv.create_line(
                            x, y, x, y, fill=color, width=2, tags=tags
                        )
                        for _ in edges
                    )
                else:
                    rays.extend(
                        (
                            self.cv.create_line(
                                x, y, x, y, fill=color, width=3, tags=tags
                            ),
                            math.tau * i / n,
                        )
                        for i in range(n)
                    )
                self.ring(x, y, color, max_r=size * 0.7, dur=0.6, tags=tags)
                self.explode(x, y, color, n=20, tags=tags)
            k = min(1.0, (t[0] - 0.35) / 1.0)
            radius = size * (1 - (1 - k) ** 3)
            sag = 40 * k * k  # gravidade puxando os raios
            col = blend(color, BG_COLOR, k**1.5)
            if shape:
                ax, ay, az = t[0] * 0.9, t[0] * 0.65, t[0] * 0.4
                ca, sa = math.cos(ax), math.sin(ax)
                cb, sb = math.cos(ay), math.sin(ay)
                cc, sc = math.cos(az), math.sin(az)
                projected = []
                for vx, vy, vz in vertices:
                    ry, rz = vy * ca - vz * sa, vy * sa + vz * ca
                    rx, rz = vx * cb + rz * sb, -vx * sb + rz * cb
                    rx, ry = rx * cc - ry * sc, rx * sc + ry * cc
                    perspective = 3.8 / (4.8 + rz)
                    projected.append((x + rx * radius * perspective,
                                      y + ry * radius * perspective + sag))
                for item, (a, b) in zip(geometry, edges):
                    self.cv.coords(item, *projected[a], *projected[b])
                    self.cv.itemconfig(
                        item, fill=col, width=max(1, 2.5 * (1 - k))
                    )
            else:
                r_out = radius
                r_in = r_out * min(1.0, k * 1.4) * 0.8
                for item, a in rays:
                    c, s = math.cos(a), math.sin(a)
                    self.cv.coords(
                        item,
                        x + c * r_in,
                        y + s * r_in + sag,
                        x + c * r_out,
                        y + s * r_out + sag,
                    )
                    self.cv.itemconfig(item, fill=col, width=1 + int(3 * (1 - k)))
            if k >= 1:
                for item, _ in rays:
                    self.cv.delete(item)
                for item in geometry:
                    self.cv.delete(item)
                return False

        self.tasks.append(run)

    def popup(self, text, x, y, color, life=0.9, size=110, shrink=0.55):
        """Texto grande que encolhe e some (contagem regressiva, GO!)."""
        item = self.cv.create_text(
            x, y, text=text, fill=color, font=("Courier", size, "bold"), tags="game_obj"
        )
        t = [0.0]

        def run(dt):
            t[0] += dt
            k = t[0] / life
            if k >= 1:
                self.cv.delete(item)
                return False
            self.cv.itemconfig(
                item,
                fill=blend(color, BG_COLOR, k * k),
                font=("Courier", int(size * (1 - shrink * k)), "bold"),
            )

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
        self.voxels.update(dt)

        tasks, self.tasks = self.tasks, []
        for task in tasks:
            if task(dt) is not False:
                self.tasks.append(task)

        if self.shake_amt > 0.4:
            a = self.shake_amt
            self.cv.scan_dragto(
                int(random.uniform(-a, a)), int(random.uniform(-a, a)), gain=1
            )
            self.shake_amt *= 0.86 ** (dt * 60)
        elif self.shake_amt > 0:
            self.shake_amt = 0.0
            self.cv.scan_dragto(0, 0, gain=1)

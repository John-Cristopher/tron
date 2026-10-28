"""Logo TRON vetorial extrudado e travessia de um corredor em perspectiva."""

import math

import theme as T


def ellipse(cx, cy, rx, ry, n=40):
    return [
        (cx + math.cos(i * math.tau / n) * rx, cy + math.sin(i * math.tau / n) * ry)
        for i in range(n)
    ]


def logo_geometry():
    """Faces frontais e contornos; vazios de R/O continuam abertos em 3D."""
    t = [
        (-5.8, -1.3),
        (-3.35, -1.3),
        (-3.35, -0.82),
        (-4.28, -0.82),
        (-4.28, 1.3),
        (-4.87, 1.3),
        (-4.87, -0.82),
        (-5.8, -0.82),
    ]
    # O R é construído em peças sólidas, sem pintar por cima de sua abertura.
    stem = [(-3.03, -1.3), (-2.48, -1.3), (-2.48, 1.3), (-3.03, 1.3)]
    outer = [(-2.48, -1.3)]
    inner = [(-2.48, -0.79)]
    for i in range(21):
        a = -math.pi / 2 + i * math.pi / 20
        outer.append((-1.92 + 0.98 * math.cos(a), -0.48 + 0.82 * math.sin(a)))
        inner.append((-1.92 + 0.43 * math.cos(a), -0.48 + 0.31 * math.sin(a)))
    outer.append((-2.48, 0.34))
    inner.append((-2.48, -0.17))
    leg = [(-2.30, 0.10), (-1.65, 0.10), (-0.68, 1.3), (-1.40, 1.3)]
    o_outer = ellipse(1.03, 0, 1.28, 1.38)
    o_inner = ellipse(1.03, 0, 0.73, 0.91)
    n = [
        (2.72, 1.3),
        (2.72, -1.3),
        (3.25, -1.3),
        (4.76, 0.42),
        (4.76, -1.3),
        (5.32, -1.3),
        (5.32, 1.3),
        (4.80, 1.3),
        (3.29, -0.42),
        (3.29, 1.3),
    ]
    faces = [t, stem, leg, n]
    for a, b in ((outer, inner), (o_outer + [o_outer[0]], o_inner + [o_inner[0]])):
        faces.extend([[a[i], a[i + 1], b[i + 1], b[i]] for i in range(len(a) - 1)])
    # O contorno do R acompanha o vão e a perna diagonal; não é uma fonte do sistema.
    r_outline = [(-3.03, -1.3), (-1.92, -1.3)]
    for i in range(1, 19):
        a = -math.pi / 2 + i * (math.pi * 5 / 6) / 18
        r_outline.append((-1.92 + 0.98 * math.cos(a), -0.48 + 0.82 * math.sin(a)))
    r_outline += [(-0.68, 1.3), (-1.40, 1.3), (-2.48, 0.10), (-2.48, 1.3), (-3.03, 1.3)]
    contours = [t, r_outline, inner, o_outer, o_inner, n]
    return faces, contours


def clip_near(points, near=0.28):
    """Recorta a face antes da projeção, inclusive enquanto a câmera a atravessa."""
    if not points:
        return []
    result = []
    previous = points[-1]
    for current in points:
        a, b = previous[2] >= near, current[2] >= near
        if a != b:
            ratio = (near - previous[2]) / (current[2] - previous[2])
            result.append(
                tuple(
                    previous[i] + (current[i] - previous[i]) * ratio for i in range(3)
                )
            )
        if b:
            result.append(current)
        previous = current
    return result


def camera_pose(age):
    """Começa vendo o logo inteiro; alinha e entra pelo centro do O."""
    hold = min(1.0, max(0.0, age / 2.5))
    push = min(1.0, max(0.0, (age - 2.5) / 5.7))
    smooth = hold * hold * (3 - 2 * hold)
    return (
        1.03 * push * push,
        0.0,
        -21 + 2 * smooth + 23 * push * push,
        -0.22 * (1 - smooth),
        -0.115 * (1 - smooth),
    )


def letter_power(age, letter):
    """T, R, O, N acendem em sequência com três falhas curtas de ignição."""
    local = age - letter * .20
    if local < 0:
        return .0
    if local < .48:
        return .16 if int(local / .08) % 2 else .95
    return .93 + .07 * math.sin(age * 2.8 + letter * .6)


def contour_pulse(contour, phase, span=.14):
    """Trecho de comprimento constante que percorre um contorno fechado."""
    points = contour + contour[:1]
    lengths = [math.dist(a, b) for a, b in zip(points, points[1:])]
    total = sum(lengths)
    start, end = phase % 1 * total, (phase % 1 + span) * total
    result, cursor = [], 0.0
    for _ in range(2):
        for a, b, length in zip(points, points[1:], lengths):
            lo, hi = max(start, cursor), min(end, cursor + length)
            if lo <= hi and length:
                for value in (lo, hi):
                    k = (value - cursor) / length
                    point = (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)
                    if not result or point != result[-1]:
                        result.append(point)
            cursor += length
        if cursor >= end:
            break
    return result


class Logo3D:
    def __init__(self, canvas, width, height):
        self.cv, self.w, self.h = canvas, width, height
        self.faces, self.contours = logo_geometry()
        self.surface_items = []
        self.outline_items = []
        self.corridor_items = []
        self.rail_items = []
        self.mesh = []
        self.mesh_letters = []
        self.pulses, self.inner_items, self.reflections = [], [], []
        self.visible = False
        self.environment_visible = False
        # Cada aresta tem uma lateral real entre z=0 e z=1.1.
        for contour_index, contour in enumerate(self.contours):
            for a, b in zip(contour, contour[1:] + contour[:1]):
                self.mesh.append(
                    (
                        [
                            (a[0], a[1], 0),
                            (b[0], b[1], 0),
                            (b[0], b[1], 1.1),
                            (a[0], a[1], 1.1),
                        ],
                        False,
                    )
                )
                self.mesh_letters.append((0, 1, 1, 2, 2, 3)[contour_index])
        self.mesh += [([(x, y, 0) for x, y in face], True) for face in self.faces]
        self.mesh_letters += [0 if sum(x for x, _ in face)/len(face) < -3.2 else
            1 if sum(x for x, _ in face)/len(face) < -.45 else
            2 if sum(x for x, _ in face)/len(face) < 2.5 else 3 for face in self.faces]
        for _ in range(12 * 6 * 2):
            self.corridor_items.append(self._polygon())
        for _ in range(22):
            self.rail_items.append(self._line(T.GRID_BRIGHT, 1))
        for _ in self.mesh:
            self.surface_items.append(self._polygon())
        for contour in self.contours:
            back = self._line(T.GRID_BRIGHT, 1)
            front = [
                self._line(color, width) for color, width in T.glow_layers(T.CYAN, 2.3)
            ]
            self.outline_items.append((back, front))
            self.pulses.append([self._line(color, width) for color, width in T.glow_layers(T.CORE, 2)])
            self.inner_items.append(self._line(T.CYAN, .7))
            self.reflections.append(self._line(T.CYAN, 1))
        self.all_items = self.corridor_items + self.rail_items + self.surface_items
        self.all_items += [
            item for back, front in self.outline_items for item in [back] + front
        ]
        self.all_items += [item for group in self.pulses for item in group] + self.inner_items + self.reflections

    def _polygon(self):
        return self.cv.create_polygon(
            0,
            0,
            0,
            0,
            0,
            0,
            fill=T.SHELL,
            outline="",
            state="hidden",
            tags=("intro", "intro_logo"),
        )

    def _line(self, color, width):
        return self.cv.create_line(
            0,
            0,
            0,
            0,
            fill=color,
            width=width,
            state="hidden",
            tags=("intro", "intro_logo"),
        )

    def hide(self):
        if self.visible:
            for item in self.all_items:
                self.cv.itemconfig(item, state="hidden")
            self.visible = False

    def render(
        self, age, view=None, origin=(0.0, 0.0, 0.0), scale=1.0, environment=True
    ):
        self.visible = True
        cx, cy, cz, yaw, roll = camera_pose(age)
        ca, sa = math.cos(yaw), math.sin(yaw)
        cr, sr = math.cos(roll), math.sin(roll)
        focal = min(self.w, self.h * 1.72) * 1.04
        alpha = min(1.0, 0.85 + max(0, age) * 0.6)

        def camera(point):
            if view is not None:
                return view.transform(
                    tuple(origin[i] + point[i] * scale for i in range(3))
                )
            x, y, z = point
            # A rotação dá profundidade às letras; a câmera se alinha antes de entrar.
            x, z = x * ca + z * sa, -x * sa + z * ca
            x, y = x * cr - y * sr, x * sr + y * cr
            return x - cx, y - cy, z - cz

        def project(point):
            if view is not None:
                return view.project(point)
            x, y, z = point
            return (
                max(-self.w * 8, min(self.w * 9, self.w * 0.5 + focal * x / z)),
                max(-self.h * 8, min(self.h * 9, self.h * 0.48 + focal * y / z)),
            )

        def face(item, vertices, color):
            points = [camera(point) for point in vertices]
            clipped = view.clip_face(points) if view is not None else clip_near(points)
            if len(clipped) < 3:
                self.cv.itemconfig(item, state="hidden")
                return
            coords = [v for point in clipped for v in project(point)]
            self.cv.coords(item, *coords)
            self.cv.itemconfig(item, state="normal", fill=color)

        # Os reflexos usam o piso real da cidade, não uma linha de horizonte fixa.
        for contour, item in zip(self.contours, self.reflections):
            if view is None:
                self.cv.itemconfig(item, state="hidden")
                continue
            points = [view.transform((origin[0] + x * scale,
                       -(origin[1] + y * scale), origin[2])) for x, y in contour + contour[:1]]
            if any(p[2] < .28 for p in points):
                self.cv.itemconfig(item, state="hidden")
                continue
            segments = [view.clip_segment(a, b) for a, b in zip(points, points[1:])]
            coords = [v for segment in segments if segment for point in segment for v in project(point)]
            if len(coords) >= 4:
                self.cv.coords(item, *coords)
                self.cv.itemconfig(item, state="normal", fill=T.blend(T.BACKGROUND, T.CYAN, .15))
                self.cv.tag_raise(item)
            else:
                self.cv.itemconfig(item, state="hidden")

        if environment:
            self.environment_visible = True
            # Placas no piso e no teto formam um cânion de circuitos, como uma cidade digital.
            first = math.floor((cz + 1) / 8) * 8
            index = 0
            for row in reversed(range(12)):
                z = first + row * 8
                depth = min(1.0, max(0.0, (z - cz) / 105))
                for side in (-1, 1):
                    y = side * 4.9
                    for column in range(6):
                        x = -12 + column * 4
                        color = T.blend(T.ARMOR, T.BACKGROUND, depth * 0.8)
                        if (column + row) % 3 == 0:
                            color = T.blend(T.GRID_BRIGHT, T.BACKGROUND, depth * 0.75)
                        face(
                            self.corridor_items[index],
                            [
                                (x + 0.10, y, z),
                                (x + 3.8, y, z),
                                (x + 3.8, y, z + 6.7),
                                (x + 0.10, y, z + 6.7),
                            ],
                            color,
                        )
                        index += 1
            for i, item in enumerate(self.rail_items):
                side = -1 if i < 11 else 1
                x = -12 + (i % 11) * 2.4
                a, b = camera((x, side * 4.88, cz + 1)), camera(
                    (x, side * 4.88, cz + 120)
                )
                if a[2] > 0.28 and b[2] > 0.28:
                    self.cv.coords(item, *project(a), *project(b))
                    self.cv.itemconfig(
                        item,
                        state="normal",
                        fill=T.blend(T.GRID_BRIGHT, T.BACKGROUND, 0.25),
                    )
                else:
                    self.cv.itemconfig(item, state="hidden")
        elif self.environment_visible:
            for item in self.corridor_items + self.rail_items:
                self.cv.itemconfig(item, state="hidden")
            self.environment_visible = False
        # Faces distantes primeiro; a câmera pode passar pelos vazios sem saltos de escala.
        order = sorted(
            range(len(self.mesh)),
            key=lambda i: sum(camera(p)[2] for p in self.mesh[i][0])
            / len(self.mesh[i][0]),
            reverse=True,
        )
        for index in order:
            points, front = self.mesh[index]
            power = letter_power(age, self.mesh_letters[index])
            color = T.blend(
                T.BACKGROUND,
                T.BIKE_ARMOR if front else T.GRID_BRIGHT,
                alpha * (0.80 if front else 0.20) * (.18 + .82 * power),
            )
            face(self.surface_items[index], points, color)
            self.cv.tag_raise(self.surface_items[index])
        for ci, (contour, (back, front)) in enumerate(zip(self.contours, self.outline_items)):
            power = letter_power(age, (0, 1, 1, 2, 2, 3)[ci])
            for z, items in ((1.1, [back]), (0, front)):
                points = [camera((x, y, z)) for x, y in contour]
                if any(p[2] < 0.28 for p in points):
                    for item in items:
                        self.cv.itemconfig(item, state="hidden")
                    continue
                coords = [v for point in points + [points[0]] for v in project(point)]
                colors = (
                    [T.blend(T.GRID_BRIGHT, T.BACKGROUND, 0.2)]
                    if z
                    else [
                        T.blend(T.BACKGROUND, c, alpha * power)
                        for c, _ in T.glow_layers(T.CYAN, 2.3)
                    ]
                )
                for item, color in zip(items, colors):
                    self.cv.coords(item, *coords)
                    self.cv.itemconfig(item, state="normal", fill=color)
                    self.cv.tag_raise(item)
            # Circuito paralelo por dentro da borda e reflexo especular móvel.
            center = (sum(x for x, _ in contour)/len(contour), sum(y for _, y in contour)/len(contour))
            inner = [(center[0] + (x-center[0])*.975, center[1] + (y-center[1])*.975) for x,y in contour]
            for path, items, tint, gain in (
                (inner + inner[:1], [self.inner_items[ci]], T.CYAN, .45 * power),
                (contour_pulse(contour, age * .22 + ci * .09), self.pulses[ci], T.CORE, power),
            ):
                points = [camera((x,y,-.015)) for x,y in path]
                if len(points) < 2 or any(point[2] < .28 for point in points):
                    for item in items:
                        self.cv.itemconfig(item, state="hidden")
                    continue
                coords = [v for point in points for v in project(point)]
                colors = list(T.glow_layers(tint, 2)) if len(items)>1 else [(tint,.7)]
                for item, (color, width) in zip(items, colors):
                    self.cv.coords(item,*coords)
                    self.cv.itemconfig(item,state="normal",fill=T.blend(T.BACKGROUND,color,gain),width=width)
                    self.cv.tag_raise(item)

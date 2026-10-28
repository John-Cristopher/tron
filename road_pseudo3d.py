"""Estrada em perspectiva com faixas agrupadas e objetos reutilizados no Canvas."""

import math

import theme as T


class RoadRenderer:
    draw_distance = 128

    def draw(self, p, sim, project, w, h, objects):
        camera_s = sim.player.s - 8
        first = math.floor(camera_s / sim.road.segment_length)
        visible = []
        ceiling = h + 1
        for i in range(self.draw_distance):
            s0 = (first + i) * sim.road.segment_length
            s1 = s0 + sim.road.segment_length
            a, b = project(s0), project(s1)
            if a is None and s1 > camera_s + 0.65:
                a = project(camera_s + 0.65)
            if a is None or b is None or b[1] >= ceiling:
                continue
            if a[1] > h + 2 and a[1] != b[1]:
                t = (h + 2 - b[1]) / (a[1] - b[1])
                a = (b[0] + (a[0] - b[0]) * t, h + 2, b[2] + (a[2] - b[2]) * t)
            visible.append((s0, s1, a, b, ceiling))
            ceiling = min(ceiling, b[1])
        groups = []
        for segment in reversed(visible):
            band = int(segment[0] // 32)
            if not groups or groups[-1][0] != band:
                groups.append((band, []))
            groups[-1][1].append(segment)
        for band, segments in groups:
            # Quatro segmentos contíguos viram um polígono, mantendo curvas/cristas.
            points = [segments[0][3]] + [seg[2] for seg in segments]

            def surface(left, right, color):
                coords = [v for x, y, r in points for v in (x + r * left, y)]
                coords += [
                    v for x, y, r in reversed(points) for v in (x + r * right, y)
                ]
                p.polygon(coords, fill=color)

            # O chão lateral compartilha exatamente os segmentos da pista.
            surface(-90, 90, T.blend(T.BACKGROUND, T.GRID, .20 + .08 * (band % 2)))
            surface(-1.12, 1.12, T.SHOULDER[band % 2])
            surface(-1, 1, T.ASPHALT[band % 2])
            for side in (-1, 1):
                coords = [v for x, y, r in points for v in (x + r * side, y)]
                T.neon_line(p, coords, T.CYAN, max(0.5, points[-1][2] * 0.003))
                if band % 2:
                    surface(side * 1.025, side * 1.085, T.blend(T.CYAN, T.GRID, 0.48))
            if band % 2:
                for lane in (-1 / 3, 1 / 3):
                    coords = [v for x, y, r in points for v in (x + r * lane, y)]
                    p.line(
                        coords, fill=T.GRID_BRIGHT, width=max(1, points[-1][2] * 0.004)
                    )
            x, y, r = points[-1]
            p.line((x - r, y, x + r, y), fill=T.GRID, width=1)
            fade = max(.08, min(.85, r / (w * .12)))
            tint = T.blend(T.BACKGROUND, T.GRID_BRIGHT, fade)
            for side in (-1, 1):
                p.line((x + side * r * 1.12, y, x + side * r * 90, y), fill=tint, width=1)
                for lateral in (2, 4, 7, 11, 17, 25):
                    if points[0][2] * lateral < 7:
                        continue
                    coords = [v for cx, cy, radius in points for v in (cx + side * radius * lateral, cy)]
                    p.line(coords, fill=tint, width=1)
        # O terreno inteiro vem antes dos objetos. Uma banda de asfalto próxima
        # nunca recobre a base de um poste que já foi desenhado.
        for s0, s1, a, b, clip in reversed(visible):
            if int(s0) % 64 == 0:
                self._scenery(p, project, s0, w, h)
            objects(s0, s1, clip)

    def _scenery(self, p, project, s, w, h):
        for side in (-1, 1):
            point = project(s, side * 1.35)
            if point is None:
                continue
            x, y, r = point
            height = min(h * 0.6, r * 0.70)
            if r < 2 or x < -w * 0.15 or x > w * 1.15:
                continue
            p.line((x, y, x, y - height), fill=T.METAL, width=max(1, r * 0.014))
            T.neon_line(
                p,
                (x, y - height, x - side * r * 0.13, y - height * 1.03),
                T.CYAN,
                max(0.7, r * 0.012),
            )
            if int(s) % 192 == 64:
                rw = r * .13
                coords = (x - rw, y, x + rw, y, x + rw * .7, y - height * .7,
                          x - rw * .7, y - height * .7, x - rw, y)
                p.polygon(coords, fill=T.ARMOR)
                p.line(coords, fill=T.GRID_BRIGHT, width=max(1, r * .005))
            elif int(s) % 192 == 128:
                apex = (x, y - height * .65)
                p.polygon((x - r * .18, y, *apex, x + r * .18, y), fill=T.SHELL)
                p.line((x - r * .18, y, *apex, x + r * .18, y, x - r * .18, y), fill=T.GRID_BRIGHT, width=1)
        if int(s) % 128 == 0:
            left, right = project(s, -1.22), project(s, 1.22)
            if left and right:
                lx, ly, r = left
                rx, ry, _ = right
                top = ly - min(h * 0.7, r * 0.95)
                coords = (
                    lx,
                    ly,
                    lx,
                    top + r * 0.12,
                    lx + r * 0.16,
                    top,
                    rx - r * 0.16,
                    top,
                    rx,
                    top + r * 0.12,
                    rx,
                    ry,
                )
                p.line(coords, fill=T.ARMOR, width=max(2, r * 0.04))
                T.neon_line(p, coords, T.CYAN, max(0.6, r * 0.006))
                if r > 18:
                    p.text((lx + rx) / 2, top + r * .12,
                           text=f"SETOR {int(s // 512) % 12 + 1:02d}", fill=T.MUTED,
                           font=(T.FONT, -max(7, min(22, int(r * .09))), "bold"))

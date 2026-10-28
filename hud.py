"""Instrumentos da perseguição: painéis chanfrados e barras segmentadas."""

from menu_nav import INPUT
import theme as T


def panel(p, left, top, right, bottom, color=T.GRID_BRIGHT, fill=T.PANEL):
    cut = min(12, (bottom - top) * 0.22)
    p.polygon(
        (
            left + cut,
            top,
            right,
            top,
            right,
            bottom - cut,
            right - cut,
            bottom,
            left,
            bottom,
            left,
            top + cut,
        ),
        fill=fill,
        outline=color,
        width=1,
    )


def draw_hud(p, sim, w, h, color):
    font = max(9, int(h / 62))
    panel(p, w * 0.025, h * 0.018, w * 0.975, h * 0.145)
    p.text(
        w * 0.04,
        h * 0.043,
        text={"reach": "01 / ALCANCE", "pressure": "02 / PRESSÃO NO VÁCUO",
              "finale": "03 / CORTE DE LUZ", "derez": "RINZLER / FALHA DO SISTEMA"}[sim.phase],
        fill=color,
        anchor="w",
        font=(T.FONT, font, "bold"),
    )
    p.text(
        w * 0.948,
        h * 0.060,
        text=f"{int(sim.player.speed*3.6):03d}",
        fill=T.CORE,
        anchor="e",
        font=(T.FONT, font * 3, "bold"),
    )
    p.text(
        w * 0.948,
        h * 0.116,
        text="KM/H",
        fill=T.MUTED,
        anchor="e",
        font=(T.FONT, font - 1),
    )
    bars = (
        (0.04, "ENERGIA", sim.player.energy / 100, color),
        (0.29, "PRESSÃO", sim.pressure, T.ORANGE),
        (0.54, "CONTATO", sim.contact, T.CYAN),
    )
    for start, label, value, tint in bars:
        left, top = w * start, h * 0.099
        p.text(
            left,
            top - h * 0.018,
            text=label,
            fill=T.MUTED,
            anchor="w",
            font=(T.FONT, max(8, font - 2)),
        )
        for i in range(16):
            x = left + w * 0.20 * i / 16
            p.rect(
                (x, top, x + w * 0.20 / 16 - 2, top + max(4, h * 0.008)),
                fill=tint if (i + 0.5) / 16 <= max(0, min(1, value)) else T.GRID,
            )
    panel(
        p,
        w * 0.34,
        h * 0.158,
        w * 0.66,
        h * 0.195,
        color=T.blend(T.ORANGE, T.GRID, 0.6),
    )
    gap = f"{int(sim.gap):03d} m" if sim.gap >= 0 else f"ATRÁS  {int(-sim.gap)} m"
    p.text(
        w * 0.5,
        h * 0.177,
        text=f"RINZLER  {gap}",
        fill=T.AMBER,
        font=(T.FONT, font, "bold"),
    )
    boost = max(0, sim.player.boost_ready - sim.time)
    wall = max(0, sim.wall_ready - sim.time)
    for left, right, label, remaining in (
        (0.035, 0.23, "BOOST", boost),
        (0.77, 0.965, "PAREDE", wall),
    ):
        panel(p, w * left, h * 0.887, w * right, h * 0.934, color=color)
        p.text(
            w * (left + right) / 2,
            h * 0.910,
            text=("E / CORTAR FAIXA" if label == "PAREDE" and sim.phase == "finale" and not sim.cut_deployed
                  else f"{label}  {remaining:.0f}s" if remaining > 0 else f"{label}  PRONTO"),
            fill=color,
            font=(T.FONT, font, "bold"),
        )
    pending = [
        wall
        for wall in sim.walls
        if wall.owner == "rival" and 0 < wall.s - sim.player.s < 180
    ]
    warning = ""
    if sim.phase == "derez":
        warning = "RINZLER DERESOLVIDO" if sim.derez_time >= 1.6 else "RINZLER / PERDENDO O CONTROLE"
    elif sim.phase == "finale":
        lane = "ESQUERDA" if sim.target_lane < -.3 else "DIREITA" if sim.target_lane > .3 else "CENTRO"
        action = "CORTE LANÇADO" if sim.cut_deployed else "ALINHE A MOTO E USE " + (INPUT.label("x") if INPUT.use_pad else "E")
        warning = f"FAIXA {lane} / {action} / {max(0, sim.finale_until - sim.time):.1f}s"
    elif sim.time < getattr(sim, "miss_until", 0):
        warning = "CORTE FALHOU / RECUPERE A PRESSÃO"
    elif pending:
        nearest = min(pending, key=lambda wall: wall.s)
        warning = "PAREDE DE LUZ / ABERTURA À " + (
            "ESQUERDA" if nearest.gap_x < 0 else "DIREITA"
        )
    elif 0 < sim.next_rival_boost - sim.time < 1:
        warning = "RINZLER PREPARANDO BOOST"
    elif abs(sim.player.x) > 1:
        warning = "FORA DA PISTA / VOLTE PARA A GRADE"
    if not warning and sim.phase == "reach":
        warning = "APROXIME-SE ATÉ 40 m / RINZLER ESCAPA A 400 m"
    elif not warning and sim.phase == "pressure":
        warning = "MANTENHA-SE ATRÁS E ALINHADO / MAIS PERTO, MAIS PRESSÃO"
    if warning:
        panel(p, w * 0.14, h * 0.21, w * 0.86, h * 0.26, T.ORANGE, T.WARNING)
        p.text(
            w * 0.5, h * 0.235, text=warning, fill=T.CORE if sim.phase == "derez" else T.AMBER,
            font=(T.FONT, max(8, font - (1 if w < 1000 else 0)), "bold")
        )
    p.text(w * .56, h * .043, text=f"TENTATIVAS {sim.attempts:02d} / {sim.chase_time if sim.phase == 'derez' else sim.time:.1f}s",
           fill=T.MUTED, font=(T.FONT, max(8, font - 1)))
    if INPUT.use_pad:
        hint = f"ANALÓGICO dirige   {INPUT.label('a')} acelera   {INPUT.label('b')} freia   {INPUT.label('rb')} boost   {INPUT.label('x')} parede   {INPUT.label('start')} pausa"
    else:
        hint = "W/↑ acelera   S/↓ freia   A/D ou ←/→ dirige   ESPAÇO boost   E parede   ESC pausa"
    p.text(w * 0.5, h * 0.97, text=hint, fill=T.MUTED, font=(T.FONT, max(8, font - 2)))

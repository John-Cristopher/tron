"""IA: olha à frente, evita becos sem saída e evita colisão de frente."""
import random

LEVELS = {
    "easy":   dict(look=5,  area=0,  mistake=0.06,  bias=1.0, wander=0.012, chase=0.35, reaction=0.120),
    "normal": dict(
        look=9, area=56, mistake=0.035, bias=1.2, wander=0.016, chase=0.75, reaction=0.085
    ),
    "hard": dict(
        look=14, area=104, mistake=0.02, bias=1.5, wander=0.012, chase=1.6, reaction=0.055
    ),
    "extreme": dict(look=18, area=160, mistake=0.005, bias=1.6, wander=0.004, chase=2.4, reaction=0.030),
}


def _free_run(game, cell, d, limit):
    n, (x, y) = 0, cell
    wrap = getattr(game, "wrap_cell", None)
    while n < limit:
        x, y = x + d[0], y + d[1]
        if wrap:
            x, y = wrap((x, y))
        if not game.is_free((x, y)):
            break
        n += 1
    return n


def _flood(game, start, limit):
    """Quantas células livres dá para alcançar a partir de `start` (busca limitada)."""
    seen, stack = {start}, [start]
    wrap = getattr(game, "wrap_cell", None)  # mapas com travessia: vizinho fora da parede reaparece do outro lado
    while stack and len(seen) < limit:
        x, y = stack.pop()
        for c in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if wrap:
                c = wrap(c)
            if c not in seen and game.is_free(c):
                seen.add(c)
                stack.append(c)
    return len(seen)


def _distance(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _predicted_cells(game, target, look):
    """Pontos de interceptação aproximados ao longo do rumo atual do alvo."""
    wrap = getattr(game, "wrap_cell", None)
    points = []
    x, y = target.cell
    for horizon in (max(2, look // 3), max(4, look // 2), look):
        px, py = x, y
        for _ in range(horizon):
            nxt = (px + target.dir[0], py + target.dir[1])
            wrapped = wrap(nxt) if wrap else nxt
            if wrapped == nxt and not game.is_free(nxt):
                break
            px, py = wrapped
        points.append((px, py))
    return points


def reset(rider):
    """Descarta o relógio de reação e o alvo ao criar/reaparecer uma moto."""
    rider.ai_next_decision_at = None
    rider.ai_target_pid = None


def _select_target(game, rider, preferred_pid=None):
    """Escolhe um rival próximo, sem perseguir aliados ou trocar de alvo sem motivo."""
    team_mode = game.is_team_mode() and not game.final_duel
    opponents = [
        other for other in game.riders.values()
        if other is not rider and other.alive
        and (not team_mode
             or game.team_for_player(other.pid) != game.team_for_player(rider.pid))
    ]
    if not opponents:
        rider.ai_target_pid = None
        return None
    preferred = next((o for o in opponents if o.pid == preferred_pid), None)
    nearest = min(opponents, key=lambda o: (_distance(rider.cell, o.cell), o.pid))
    current = next((o for o in opponents if o.pid == rider.ai_target_pid), None)
    # Mantém o alvo, a menos que outro rival esteja pelo menos 30% mais perto.
    if preferred is not None:
        target = preferred
    elif current is not None and _distance(rider.cell, nearest.cell) >= 0.7 * _distance(rider.cell, current.cell):
        target = current
    else:
        target = nearest
    rider.ai_target_pid = target.pid
    return target


def decide(game, rider, level="hard", target_pid=None):
    cfg = LEVELS.get(level, LEVELS["hard"])
    now = game.sim_time
    due = rider.ai_next_decision_at
    if due is None:
        rider.ai_next_decision_at = now + cfg["reaction"]
        return
    if now + 1e-9 < due:
        return
    # Sem desvio de emergência entre decisões: um corte recente pode fechar a IA.
    # Usa tempo de simulação para a pausa não consumir o intervalo de reação.
    rider.ai_next_decision_at = now + cfg["reaction"]
    if rider.queue:
        return
    d = rider.dir
    wrap = getattr(game, "wrap_cell", None)
    danger = {
        wrap((o.cell[0] + o.dir[0], o.cell[1] + o.dir[1])) if wrap
        else (o.cell[0] + o.dir[0], o.cell[1] + o.dir[1])
        for o in game.riders.values() if o is not rider and o.alive
    }
    target = _select_target(game, rider, target_pid)
    intercepts = _predicted_cells(game, target, cfg["look"]) if target else ()
    turn_boost = cfg["look"] if random.random() < cfg["wander"] else 0   # curva "por vontade própria"
    scored = []
    for nd in (d, (d[1], -d[0]), (-d[1], d[0])):
        nxt = (rider.cell[0] + nd[0], rider.cell[1] + nd[1])
        if wrap:
            nxt = wrap(nxt)
        if not game.is_free(nxt):
            continue
        s = _free_run(game, nxt, nd, cfg["look"])
        if cfg["area"]:
            s += _flood(game, nxt, cfg["area"]) * (0.1 if target is None else 0.15)
        s += cfg["bias"] if nd == d else turn_boost
        if intercepts:
            s -= min(_distance(nxt, point) for point in intercepts) * cfg["chase"]
        if nxt in danger:
            s -= 40
        scored.append((s + random.random(), nd))
    if not scored:
        return
    nd = random.choice(scored)[1] if random.random() < cfg["mistake"] else max(scored)[1]
    if nd != d:
        rider.queue.append(nd)
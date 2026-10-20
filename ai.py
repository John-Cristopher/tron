"""IA do modo treinamento: olha à frente, evita becos sem saída e evita colisão de frente."""
import random

LEVELS = {
    "easy":   dict(look=5,  area=0,   mistake=0.06, bias=1.0, wander=0.012),
    "normal": dict(look=12, area=120, mistake=0.015, bias=1.5, wander=0.010),
    "hard":   dict(look=22, area=320, mistake=0.0,  bias=2.0, wander=0.006),
}


def _free_run(game, cell, d, limit):
    n, (x, y) = 0, cell
    while n < limit:
        x, y = x + d[0], y + d[1]
        if not game.is_free((x, y)):
            break
        n += 1
    return n


def _flood(game, start, limit):
    """Quantas células livres dá para alcançar a partir de `start` (busca limitada)."""
    seen, stack = {start}, [start]
    while stack and len(seen) < limit:
        x, y = stack.pop()
        for c in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if c not in seen and game.is_free(c):
                seen.add(c)
                stack.append(c)
    return len(seen)


def decide(game, rider, level="normal"):
    cfg = LEVELS.get(level, LEVELS["normal"])
    d = rider.dir
    danger = {(o.cell[0] + o.dir[0], o.cell[1] + o.dir[1])
              for o in game.riders.values() if o is not rider and o.alive}
    turn_boost = cfg["look"] if random.random() < cfg["wander"] else 0   # curva "por vontade própria"
    scored = []
    for nd in (d, (d[1], -d[0]), (-d[1], d[0])):
        nxt = (rider.cell[0] + nd[0], rider.cell[1] + nd[1])
        if not game.is_free(nxt):
            continue
        s = _free_run(game, nxt, nd, cfg["look"])
        if cfg["area"]:
            s += _flood(game, nxt, cfg["area"]) * 0.1
        s += cfg["bias"] if nd == d else turn_boost
        if nxt in danger:
            s -= 40
        scored.append((s + random.random(), nd))
    if not scored:
        return
    nd = random.choice(scored)[1] if random.random() < cfg["mistake"] else max(scored)[1]
    if nd != d:
        rider.queue.append(nd)
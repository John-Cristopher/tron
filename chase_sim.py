"""Simulação da perseguição, sem dependência da janela ou do áudio. Unidades em metros."""
from dataclasses import dataclass
import math

FIXED_DT = 1 / 120
MAX_SPEED = 100.0
BOOST_SPEED = 120.0
ROAD_HALF_WIDTH = 7.5
REACTION_SEC = 0.14
LOST_DISTANCE = 400.0
SLIPSTREAM_DISTANCE = 40.0
FINALE_SECONDS = 4.0
DEREZ_SECONDS = 4.0
LANES = (-.60, 0.0, .60)


def clamp(value, lo, hi):
    return max(lo, min(hi, value))


class Road:
    segment_length = 8.0

    @staticmethod
    def center(s):
        return 85 * math.sin(s / 650) + 38 * math.sin(s / 270)

    @staticmethod
    def heading(s):
        return 85 / 650 * math.cos(s / 650) + 38 / 270 * math.cos(s / 270)

    @staticmethod
    def curvature(s):
        return -85 / 650**2 * math.sin(s / 650) - 38 / 270**2 * math.sin(s / 270)

    @staticmethod
    def height(s):
        return 12 * math.sin(s / 240) + 8 * math.sin(s / 510)


@dataclass(frozen=True)
class Controls:
    steer: float = 0.0
    throttle: float = 0.0
    brake: float = 0.0
    boost: bool = False
    wall: bool = False


@dataclass
class Bike:
    s: float
    x: float
    speed: float
    energy: float = 100.0
    boost_until: float = 0.0
    boost_ready: float = 0.0
    hit_until: float = 0.0


@dataclass
class LightWall:
    s: float
    gap_x: float
    owner: str
    active_at: float
    expires_at: float
    gap_width: float = 0.72
    hit: bool = False
    cut_x: float | None = None
    cut_width: float = .48

    def blocks(self, x):
        if self.cut_x is not None:
            return abs(x - self.cut_x) <= self.cut_width / 2
        return abs(x - self.gap_x) > self.gap_width / 2


@dataclass
class Obstacle:
    s: float
    x: float
    width: float = 0.22


class ChaseSimulation:
    def __init__(self):
        self.road = Road()
        self.player = Bike(0.0, -.32, 65.0)
        self.rival = Bike(240.0, .20, 76.0)
        self.time = 0.0
        self.accumulator = 0.0
        self.pressure = 0.0
        self.contact = 1.0
        self.result = None
        self.reason = ""
        self.walls = []
        self.obstacles = [Obstacle(950 + i * 620, (-.58, .58, 0)[i % 3]) for i in range(5)]
        self.events = []
        self.ai_due = 0.0
        self.ai_steer = 0.0
        self.ai_throttle = 1.0
        self.ai_brake = 0.0
        self.next_rival_boost = 9.0
        self.next_rival_wall = 6.0
        self.wall_ready = 0.0
        self._boost_held = self._wall_held = False
        self.phase = "reach"
        self.attempts = 0
        self.finale_until = self.telegraph_until = 0.0
        self.target_lane = 0.0
        self.cut_deployed = False
        self.derez_time = 0.0
        self.hit_stop = 0.0
        self.score = 0
        self.chase_time = 0.0
        self.miss_until = 0.0
        self._crash_gap = self._crash_x = 0.0

    @property
    def gap(self):
        return self.rival.s - self.player.s

    @property
    def in_slipstream(self):
        return (0 < self.gap <= SLIPSTREAM_DISTANCE
                and abs(self.player.x - self.rival.x) < .30
                and self.player.speed > 55)

    @property
    def telegraphing(self):
        return self.phase == "finale" and self.time < self.telegraph_until

    def _open_finale(self):
        self.phase = "finale"
        self.pressure = 1.0
        self.attempts += 1
        self.finale_until = self.time + FINALE_SECONDS
        self.telegraph_until = self.time + max(.65, 1.65 - .20 * (self.attempts - 1))
        self.target_lane = min(LANES, key=lambda lane: abs(lane + self.rival.x))
        if abs(self.target_lane - self.rival.x) < .30:
            self.target_lane = -.60 if self.rival.x >= 0 else .60
        self.wall_ready = self.time
        self.cut_deployed = False
        self.next_rival_wall = max(self.next_rival_wall, self.finale_until + 1)
        self.events.append("finale_ready")

    def _miss_finale(self):
        self.phase = "pressure"
        self.pressure = .60
        self.finale_until = self.telegraph_until = 0.0
        self.wall_ready = min(self.wall_ready, self.time + 1)
        self.next_rival_boost = self.time + .6
        self.miss_until = self.time + 2
        self.events.append("finale_miss")

    def _begin_derez(self):
        self.phase = "derez"
        self.derez_time = 0.0
        self.hit_stop = .07
        self.chase_time = self.time
        self._crash_gap = clamp(self.gap, 12, 45)
        self._crash_x = self.rival.x
        self.walls.clear()
        self.rival.energy = 0
        self.events.append("rival_impact")

    def _derez_step(self, dt):
        if self.hit_stop > 0:
            frozen = min(dt, self.hit_stop)
            self.hit_stop = max(0, self.hit_stop - frozen)
            dt -= frozen
        if dt <= 0:
            return
        before = self.derez_time
        self.derez_time += dt
        self.time += dt
        # O jogador continua; a moto avariada desacelera e cresce na projeção.
        self.player.speed += (88 - self.player.speed) * min(1, dt * 2)
        self.player.s += self.player.speed * dt
        progress = clamp(self.derez_time / 1.6, 0, 1)
        self.rival.s = self.player.s + self._crash_gap * (1 - progress) + 9 * progress
        self.rival.x = self._crash_x + math.sin(self.derez_time * 27) * .22 * progress
        self.rival.speed = max(0, self.player.speed * (1 - progress))
        for threshold, event in ((.15, "rival_skid"), (1.2, "rival_overload"),
                                 (1.6, "rival_derez"), (3.0, "rival_tail")):
            if before < threshold <= self.derez_time:
                self.events.append(event)
        if self.derez_time >= DEREZ_SECONDS:
            self.score = max(0, round(12000 - self.chase_time * 35
                             + self.player.energy * 50 - (self.attempts - 1) * 1200))
            self.result = "won"
            self.reason = "Rinzler deresolvido. O caminho para CLU está aberto."

    def advance(self, elapsed, controls=Controls(), paused=False):
        if paused or self.result:
            return
        self.accumulator += clamp(elapsed, 0.0, .25)
        while self.accumulator + 1e-10 >= FIXED_DT and self.result is None:
            self.accumulator -= FIXED_DT
            self._step(FIXED_DT, controls)

    def _drive(self, bike, controls, dt):
        boosted = self.time < bike.boost_until
        cap = BOOST_SPEED if boosted else MAX_SPEED
        acceleration = 32 * clamp(controls.throttle, 0, 1) - 58 * clamp(controls.brake, 0, 1) - 5
        if boosted:
            acceleration += 24
        if abs(bike.x) > 1:
            acceleration -= 34
            cap = min(cap, 66)
        bike.speed = clamp(bike.speed + acceleration * dt, 0, cap)
        steering = clamp(controls.steer, -1, 1) * (0.30 + .95 * bike.speed / MAX_SPEED)
        centrifugal = self.road.curvature(bike.s) * bike.speed**2 * .035
        bike.x = clamp(bike.x + (steering - centrifugal) * dt, -1.48, 1.48)
        bike.s += bike.speed * dt

    def _boost(self, bike, owner):
        if self.time >= bike.boost_ready:
            bike.boost_until = self.time + 1.5
            bike.boost_ready = self.time + (max(4, 8 - self.attempts * .6) if owner == "rival" else 8)
            self.events.append("boost")

    def _hit(self, bike, owner, damage=18):
        if self.time < bike.hit_until:
            return
        bike.hit_until = self.time + .9
        bike.energy = max(0, bike.energy - damage)
        bike.speed *= .64
        self.events.append("impact")
        if owner == "rival":
            self.pressure = min(1, self.pressure + .22)

    def _think(self):
        # Rinzler segue a mesma física, mas só atualiza a direção neste intervalo.
        close = 0 < self.gap < 65
        target_x = math.sin(self.time * (.65 if close else .35)) * (.60 if close else .45)
        if self.phase == "finale":
            target_x = self.rival.x if self.telegraphing else self.target_lane
        for wall in self.walls:
            if wall.owner != "rival" and wall.cut_x is None and 0 < wall.s - self.rival.s < 150:
                target_x = wall.gap_x
        obstacle = next((o for o in self.obstacles if 0 < o.s - self.rival.s < 110), None)
        if self.phase != "finale" and obstacle is not None and abs(target_x - obstacle.x) < .35:
            target_x = -.55 if obstacle.x >= 0 else .55
        # Compensa a curva para que a faixa anunciada seja o destino real do corte.
        drift = self.road.curvature(self.rival.s) * self.rival.speed**2 * .035
        steering_gain = .30 + .95 * self.rival.speed / MAX_SPEED
        response = 5 if self.phase == "finale" else (4.2 if close else 3.5)
        self.ai_steer = clamp(((target_x - self.rival.x) * response + drift) / steering_gain, -1, 1)
        target_speed = (94 if close else 86) + 3 * math.sin(self.time * .31)
        if self.phase == "finale":
            target_speed = 91
        elif self.gap < 12:
            target_speed = 100
        if self.time < self.rival.boost_until:
            target_speed = BOOST_SPEED
        self.ai_throttle = clamp(.15625 + (target_speed - self.rival.speed) * .22, 0, 1)
        self.ai_brake = clamp((self.rival.speed - target_speed - 2) * .06, 0, .35)

    def _step(self, dt, controls):
        if self.phase == "derez":
            self._derez_step(dt)
            return
        self.time += dt
        if controls.boost and not self._boost_held:
            self._boost(self.player, "player")
        if controls.wall and not self._wall_held and self.time >= self.wall_ready:
            if self.phase == "finale" and not self.cut_deployed:
                # A pressão sobrecarrega o emissor: uma lâmina longitudinal corta
                # a faixa escolhida à frente, no ponto da manobra anunciada.
                lead = max(.65, self.telegraph_until - self.time + .80)
                self.walls.append(LightWall(self.rival.s + self.rival.speed * lead,
                    0, "player", self.time, self.time + FINALE_SECONDS,
                    cut_x=clamp(self.player.x, -.80, .80)))
                self.cut_deployed = True
                self.wall_ready = self.time + 7
                self.events.append("wall_on")
            elif self.phase != "finale":
                self.walls.append(LightWall(self.player.s - 5,
                    -.60 if self.player.x >= 0 else .60, "player", self.time, self.time + 5))
                self.wall_ready = self.time + 7
                self.events.append("wall_on")
        self._boost_held, self._wall_held = controls.boost, controls.wall
        if self.time >= self.ai_due:
            self._think()
            self.ai_due = self.time + REACTION_SEC
        if self.phase != "finale" and self.time >= self.next_rival_boost:
            self._boost(self.rival, "rival")
            self.next_rival_boost = self.time + max(5, 10 - self.attempts)
        if self.phase != "finale" and self.time >= self.next_rival_wall:
            self.walls.append(LightWall(self.rival.s + 95,
                -.60 if self.player.x >= 0 else .60, "rival", self.time + .9, self.time + 5.9))
            self.next_rival_wall = self.time + (3.8 if 0 < self.gap < 65 else 8)
            self.events.append("wall_warning")
        for wall in self.walls:
            if self.time - dt < wall.active_at <= self.time:
                self.events.append("wall_on")
        previous = {"player": self.player.s, "rival": self.rival.s}
        self._drive(self.player, controls, dt)
        self._drive(self.rival, Controls(self.ai_steer, self.ai_throttle, self.ai_brake), dt)
        if self.gap > LOST_DISTANCE:
            self.result, self.reason = "lost", "Rinzler escapou pelas Terras Ermas."
            return
        for owner, bike in (("player", self.player), ("rival", self.rival)):
            if abs(bike.x) > 1:
                bike.energy = max(0, bike.energy - 5 * dt)
            for wall in self.walls:
                if (wall.owner != owner and not wall.hit
                    and wall.active_at <= self.time < wall.expires_at
                    and previous[owner] <= wall.s <= bike.s):
                    if wall.cut_x is not None:
                        wall.hit = True
                        if self.phase == "finale":
                            if wall.blocks(bike.x) and self.player.energy > 0:
                                self._begin_derez()
                                return
                            self._miss_finale()
                    elif wall.blocks(bike.x):
                        self._hit(bike, owner)
                        wall.hit = True
            for obstacle in self.obstacles:
                if previous[owner] <= obstacle.s <= bike.s and abs(bike.x - obstacle.x) < obstacle.width + .10:
                    self._hit(bike, owner, 14)
        if abs(self.gap) < 3 and abs(self.player.x - self.rival.x) < .19:
            self._hit(self.player, "player", 10)
            self._hit(self.rival, "rival", 10)
        self.walls = [w for w in self.walls if w.expires_at > self.time]
        for obstacle in self.obstacles:
            if obstacle.s < min(self.player.s, self.rival.s) - 50:
                obstacle.s += 3100
        if self.phase == "finale":
            if self.time >= self.finale_until:
                self._miss_finale()
        else:
            self.phase = "pressure" if self.gap <= SLIPSTREAM_DISTANCE else "reach"
            if self.in_slipstream:
                self.pressure = min(1, self.pressure + dt * (.12 + .18 * (1 - self.gap / SLIPSTREAM_DISTANCE)))
            else:
                self.pressure = max(0, self.pressure - dt * .018)
        self.contact = clamp((LOST_DISTANCE - max(0, self.gap)) / (LOST_DISTANCE - SLIPSTREAM_DISTANCE), 0, 1)
        if self.player.energy <= 0:
            self.result, self.reason = "lost", "Sua moto perdeu toda a energia."
        elif self.pressure >= 1 and self.phase != "finale":
            self._open_finale()

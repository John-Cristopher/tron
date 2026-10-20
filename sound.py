"""Áudio procedural: gera os WAVs na 1ª execução (assets/sounds) e toca com
pygame (recomendado), winsound ou players do sistema.

Quer sons próprios? Basta substituir qualquer .wav da pasta assets/sounds
(os arquivos só são gerados se não existirem)."""
import math
import os
import random
import shutil
import struct
import subprocess
import sys
import wave
from functools import lru_cache

SR = 22050
SOUND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "sounds")


# ---------------------------------------------------------------- síntese
def _osc(kind, ph):
    ph %= 1.0
    if kind == "sine":
        return math.sin(2 * math.pi * ph)
    if kind == "square":
        return 1.0 if ph < 0.5 else -1.0
    if kind == "saw":
        return 2 * ph - 1
    return 4 * abs(ph - 0.5) - 1  # triangle


@lru_cache(maxsize=None)
def tone(freq, dur, kind="square", vol=0.4, end=None, decay=3.0, attack=0.004):
    n = int(SR * dur)
    a = max(1, int(SR * attack))
    ph, out = 0.0, []
    for i in range(n):
        t = i / n
        f = freq if end is None else freq + (end - freq) * t
        ph += f / SR
        out.append(_osc(kind, ph) * min(1.0, i / a) * math.exp(-decay * t) * vol)
    return out


def noise(dur, vol=0.5, decay=4.0):
    n = int(SR * dur)
    return [random.uniform(-1, 1) * math.exp(-decay * i / n) * vol for i in range(n)]


def lowpass(x, a=0.2):
    y, out = 0.0, []
    for v in x:
        y += a * (v - y)
        out.append(y)
    return out


def layer(*parts):
    """Mixa trechos: cada parte é (amostras, início_em_segundos)."""
    total = max(int(s * SR) + len(x) for x, s in parts)
    out = [0.0] * total
    for x, s in parts:
        o = int(s * SR)
        for i, v in enumerate(x):
            out[o + i] += v
    return out


def save_wav(path, samples):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1.0, min(1.0, v)) * 32767)) for v in samples))


def _sfx():
    return {
        "move": lambda: tone(660, 0.05, "square", 0.22, decay=6),
        "select": lambda: layer((tone(520, 0.07, "square", 0.28, decay=4), 0.0),
                                (tone(780, 0.14, "square", 0.28, decay=4), 0.07)),
        "turn": lambda: tone(1400, 0.03, "square", 0.10, end=800, decay=5),
        "beep": lambda: tone(440, 0.20, "sine", 0.55, decay=2.0),
        "go": lambda: layer((tone(660, 0.55, "saw", 0.35, end=1320, decay=1.6), 0.0),
                            (tone(330, 0.55, "sine", 0.40, end=660, decay=1.6), 0.0)),
        "pause": lambda: layer((tone(500, 0.06, "square", 0.25), 0.0),
                               (tone(350, 0.09, "square", 0.25), 0.06)),
        "crash": lambda: layer((lowpass(noise(0.9, 0.95, 3.2), 0.22), 0.0),
                               (tone(190, 0.8, "sine", 0.8, end=32, decay=2.4), 0.0),
                               (tone(900, 0.12, "saw", 0.25, end=100, decay=5), 0.0)),
        "round_win": lambda: layer(*[(tone(f, 0.16, "square", 0.28, decay=3), i * 0.09)
                                     for i, f in enumerate((523, 659, 784, 1047))]),
        "match_win": lambda: layer(*[(tone(f, 0.28, "saw", 0.28, decay=2.2), i * 0.14)
                                     for i, f in enumerate((392, 523, 659, 784, 1047, 1319))]),
        "music": _music,
    }


def _music():
    """Loop synthwave de 4 acordes (Am F C G): baixo, arpejo, bumbo e chimbal."""
    step = 60 / 112 / 2
    minor, major = (1, 1.1892, 1.4983, 2), (1, 1.2599, 1.4983, 2)
    chords = [(110.0, minor), (87.31, major), (130.81, major), (98.0, major)]
    pattern = (0, 1, 2, 3, 2, 1, 2, 1)
    parts, n = [], 0
    for root, tri in chords:
        for i in range(8):
            t = n * step
            parts.append((tone(root / 2, step * 0.95, "saw", 0.30, decay=2.5), t))
            parts.append((tone(round(root * 2 * tri[pattern[i]], 2), step * 1.7, "tri", 0.20, decay=2.5), t))
            parts.append((tone(140, 0.16, "sine", 0.65, end=42, decay=4), t) if i % 2 == 0
                         else (noise(0.05, 0.12, 6), t))
            n += 1
    mixed = layer(*parts)
    size = int(n * step * SR)
    out = mixed[:size]
    for i, v in enumerate(mixed[size:]):   # a "cauda" volta pro início => loop sem clique
        out[i] += v
    return [v * 0.6 for v in out]


# ---------------------------------------------------------------- reprodução
class SoundManager:
    def __init__(self):
        self.sfx_on = True
        self.music_on = True
        self.backend = "none"
        self._paths = {}
        self._sounds = {}
        self._music = None
        self._chan = None
        self._player = None
        try:
            self._ensure_files()
            self._init_backend()
        except Exception as exc:  # áudio nunca deve derrubar o jogo
            print("[som] desativado:", exc)

    @property
    def music_supported(self):
        return self.backend == "pygame"

    def _ensure_files(self):
        os.makedirs(SOUND_DIR, exist_ok=True)
        for name, build in _sfx().items():
            path = os.path.join(SOUND_DIR, name + ".wav")
            if not os.path.exists(path):
                save_wav(path, build())
            self._paths[name] = path

    def _init_backend(self):
        try:
            import pygame
            pygame.mixer.pre_init(SR, -16, 1, 512)
            pygame.mixer.init()
            pygame.mixer.set_num_channels(12)
            pygame.mixer.set_reserved(1)           # canal 0 só para a música
            self.pg = pygame
            self._chan = pygame.mixer.Channel(0)
            self._sounds = {n: pygame.mixer.Sound(p) for n, p in self._paths.items() if n != "music"}
            self._music = pygame.mixer.Sound(self._paths["music"])
            self._music.set_volume(0.35)
            self.backend = "pygame"
            return
        except Exception:
            pass
        if sys.platform == "win32":
            self.backend = "winsound"
        else:
            for exe, args in (("paplay", []), ("aplay", ["-q"]), ("afplay", [])):
                found = shutil.which(exe)
                if found:
                    self._player = [found] + args
                    self.backend = "subprocess"
                    break

    def play(self, name):
        if not self.sfx_on or self.backend == "none" or name not in self._paths:
            return
        try:
            if self.backend == "pygame":
                self._sounds[name].play()
            elif self.backend == "winsound":
                import winsound
                winsound.PlaySound(self._paths[name], winsound.SND_FILENAME | winsound.SND_ASYNC)
            else:
                subprocess.Popen(self._player + [self._paths[name]],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def start_music(self):
        if self.music_on and self.backend == "pygame":
            self._chan.play(self._music, loops=-1)

    def stop_music(self):
        if self.backend == "pygame":
            self._chan.stop()

    def set_music(self, on):
        self.music_on = on
        self.start_music() if on else self.stop_music()

    def toggle_music(self):
        self.set_music(not self.music_on)

    def shutdown(self):
        try:
            if self.backend == "pygame":
                self.pg.mixer.quit()
        except Exception:
            pass
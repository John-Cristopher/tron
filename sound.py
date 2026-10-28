"""Gera efeitos WAV procedurais e carrega clipes em assets/sounds.

Os efeitos em WAV são gerados na 1ª execução; clipes externos ficam preservados."""

import math
import os
import random
import shutil
import subprocess
import sys
import time
import unicodedata
import wave
from array import array
from functools import lru_cache
from pathlib import Path

SR = 22050
SOUND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "sounds")
MUSIC_DIR = os.path.join(os.path.dirname(SOUND_DIR), "music")
COLLISION_SOUNDS = {
    "pilot_scream": "grito piloto.mp3",
    "bike_derez": "deresolucao.mp3",
    "bike_impact": "pancada moto.mp3",
}
MENU_SOUNDS = {
    "menu_move": ("seletor_menu", "move"),
    "menu_select": ("menu", "select"),
}
MUSIC_FADE_SEC = 1.5
MUSIC_TRACK_DURATION_LIMITS = {("game", "Lightbikes Intro"): 15}
MUSIC_PLAYLISTS = {
    "intro": (("Legacy Open",), 0.85, False),
    "chase": (("chase",), 0.65, True),
    "menu": (
        (
            "Encom Tower Part 1",
            "Sam Visits Arcade",
            "Sam Descends To Grid",
            "Rinzler Vs Sam",
            "Portal Climax",
        ),
        0.34,
        True,
    ),
    "pause": (
        (
            "Encom Tower Part 2",
            "Recognizer Capture",
            "Sirens",
            "Solar Sailer",
            "Portal Arrival",
        ),
        0.28,
        True,
    ),
    "game": (
        (
            "Lightbikes Intro",
            "Motochase",
            "Separate Ways",
            "Lightbikes Battle",
            "End Of Line",
            "Party Crashers",
            "Legacy Theme",
        ),
        0.8,
        True,
    ),
    "victory": (("Final Scheme Intro",), 0.8, False),
}


def _normalized_track_name(name):
    stem = os.path.splitext(os.path.basename(name))[0]
    prefix, separator, remainder = stem.partition("-")
    if separator and prefix.strip().isdigit():
        stem = remainder
    normalized = "".join(
        char
        for char in unicodedata.normalize("NFKD", stem.casefold())
        if char.isalnum()
    )
    return {
        "motorchase": "motochase",
        "samdecendstogrid": "samdescendstogrid",
    }.get(normalized, normalized)


def effect_files(directory, names):
    """Resolve nomes e extensões sem distinguir maiúsculas de minúsculas."""
    directory = Path(directory)
    if not directory.is_dir():
        return
    files = {
        path.name.casefold(): path for path in directory.iterdir() if path.is_file()
    }
    for name in names:
        for extension in (".ogg", ".wav", ".mp3"):
            path = files.get((name + extension).casefold())
            if path is not None:
                yield path


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


def crunch(x, drive=3.0, bits=6, hold=3, gain=0.7):
    """Saturação + bitcrush + redução de taxa: deixa o som sujo, digital e com mais punch."""
    q = 2 ** (bits - 1)
    out, v = [], 0.0
    for i, s in enumerate(x):
        if i % hold == 0:
            v = round(math.tanh(s * drive) * q) / q * gain
        out.append(v)
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
        pcm = array("h", (int(max(-1.0, min(1.0, v)) * 32767) for v in samples))
        if sys.byteorder != "little":
            pcm.byteswap()
        w.writeframes(pcm.tobytes())


@lru_cache(maxsize=None)
def sustained_tone(freq, dur, kind="sine", vol=0.1, attack=0.025, release=0.12):
    n = int(SR * dur)
    attack_n = max(1, int(SR * attack))
    release_n = max(1, int(SR * release))
    ph, out = 0.0, []
    for i in range(n):
        ph += freq / SR
        envelope = min(1.0, i / attack_n, (n - i) / release_n)
        out.append(_osc(kind, ph) * max(0.0, envelope) * vol)
    return out


def _midi_freq(note):
    return 440.0 * 2 ** ((note - 69) / 12)


def _shout_voice(freq, dur, volume, pitch_end):
    n = int(SR * dur)
    formants = (650, 1250, 2450)
    harmonics = []
    for harmonic in range(1, 11):
        harmonic_freq = freq * harmonic
        weight = sum(
            math.exp(-0.5 * ((harmonic_freq - center) / (center * 0.32)) ** 2)
            for center in formants
        )
        harmonics.append((harmonic, weight / harmonic))

    phases = [0.0] * len(harmonics)
    samples = []
    attack = max(1, int(SR * 0.06))
    release = max(1, int(SR * 0.18))
    for i in range(n):
        t = i / n
        pitch = freq + (pitch_end - freq) * t
        envelope = min(1.0, i / attack, (n - i) / release)
        voice = 0.0
        for index, (harmonic, weight) in enumerate(harmonics):
            phases[index] += pitch * harmonic / SR
            voice += math.sin(2 * math.pi * phases[index]) * weight
        samples.append(voice * max(0.0, envelope) * volume)
    return samples


def _crowd_reaction(kind):
    rng = random.Random(371 if kind == "gasp" else 917)
    voices = []
    voice_count = 14 if kind == "gasp" else 20
    for _ in range(voice_count):
        freq = rng.uniform(145, 285)
        dur = rng.uniform(0.35, 0.7) if kind == "gasp" else rng.uniform(0.55, 1.05)
        pitch_end = (
            freq * rng.uniform(0.72, 0.9)
            if kind == "gasp"
            else freq * rng.uniform(1.08, 1.28)
        )
        start = rng.uniform(0, 0.45)
        volume = rng.uniform(0.025, 0.055)
        voices.append((_shout_voice(freq, dur, volume, pitch_end), start))

    if kind == "cheer":
        for _ in range(16):
            start = rng.uniform(0.05, 1.0)
            clap = lowpass(noise(0.075, rng.uniform(0.08, 0.16), 16), 0.55)
            voices.append((clap, start))

    mixed = layer(*voices)
    return [math.tanh(sample * 1.5) / math.tanh(1.5) for sample in mixed]


def _music_track(progression, bpm, bars, style):
    beat = 60 / bpm
    bar = beat * 4
    parts = []
    arp_patterns = (
        (0, 2, 1, 2, 3, 2, 1, 2),
        (0, 1, 2, 3, 2, 1, 2, 1),
        (0, 2, 3, 2, 1, 2, 3, 2),
        (0, 1, 3, 2, 1, 3, 2, 1),
    )

    for bar_index in range(bars):
        root, intervals = progression[bar_index % len(progression)]
        start = bar_index * bar
        pattern = arp_patterns[(bar_index // 4) % len(arp_patterns)]
        if style == "game":
            if bar_index < 4 or 16 <= bar_index < 20:
                section, energy = "break", 0.34
            elif bar_index < 8 or 20 <= bar_index < 24:
                section, energy = "build", 0.68
            elif bar_index < 16:
                section, energy = "drop", 1.0
            else:
                section, energy = "final", 1.0
            arp_steps = 8 if section in ("build", "drop", "final") else 4
        else:
            section, energy = "menu", 0.5
            arp_steps = 4

        for interval in intervals:
            parts.append(
                (
                    sustained_tone(
                        _midi_freq(root + interval + (5 if style == "game" else 12)),
                        bar * 0.98,
                        "sine",
                        0.012 if style == "game" else 0.035,
                    ),
                    start,
                )
            )

        for step in range(arp_steps):
            note_index = pattern[step if style == "game" else step * 2]
            note = root + intervals[note_index] + (0 if style == "game" else 12)
            note_time = start + step * (beat / 2 if style == "game" else beat)
            note_length = beat * (0.44 if style == "game" else 0.72)
            if style == "game":
                volume = 0.034 if section == "break" else 0.05 + 0.02 * energy
                parts.append(
                    (
                        tone(
                            _midi_freq(note),
                            note_length,
                            "saw",
                            volume,
                            decay=2.8,
                            attack=0.008,
                        ),
                        note_time,
                    )
                )
            else:
                parts.append(
                    (
                        tone(
                            _midi_freq(note),
                            note_length,
                            "tri",
                            0.055,
                            decay=3.2,
                            attack=0.006,
                        ),
                        note_time,
                    )
                )

        if style == "game":
            if section in ("drop", "final"):
                for interval in (
                    intervals[0],
                    intervals[2],
                    intervals[1],
                    intervals[3],
                ):
                    parts.append(
                        (
                            sustained_tone(
                                _midi_freq(root + interval + 19),
                                beat * 0.2,
                                "saw",
                                0.035,
                                attack=0.004,
                                release=0.1,
                            ),
                            start + beat * 0.5,
                        )
                    )

            bass_pattern = (0, 0, 7, 0, 0, 7, 10, 7)
            bass_steps = (
                8 if section in ("drop", "final") else (4 if section == "build" else 2)
            )
            for step in range(bass_steps):
                note = root - 12 + bass_pattern[step]
                bass_time = start + step * (beat / 2 if bass_steps == 8 else beat)
                bass_length = beat * (0.38 if bass_steps == 8 else 0.72)
                parts.append(
                    (
                        crunch(
                            tone(
                                _midi_freq(note),
                                bass_length,
                                "saw",
                                1.0,
                                decay=2.2,
                                attack=0.006,
                            ),
                            2.5,
                            8,
                            2,
                            0.105 if section in ("drop", "final") else 0.065,
                        ),
                        bass_time,
                    )
                )

            if section in ("drop", "final"):
                lead_notes = (3, 2, 1, 2, 3, 1, 2, 0)
                lead_shift = 12 if section == "drop" else 14
                for offset, index in ((0.5, 0), (1.5, 1), (2.5, 2), (3.5, 3)):
                    note = (
                        root
                        + intervals[lead_notes[(bar_index + index) % len(lead_notes)]]
                        + lead_shift
                    )
                    parts.append(
                        (
                            tone(
                                _midi_freq(note),
                                beat * 0.38,
                                "saw",
                                0.042,
                                decay=2.0,
                                attack=0.012,
                            ),
                            start + offset * beat,
                        )
                    )

            if section in ("build", "drop", "final"):
                for beat_index in range(4):
                    hit_time = start + beat_index * beat
                    kick_volume = 0.25 if section == "build" else 0.38
                    parts.append(
                        (
                            tone(96, 0.30, "sine", kick_volume, end=34, decay=4.8),
                            hit_time,
                        )
                    )
                    parts.append(
                        (
                            tone(
                                180,
                                0.11,
                                "saw",
                                0.11 if section == "build" else 0.18,
                                end=52,
                                decay=8,
                                attack=0.001,
                            ),
                            hit_time,
                        )
                    )
                    if beat_index in (1, 3) and section != "build":
                        parts.append((lowpass(noise(0.16, 0.24, 5), 0.42), hit_time))
                        parts.append(
                            (tone(150, 0.12, "sine", 0.12, end=72, decay=5), hit_time)
                        )
                    parts.append(
                        (
                            noise(0.045, 0.05 if section == "build" else 0.07, 8),
                            hit_time + beat * 0.5,
                        )
                    )
                if section in ("drop", "final"):
                    for beat_index in range(4):
                        parts.append(
                            (noise(0.045, 0.055, 10), start + beat_index * beat)
                        )
            else:
                parts.append((tone(62, 0.28, "sine", 0.08, end=42, decay=5), start))
                for beat_index in (1, 3):
                    parts.append((noise(0.045, 0.025, 8), start + beat_index * beat))
        else:
            parts.append((tone(62, 0.28, "sine", 0.12, end=42, decay=5), start))
            for beat_index in (1, 3):
                parts.append((noise(0.045, 0.025, 8), start + beat_index * beat))

    mixed = layer(*parts)
    size = int(bars * bar * SR)
    out = mixed[:size]
    for i, sample in enumerate(mixed[size:]):
        out[i] += sample
    if style == "game":
        # Sidechain "pumping" do electro francês: o volume afunda a cada batida e volta
        beat_n = beat * SR
        return [
            math.tanh(sample * 1.8)
            / math.tanh(1.8)
            * (0.5 + 0.5 * min(1.0, (i % beat_n) / (beat_n * 0.45)))
            for i, sample in enumerate(out)
        ]
    gain = 0.88
    return [sample * gain for sample in out]


def _music():
    """Trilha electro original grave, sombria, com pausas e batida pesada."""
    progression = (
        (45, (0, 3, 7, 10)),
        (41, (0, 3, 7, 10)),
        (38, (0, 3, 7, 10)),
        (40, (0, 4, 7, 11)),
    )
    return _music_track(progression, bpm=116, bars=32, style="game")


def _menu_music():
    """Trilha ambiente original para o menu, com 24 compassos e cerca de 60 segundos."""
    progression = (
        (48, (0, 4, 7, 11)),
        (45, (0, 3, 7, 10)),
        (41, (0, 4, 7, 11)),
        (43, (0, 4, 7, 9)),
    )
    return _music_track(progression, bpm=96, bars=24, style="menu")


def _sfx():
    """Sons arcade sci-fi com transientes curtos e impacto grave em camadas."""
    return {
        # Movimento é seco e discreto para não competir com a trilha.
        "move": lambda: layer(
            (tone(920, 0.035, "square", 0.10, end=620, decay=10), 0.0),
            (tone(1840, 0.018, "sine", 0.045, end=1200, decay=14), 0.0),
        ),
        "select": lambda: layer(
            (tone(620, 0.055, "sine", 0.20, end=840, decay=7), 0.0),
            (tone(1240, 0.085, "tri", 0.12, end=1560, decay=8), 0.035),
        ),
        "intro_scan": lambda: layer(
            (tone(330,.65,"sine",.12,end=1760,decay=1.4),0),
            (lowpass(noise(.4,.08,3),.1),.02)),
        "turn": lambda: layer(
            (
                crunch(
                    tone(1550, 0.05, "saw", 0.5, end=620, decay=10), 2.5, 5, 2, 0.12
                ),
                0.0,
            ),
            (tone(780, 0.035, "sine", 0.07, end=440, decay=12), 0.0),
        ),
        "beep": lambda: layer(
            (tone(660, 0.16, "sine", 0.32, end=520, decay=4), 0.0),
            (tone(1320, 0.07, "square", 0.10, decay=9), 0.0),
        ),
        "go": lambda: layer(
            (
                crunch(
                    tone(420, 0.42, "saw", 0.6, end=1180, decay=2.8), 2.2, 6, 2, 0.26
                ),
                0.0,
            ),
            (tone(210, 0.48, "sine", 0.30, end=520, decay=2.3), 0.0),
            (tone(1760, 0.11, "sine", 0.10, end=1100, decay=7), 0.20),
        ),
        "pause": lambda: layer(
            (tone(680, 0.08, "square", 0.16, end=460, decay=6), 0.0),
            (tone(360, 0.13, "sine", 0.18, end=220, decay=5), 0.06),
        ),
        # Fogos: estouro grave + estalos crocantes espalhados.
        "firework": lambda: layer(
            (tone(110, 0.3, "sine", 0.45, end=38, decay=6), 0.0),
            (crunch(noise(0.14, 1.0, 9), 3.0, 5, 2, 0.32), 0.0),
            *[
                (crunch(noise(0.035, 1.0, 12), 3.0, 4, 3, 0.16), s)
                for s in (0.11, 0.16, 0.19, 0.26, 0.3, 0.37, 0.45, 0.5, 0.61)
            ]
        ),
        "round_win": lambda: layer(
            *[
                (tone(f, 0.19, "square", 0.22, end=f * 1.015, decay=3.5), i * 0.105)
                for i, f in enumerate((523, 659, 784, 1047))
            ]
        ),
        "match_win": lambda: layer(
            *[
                (tone(f, 0.30, "saw", 0.23, end=f * 1.02, decay=2.5), i * 0.13)
                for i, f in enumerate((392, 523, 659, 784, 1047, 1319))
            ]
        ),
    }


# ---------------------------------------------------------------- reprodução
class SoundManager:
    def __init__(self):
        self.sfx_on = True
        self.music_on = True
        self.music_level = 1.0  # volume da música (0..1), ajustável no menu de pausa
        self.sfx_level = 1.0  # volume dos efeitos (0..1); 0 desliga os efeitos
        self.engine_level = 1.0
        self._intro_menu_tail = False
        self._base_volume = {}
        self.backend = "none"
        self._paths = {}
        self._crowd_mp3_paths = {}
        self._sounds = {}
        self._current_music = "menu"
        self._active_music = None
        self._music_playlists = {}
        self._music_positions = {}
        self._music_remaining = {}
        self._music_index = 0
        self._music_duration_ms = 0
        self._music_phase = "idle"
        self._music_fade_started = 0.0
        self._music_fade_from = 0.0
        self._music_volume = 0.0
        self._music_next_index = None
        self._music_stop_after_fade = False
        self._crowd_channels = {}
        self._crowd_processes = {"crowd_gasp": [], "crowd_cheer": []}
        self._player = None
        self._last_play = {}
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
        marker = os.path.join(SOUND_DIR, ".soundset_v4")
        rebuild = not os.path.exists(marker)
        for name, build in _sfx().items():
            path = os.path.join(SOUND_DIR, name + ".wav")
            if rebuild or not os.path.exists(path):
                save_wav(path, build())
            self._paths[name] = path
        for name, (stem, fallback) in MENU_SOUNDS.items():
            custom = next(effect_files(SOUND_DIR, (stem,)), None)
            self._paths[name] = str(custom) if custom else self._paths[fallback]
        for index in range(1, 4):
            name = f"firework_{index}"
            custom = next(effect_files(SOUND_DIR, (name,)), None)
            if custom is not None:
                self._paths[name] = str(custom)
        self._paths["intro_portal"] = self._paths["go"]
        for name, filename in COLLISION_SOUNDS.items():
            path = os.path.join(SOUND_DIR, filename)
            if os.path.isfile(path):
                self._paths[name] = path
            else:
                print("[som] áudio de colisão não encontrado:", path)
        for name, reaction in (("crowd_gasp", "gasp"), ("crowd_cheer", "cheer")):
            path = os.path.join(SOUND_DIR, name + ".wav")
            if not os.path.exists(path):
                save_wav(path, _crowd_reaction(reaction))
            self._paths[name] = path
            mp3_path = os.path.join(SOUND_DIR, name + ".mp3")
            if os.path.isfile(mp3_path):
                self._crowd_mp3_paths[name] = mp3_path
        with open(marker, "w", encoding="utf-8") as f:
            f.write("2\n")

        music_marker = os.path.join(SOUND_DIR, ".musicset_v4")
        rebuild_music = not os.path.exists(music_marker)
        for name, build in (("music", _music), ("menu_music", _menu_music)):
            path = os.path.join(SOUND_DIR, name + ".wav")
            if rebuild_music or not os.path.exists(path):
                save_wav(path, build())
            self._paths[name] = path
        with open(music_marker, "w", encoding="utf-8") as f:
            f.write("1\n")

    def _resolve_music_playlists(self):
        files = {}
        for directory in (SOUND_DIR, MUSIC_DIR):
            if not os.path.isdir(directory):
                continue
            for filename in sorted(os.listdir(directory)):
                if os.path.splitext(filename)[1].lower() not in (
                    ".ogg",
                    ".mp3",
                    ".wav",
                ):
                    continue
                path = os.path.join(directory, filename)
                if os.path.isfile(path):
                    files[_normalized_track_name(filename)] = path

        playlists = {}
        for context, (names, gain, loop) in MUSIC_PLAYLISTS.items():
            tracks = []
            for name in names:
                path = files.get(_normalized_track_name(name))
                if path is None:
                    if context != "chase":
                        print("[som] faixa não encontrada:", name)
                else:
                    tracks.append((name, path))
            if not tracks and context in ("menu", "game", "pause"):
                fallback = "menu_music" if context in ("menu", "pause") else "music"
                tracks.append((fallback, self._paths[fallback]))
                print("[som] usando trilha procedural como alternativa:", context)
            playlists[context] = (tracks, gain, loop)
        if not playlists["chase"][0]:
            _, gain, loop = playlists["chase"]
            playlists["chase"] = (list(playlists["game"][0]), gain, loop)
            print("[som] perseguição: usando a playlist da partida.")
        return playlists

    def _trim_start(self, sound):
        """Corta o silêncio do começo: seletor_menu.WAV soava 30 ms depois do destaque."""
        try:
            channels = int(self.pg.mixer.get_init()[2])
            samples = memoryview(sound.get_raw()).cast("h")
        except (TypeError, ValueError):  # formato inesperado: usa o som como veio
            return sound
        peak = max(map(abs, samples), default=0)
        first = next((i for i, v in enumerate(samples) if abs(v) > peak * 0.05), 0)
        first -= first % channels
        if first == 0:
            return sound
        return self.pg.mixer.Sound(buffer=samples[first:].tobytes())

    def _load_effects(self):
        self._sounds = {}
        for name, path in self._paths.items():
            if name in ("music", "menu_music"):
                continue
            paths = [self._crowd_mp3_paths.get(name, path)]
            if paths[0] != path:
                paths.append(path)
            if name in MENU_SOUNDS:
                paths.append(self._paths[MENU_SOUNDS[name][1]])
            for candidate in paths:
                try:
                    sound = self.pg.mixer.Sound(candidate)
                    if name in MENU_SOUNDS:
                        sound = self._trim_start(sound)
                    self._sounds[name] = sound
                    self._paths[name] = candidate
                    break
                except Exception:
                    continue

    def _init_backend(self):
        try:
            import pygame

            pygame.mixer.pre_init(SR, -16, 1, 512)
            pygame.mixer.init()
            pygame.mixer.set_num_channels(12)
            pygame.mixer.set_reserved(
                3
            )  # reserva os canais usados pelas reações da plateia
            self.pg = pygame
            self._load_effects()
            self._crowd_channels = {
                "crowd_gasp": pygame.mixer.Channel(1),
                "crowd_cheer": pygame.mixer.Channel(2),
            }
            for name, snd in self._sounds.items():
                self._base_volume[name] = {
                    "move": 0.42,
                    "menu_move": 0.42,
                    "menu_select": 0.68,
                    "intro_portal": 0.15,
                    "intro_scan": 0.32,
                    "turn": 0.55,
                    "pilot_scream": 0.2,
                    "bike_derez": 0.42,
                    "bike_impact": 0.45,
                    "crowd_gasp": 1.0,
                    "crowd_cheer": 1.0,
                }.get(name, 0.68)
                snd.set_volume(self._base_volume[name] * self.sfx_level)
            self._music_playlists = self._resolve_music_playlists()
            self.backend = "pygame"
            return
        except Exception as exc:
            print("[som] pygame indisponível:", exc)
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
        # Evita rajadas de sons idênticos caso uma tecla gere eventos repetidos.
        now = __import__("time").monotonic()
        cooldown = (
            0.07 if name in MENU_SOUNDS else 0.035 if name in ("move", "turn") else 0.0
        )
        if now - self._last_play.get(name, -1e9) < cooldown:
            return
        self._last_play[name] = now
        sound_name = name
        if name == "firework" and self.backend == "pygame":
            variants = [
                f"firework_{index}"
                for index in range(1, 4)
                if f"firework_{index}" in self._sounds
            ]
            if variants:
                sound_name = random.choice(variants)
        try:
            if self.backend == "pygame":
                if sound_name not in self._sounds:
                    return
                if name in MENU_SOUNDS:
                    self.pg.mixer.Channel(0).play(self._sounds[sound_name])
                elif name in self._crowd_channels:
                    self._crowd_channels[name].play(self._sounds[sound_name])
                else:
                    self._sounds[sound_name].play()
            elif self.backend == "winsound":
                import winsound

                winsound.PlaySound(
                    self._paths[sound_name], winsound.SND_FILENAME | winsound.SND_ASYNC
                )
            else:
                process = subprocess.Popen(
                    self._player + [self._paths[sound_name]],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                if name in self._crowd_processes:
                    active = [
                        p for p in self._crowd_processes[name] if p.poll() is None
                    ]
                    active.append(process)
                    self._crowd_processes[name] = active
        except Exception:
            pass

    def stop_crowd(self):
        if self.backend == "pygame":
            for channel in self._crowd_channels.values():
                channel.stop()
        elif self.backend == "winsound":
            import winsound

            winsound.PlaySound(None, 0)
        elif self.backend == "subprocess":
            for processes in self._crowd_processes.values():
                for process in processes:
                    if process.poll() is None:
                        process.terminate()
                processes.clear()

    def start_music(self, track=None):
        if track is not None:
            self.set_music_track(track)
            return
        self._music_stop_after_fade = False
        if (
            self.music_on
            and self.backend == "pygame"
            and self._music_phase == "idle"
            and self._active_music is None
        ):
            self._start_music_track(self._current_music)

    def set_music_track(self, track, restart=False):
        self._intro_menu_tail = False
        if track not in MUSIC_PLAYLISTS:
            raise ValueError("Trilha desconhecida: " + track)
        if track == self._current_music and not restart:
            self.start_music()
            return
        if not (restart and track == self._current_music):
            self._save_music_position()
        if restart:
            self._music_positions.pop(track, None)
            self._music_remaining.pop(track, None)
            if track == "game":
                self._refill_music_queue(track, first_game_track=True)
        self._current_music = track
        if track == "victory":
            self._music_positions.pop(track, None)
        self._music_next_index = None
        self._music_stop_after_fade = False
        if self.music_on and self.backend == "pygame":
            if self._music_phase == "fade_out":
                return
            if self.pg.mixer.music.get_busy():
                self._begin_music_fade_out()
            else:
                self.pg.mixer.music.stop()
                self._active_music = None
                self._music_phase = "idle"
                self._start_music_track(track)

    def enter_menu_music(self, preserve_intro=False):
        """O menu pode assumir a tela sem interromper o restante de Legacy Open."""
        if (
            (preserve_intro or self._intro_menu_tail)
            and self._active_music == "intro"
            and self._music_phase != "fade_out"
        ):
            self._intro_menu_tail = True
            return
        self.set_music_track("menu")

    def start_intro_music(self, start=0.0):
        """Inicia Legacy Open em `start` segundos, sem aguardar uma transição da música do menu."""
        self._intro_start = start
        self._current_music = "intro"
        self._intro_menu_tail = False
        self._music_positions.pop("intro", None)
        self._music_remaining.pop("intro", None)
        self._music_stop_after_fade = False
        if self.backend != "pygame" or not self.music_on:
            return False
        self.pg.mixer.music.stop()
        self._active_music = None
        self._music_phase = "idle"
        self._music_next_index = None
        self._start_music_track("intro", index=0, position_ms=round(start * 1000))
        return self._active_music == "intro"

    def intro_position(self):
        """Segundos efetivamente reproduzidos; None permite a alternativa sem áudio."""
        if self.backend != "pygame" or self._active_music != "intro":
            return None
        position = self.pg.mixer.music.get_pos()
        if position < 0 or not self.pg.mixer.music.get_busy():
            return None
        # get_pos() conta desde o play(), sem incluir o ponto de início
        return getattr(self, "_intro_start", 0.0) + position / 1000

    def _save_music_position(self):
        if self.backend != "pygame" or self._active_music is None:
            return
        if self.pg.mixer.music.get_busy():
            position = max(0, self.pg.mixer.music.get_pos())
            self._music_positions[self._active_music] = (self._music_index, position)

    def _music_target_volume(self, context):
        _, gain, _ = self._music_playlists[context]
        return 0.28 * self.music_level * gain

    def _refill_music_queue(self, context, first_game_track=False, previous=None):
        tracks, _, loop = self._music_playlists[context]
        if not loop:
            self._music_remaining[context] = []
            return

        candidates = list(range(len(tracks)))
        if context == "game" and len(candidates) > 1:
            candidates.remove(0)
        if previous in candidates and len(candidates) > 1:
            candidates.remove(previous)
        random.shuffle(candidates)
        if first_game_track and context == "game" and tracks:
            candidates.insert(0, 0)
        self._music_remaining[context] = candidates

    def _draw_next_music_index(self, context, previous):
        if not self._music_remaining.get(context):
            self._refill_music_queue(context, previous=previous)
        remaining = self._music_remaining.get(context, [])
        return remaining.pop(0) if remaining else None

    def _start_music_track(self, context, index=None, position_ms=None):
        tracks, _, loop = self._music_playlists[context]
        if not tracks:
            self._active_music = None
            self._music_phase = "idle"
            return

        if index is None:
            saved_position = self._music_positions.get(context)
            if saved_position is not None:
                index, saved_ms = saved_position
                if position_ms is None:
                    position_ms = saved_ms
            else:
                if loop:
                    if not self._music_remaining.get(context):
                        self._refill_music_queue(
                            context, first_game_track=context == "game"
                        )
                    index = self._music_remaining[context].pop(0)
                else:
                    index = 0
        if position_ms is None:
            position_ms = 0
        if index < 0 or index >= len(tracks):
            index = 0

        for attempt in range(len(tracks)):
            if attempt == 0:
                track_index = index
            else:
                track_index = self._draw_next_music_index(context, index)
                if track_index is None:
                    break
            name, path = tracks[track_index]
            try:
                self.pg.mixer.music.load(path)
                self._music_duration_ms = int(
                    self.pg.mixer.Sound(path).get_length() * 1000
                )
                duration_limit = MUSIC_TRACK_DURATION_LIMITS.get((context, name))
                if duration_limit is not None:
                    self._music_duration_ms = min(
                        self._music_duration_ms, duration_limit * 1000
                    )
                if position_ms >= self._music_duration_ms:
                    position_ms = 0
                self.pg.mixer.music.set_volume(0.0)
                self.pg.mixer.music.play(loops=0, start=position_ms / 1000)
            except self.pg.error as exc:
                print("[som] não foi possível reproduzir", name + ":", exc)
                position_ms = 0
                continue

            self._music_index = track_index
            self._active_music = context
            self._music_positions[context] = (track_index, position_ms)
            if track_index in self._music_remaining.get(context, []):
                self._music_remaining[context].remove(track_index)
            self._music_phase = "fade_in"
            self._music_fade_started = time.monotonic()
            self._music_fade_from = 0.0
            self._music_volume = 0.0
            self._music_next_index = None
            return

        print("[som] nenhuma faixa reproduzível na lista:", context)
        self._active_music = None
        self._music_phase = "idle"

    def _begin_music_fade_out(self, next_index=None):
        if not self.pg.mixer.music.get_busy():
            self.pg.mixer.music.stop()
            self._active_music = None
            self._music_phase = "idle"
            if next_index == -1:
                self._music_positions.pop(self._current_music, None)
            elif self.music_on and not self._music_stop_after_fade:
                self._start_music_track(self._current_music, index=next_index)
            return
        self._music_next_index = next_index
        self._music_fade_from = self._music_volume
        self._music_fade_started = time.monotonic()
        self._music_phase = "fade_out"

    def _next_music_index(self):
        _, _, loop = self._music_playlists[self._active_music]
        if not loop:
            return -1
        return self._draw_next_music_index(self._active_music, self._music_index)

    def update_music(self):
        if self.backend != "pygame" or self._active_music is None:
            return

        if (
            self._intro_menu_tail
            and self._active_music == "intro"
            and self._music_phase != "fade_out"
        ):
            if not self.pg.mixer.music.get_busy():
                self.set_music_track("menu")
                return

        now = time.monotonic()
        elapsed = now - self._music_fade_started
        fade_progress = min(1.0, elapsed / MUSIC_FADE_SEC)

        if self._music_phase == "fade_in":
            self._music_volume = (
                self._music_target_volume(self._active_music) * fade_progress
            )
            self.pg.mixer.music.set_volume(self._music_volume)
            if fade_progress >= 1.0:
                self._music_phase = "playing"
        elif self._music_phase == "fade_out":
            self._music_volume = self._music_fade_from * (1.0 - fade_progress)
            self.pg.mixer.music.set_volume(self._music_volume)
            if fade_progress >= 1.0:
                if self._music_next_index is None:
                    self._save_music_position()
                self.pg.mixer.music.stop()
                self._active_music = None
                self._music_phase = "idle"
                next_index = self._music_next_index
                self._music_next_index = None
                if next_index == -1:
                    self._music_positions.pop(self._current_music, None)
                elif self.music_on and not self._music_stop_after_fade:
                    self._start_music_track(self._current_music, index=next_index)
            return

        if not self.pg.mixer.music.get_busy():
            if self._music_phase == "playing":
                next_index = self._next_music_index()
                if next_index == -1 or next_index is None:
                    self._active_music = None
                    self._music_phase = "idle"
                else:
                    self._start_music_track(
                        self._active_music, index=next_index, position_ms=0
                    )
            return

        if self._music_phase == "playing":
            position = self.pg.mixer.music.get_pos()
            if (
                position >= 0
                and not (self._intro_menu_tail and self._active_music == "intro")
                and self._music_duration_ms - position <= MUSIC_FADE_SEC * 1000
            ):
                next_index = self._next_music_index()
                self._begin_music_fade_out(next_index)

    def stop_music(self):
        if self.backend == "pygame":
            self._save_music_position()
            self._music_stop_after_fade = True
            self._begin_music_fade_out()

    def set_music(self, on):
        self.music_on = on
        if on:
            self.start_music()
        else:
            self.stop_music()

    def set_music_level(self, level):
        """Volume da música de 0 a 1 (só com pygame)."""
        self.music_level = max(0.0, min(1.0, level))
        if self.backend == "pygame" and self._active_music is not None:
            if self._music_phase == "playing":
                self._music_volume = self._music_target_volume(self._active_music)
                self.pg.mixer.music.set_volume(self._music_volume)

    def set_sfx_level(self, level):
        """Volume dos efeitos de 0 a 1. Sem pygame não há volume: 0 desliga e qualquer outro valor liga."""
        self.sfx_level = max(0.0, min(1.0, level))
        self.sfx_on = self.sfx_level > 0
        for name, snd in self._sounds.items():
            snd.set_volume(self._base_volume.get(name, 0.68) * self.sfx_level)

    def set_engine_level(self, level):
        self.engine_level = max(0.0, min(1.0, level))

    def toggle_music(self):
        self.set_music(not self.music_on)

    def shutdown(self):
        try:
            if self.backend == "pygame":
                self.pg.mixer.quit()
        except Exception:
            pass

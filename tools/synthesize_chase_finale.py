"""Efeitos originais do finale. Execute para repor WAVs ausentes sem sobrescrever clipes."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sound import tone, noise, lowpass, crunch, layer, save_wav


def main():
    output = Path(__file__).resolve().parents[1] / "assets" / "chase"
    output.mkdir(exist_ok=True)
    effects = {
        "finale_ready": lambda: layer((tone(880, .12, "sine", .24), 0),
                                      (tone(1320, .20, "sine", .21), .13)),
        "finale_miss": lambda: tone(440, .28, "triangle", .25, end=130, decay=4),
        "rival_impact": lambda: layer((crunch(noise(.12, .4, 12), hold=6), 0),
            (tone(2200, .07, "square", .22, end=120, decay=10), 0),
            (tone(95, .18, "sine", .35, end=40, decay=8), 0)),
        "rival_skid": lambda: layer((tone(420, 1.03, "sine", .17, end=1900, decay=.2), 0),
            (lowpass(noise(.9, .12, .7), .18), .04)),
        "rival_overload": lambda: layer((tone(1900, .4, "sine", .18, end=3200, decay=.2), 0),
            (crunch(tone(720, .35, "saw", .12, end=1800, decay=.4), bits=5), 0)),
        "rival_derez": lambda: layer((tone(95, .95, "sine", .48, end=27, decay=4), 0),
            (lowpass(noise(.5, .4, 8), .13), 0),
            *((tone(1700 + i * 213, .22, "sine", .085, end=800 + i * 137, decay=9),
               .10 + i * .065) for i in range(12))),
        "rival_tail": lambda: tone(58, .24, "sine", .28, end=28, decay=12),
    }
    for name, synthesize in effects.items():
        path = output / (name + ".wav")
        if not path.exists():
            save_wav(str(path), synthesize())
            print(path.name)


if __name__ == "__main__":
    main()

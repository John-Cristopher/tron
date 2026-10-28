"""
intro.py - Animação de introdução "Flynn apresenta a Grade" (Tkinter Canvas).

Uso:
    from intro import Intro
    intro = Intro(root, canvas, on_done=mostrar_menu, on_sound=tocar_som)
    intro.start()
    # em qualquer lugar (ex.: leitura do controle):  intro.skip()

Fases sincronizadas com Legacy Open:
    0 - 20 s    pulado: a intro começa em INTRO_START (música e relógio juntos)
    20 - 34 s   CLI âmbar e narração, com digitação variável
    34 - 36.8 s varredura ciano e cubos revelam a cidade sob o terminal
    34 - 42 s   Grade e torres se constroem progressivamente
    38 - 43 s   câmera avança pela cidade
    43 - 46 s   o olhar sobe até o pórtico do título no mesmo cenário
    46 s        título TRON extrudado em perspectiva
    50 - 61.5 s câmera entra pela abertura do O, revelando o menu
    62 s        título, botões e plateia acendem; Legacy Open continua até o fim

Tudo é baseado em tempo (perf_counter), então a velocidade é a mesma
em qualquer PC. Os itens do Canvas são criados uma vez e só atualizados
com coords()/itemconfig() a cada frame (sem delete("all")).
"""

from bisect import bisect_right
import math
import time
import tkinter as tk
import theme as T
from intro_logo import Logo3D
from intro_world import IntroWorld, LOGO_ORIGIN, LOGO_SCALE, LOGO_TIME
from intro_portal import IntroPortal
from intro_terminal import Terminal, REZ_START, REZ_END

# ---------- tema compartilhado ----------
BG, CYAN, CORE = T.BACKGROUND, T.CYAN, T.CORE
FONT_MONO = (T.FONT, 18)

# Trecho fornecido pelo usuário; as quebras são apenas para a apresentação no CLI.
LINES = [
    "A Grade.",
    "Uma fronteira digital",
    "Eu tentava imaginar grupos de informações",
    "enquanto se moviam pelo computador.",
    "Com o que se pareciam?",
    "Navios? Motocicletas?",
    "Os circuitos seriam como autoestradas?",
    "Eu continuei sonhando com um mundo que pensei que nunca veria.",
    "E então, um dia...",
]

# Início da intro dentro de Legacy Open: corta a parte longa do texto mantendo a sincronia.
INTRO_START = 20.0
T_TERM_END = REZ_END
T_TITLE_START = LOGO_TIME
T_TITLE_END = 62.0
TYPE_SPEED = 12.0
LINE_PAUSES = (1.0, 1.2, 0.2, 1.0, 0.8, 1.0, 1.0, 0.9, 1.4)


def _typing_cues():
    cues, clock = [], .8
    for row, (line, pause) in enumerate(zip(LINES, LINE_PAUSES)):
        for index, char in enumerate(line):
            # Variação determinista: nenhuma nova aleatoriedade ou timer por tecla.
            clock += (.66 + .50 * (.5 + .5 * math.sin(row * 11.7 + index * 2.3))) / TYPE_SPEED
            if index and line[index-1] == ".":
                clock += .20
            cues.append((clock, row, index + 1))
        clock += pause
    first = INTRO_START + .8
    scale = (32.5 - first) / (cues[-1][0] - .8)
    return tuple((first + (at-.8)*scale,row,count) for at,row,count in cues)


TYPE_CUES = _typing_cues()
TYPE_TIMES = tuple(cue[0] for cue in TYPE_CUES)


def terminal_text(elapsed):
    """Ritmo variável e pausas nas reticências; o inglês permanece configurável."""
    index = bisect_right(TYPE_TIMES, elapsed) - 1
    if index < 0:
        return ""
    _, row, shown = TYPE_CUES[index]
    return "\n".join([*LINES[:row], LINES[row][:shown]])


# Mantém a mesma mistura de cores usada nos outros renderizadores.
mix = T.blend


def ease_in_out(t):
    t = max(0, min(1, t))
    return 3 * t * t - 2 * t * t * t


class Intro:
    def __init__(
        self, root, canvas, on_done, on_sound=None, fps=60, on_start=None, timeline=None
    ):
        self.root = root
        self.c = canvas
        self.c.configure(bg=BG)
        self.on_done = on_done
        self.on_sound = on_sound or (lambda name: None)
        self.on_start, self.timeline = on_start, timeline
        self.dt_ms = int(1000 / fps)

        self.running = False
        self.skipping = False
        self.skip_t0 = 0.0
        self.t0 = 0.0
        self._after_id = None

        self.w = self.h = 0
        self.horizon = 0
        self.cam_z = 0.0
        self._key_id = self._click_id = None
        self._completed = False
        self._elapsed = 0.0
        self._clock_anchor = None
        self._typed = 0

    # ------------------------------------------------------------ API
    def start(self):
        if self.running:
            return
        c = self.c
        c.configure(bg=BG)
        c.update_idletasks()
        self.w = c.winfo_width()
        self.h = c.winfo_height()
        self.cam_z = 0.0
        self.skipping = self._completed = False

        c.configure(bg=BG)
        c.delete("intro")
        self._build_items()

        self._key_id = self.root.bind("<Key>", self._on_key, add="+")
        self._click_id = self.root.bind("<Button-1>", self._on_key, add="+")

        self.running = True
        if self.on_start is not None:
            self.on_start(INTRO_START)
        self.t0 = time.perf_counter()
        self._elapsed, self._clock_anchor, self._typed = INTRO_START, None, 0
        self._tick()

    def skip(self):
        """Pula a animação com um fade rápido. Seguro de chamar várias vezes."""
        if self.running and not self.skipping:
            self.skipping = True
            self.skip_t0 = time.perf_counter()

    # ------------------------------------------------------------ itens
    def _build_items(self):
        c, w, h = self.c, self.w, self.h
        self.terminal = Terminal(c, w, h)
        self.term = self.terminal.term
        self.terminal_visible = True
        self.rez_sounded = False
        self.world = IntroWorld(c, w, h)
        self.portal = IntroPortal(c, w, h)
        self.portal_sounded = False
        self.logo3d = Logo3D(c, w, h)
        self.fade = c.create_rectangle(
            0, 0, w, h, fill=BG, outline="", state="hidden", tags="intro"
        )
        self._build_atmosphere()
        self.hint_bg = c.create_rectangle(w - min(w * .90, 570), h - 52, w - 16, h - 12,
            fill=BG, outline="", tags="intro")
        self.hint = c.create_text(
            w - 30,
            h - 24,
            anchor="se",
            fill=T.MUTED,
            font=(T.FONT, 12),
            text="tecla, clique ou bot\u00e3o do controle para pular",
            tags="intro",
        )

    # ------------------------------------------------------------ loop
    def _build_atmosphere(self):
        self.speed_rays = [self.c.create_line(0,0,0,0,fill=CYAN,width=1,
                          state="hidden",tags="intro") for _ in range(28)]
        self.flare = [self.c.create_line(0,0,0,0,fill=color,width=weight,
                      state="hidden",tags="intro") for color,weight in T.glow_layers(CYAN,2)]
        self.cross_flash = self.c.create_rectangle(0,0,self.w,self.h,fill=CORE,
                            outline="",state="hidden",tags="intro")

    def _atmosphere(self,t):
        c,w,h = self.c,self.w,self.h
        for i,item in enumerate(self.speed_rays):
            if not 54 < t < 61.1:
                c.itemconfig(item,state="hidden")
                continue
            boost = ease_in_out((t-54)/7)
            angle = (i+.4)*math.tau/len(self.speed_rays)
            radius = .12 + ((i*.618+t*(.35+boost))%1)*.65
            length = .025 + boost*.15
            cx,cy = w*.5,h*.48
            c.coords(item,cx+math.cos(angle)*w*radius,cy+math.sin(angle)*h*radius,
                     cx+math.cos(angle)*w*(radius+length),cy+math.sin(angle)*h*(radius+length))
            c.itemconfig(item,state="normal",fill=mix(BG,CYAN,.16+boost*.45),width=1+i%2)
            c.tag_raise(item)
        pulse = max(max(0,1-abs(t-35.1)/.40)*.6,
                    max(0,1-abs(t-46.7)/.60)*.55,
                    max(0,1-abs(t-60.72)/.36))
        for item,(color,weight) in zip(self.flare,T.glow_layers(CYAN,2)):
            if pulse:
                span = w*(.15+pulse*.55)
                y = h*.48 if t>40 else h*.50
                c.coords(item,w*.5-span,y,w*.5+span,y)
                c.itemconfig(item,state="normal",fill=mix(BG,color,pulse),width=weight)
                c.tag_raise(item)
            else:
                c.itemconfig(item,state="hidden")
        flash = max(0,1-abs(t-60.72)/.18)
        c.itemconfig(self.cross_flash,state="normal" if flash else "hidden",
                     fill=mix(BG,CORE,flash),stipple="gray50" if flash>.6 else "gray25")
        c.tag_raise(self.cross_flash)

    def _tick(self):
        started = time.perf_counter()
        self._after_id = None
        if not self.running:
            return
        t = self.elapsed()
        self._update(t)
        if t >= T_TITLE_END or (
            self.skipping and time.perf_counter() - self.skip_t0 > 0.35
        ):
            self._finish()
            return
        spent = (time.perf_counter()-started)*1000
        self._after_id = self.root.after(max(1,int(self.dt_ms-spent)),self._tick)

    def elapsed(self):
        """Usa a reprodução real; sem áudio, mantém um relógio monotônico contínuo."""
        wall = INTRO_START + max(0.0, time.perf_counter() - self.t0)
        position = self.timeline() if self.timeline is not None else None
        if type(position) in (int, float) and math.isfinite(position) and position >= 0:
            value = position
            self._clock_anchor = (wall, position)
        elif self._clock_anchor is not None:
            anchor_wall, anchor_position = self._clock_anchor
            value = anchor_position + wall - anchor_wall
        else:
            value = wall
        self._elapsed = max(self._elapsed, value)
        return self._elapsed

    def _update(self, t):
        c = self.c
        if t >= REZ_START:
            view = self.world.render(t)
            self.cam_z = view.z
            self.portal.render(t, view)
            if not self.rez_sounded:
                self.rez_sounded = True
                self.on_sound("rez")
            if t >= 60.7 and not self.portal_sounded:
                self.portal_sounded = True
                self.on_sound("portal")
            if t >= T_TITLE_START:
                self.logo3d.render(t - T_TITLE_START, view=view, origin=LOGO_ORIGIN,
                                   scale=LOGO_SCALE, environment=False)
        if t < REZ_END:
            txt = terminal_text(t)
            targets = []
            if t > REZ_START:
                for block in self.world.blocks[:12]:
                    point = self.world.view.transform((block.x, -block.height * .5, block.z))
                    if point[2] > 1:
                        x, y = self.world.view.project(point)
                        targets.append((max(0, min(self.w,x)), max(0, min(self.h,y))))
            self.terminal.render(t, txt, targets)
            shown = len(txt.replace("\n", ""))
            if shown > self._typed and shown // 3 > self._typed // 3:
                self.on_sound("type")
            self._typed = shown
        elif self.terminal_visible:
            self.terminal.hide()
            self.terminal_visible = False
        self._atmosphere(t)
        c.tag_raise(self.fade)
        c.tag_raise(self.hint_bg)
        c.tag_raise(self.hint)
        if self.skipping:
            p = (time.perf_counter() - self.skip_t0) / 0.35
            stipple = (
                "gray25"
                if p < 0.33
                else "gray50" if p < 0.66 else "gray75" if p < 0.9 else ""
            )
            c.itemconfig(self.fade, state="normal", stipple=stipple)
        hint_gain = 1 - ease_in_out((t - INTRO_START - 2.5) / .8)
        c.itemconfig(self.hint, state="normal" if hint_gain else "hidden",
                     fill=mix(BG, T.MUTED, hint_gain))
        c.itemconfig(self.hint_bg, state="normal" if hint_gain else "hidden")

    # ------------------------------------------------------------ fim
    def _on_key(self, _event=None):
        if self.running:
            self.skip()

    def _finish(self):
        if self._completed:
            return
        self._completed = True
        self.cancel()
        self.on_done()

    def cancel(self):
        """Libera apenas os eventos e itens desta introdução, sem abrir outra tela."""
        self.running = False
        if self._after_id:
            try:
                self.root.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None
        for sequence, attr in (("<Key>", "_key_id"), ("<Button-1>", "_click_id")):
            binding = getattr(self, attr)
            if binding:
                self.root.unbind(sequence, binding)
                setattr(self, attr, None)
        self.c.delete("intro")


class IntroFrame(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=BG)
        self.controller = controller
        self.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(
            self,
            width=controller.screen_width,
            height=controller.screen_height,
            bg=BG,
            highlightthickness=0,
            takefocus=0,
        )
        self.canvas.pack(fill="both", expand=True)
        self.intro = Intro(
            parent,
            self.canvas,
            on_done=lambda: controller.show_menu("title", preserve_intro=True,
                                                arrival=not self.intro.skipping),
            on_sound=lambda name: (
                controller.sound.play({"type": "move", "portal": "intro_portal", "rez": "intro_scan"}[name])
                if name in ("type", "portal", "rez")
                else None
            ),
            on_start=controller.sound.start_intro_music,
            timeline=controller.sound.intro_position,
        )
        self.start_id = self.after_idle(self._start)
        self.skip_pending = False

    def _start(self):
        self.start_id = None
        self.intro.start()
        if self.skip_pending:
            self.intro.skip()

    def skip(self):
        self.skip_pending = True
        self.intro.skip()

    def on_escape(self):
        self.skip()

    def on_pad(self, pid, kind, value):
        if kind == "button" or kind == "dir" and any(value):
            self.skip()

    def destroy_arena(self):
        if self.start_id is not None:
            self.after_cancel(self.start_id)
            self.start_id = None
        self.intro.cancel()


# ---------------- teste isolado:  python intro.py ----------------
if __name__ == "__main__":
    root = tk.Tk()
    root.configure(bg=BG)
    root.geometry("1280x720")
    cv = tk.Canvas(root, bg=BG, highlightthickness=0)
    cv.pack(fill="both", expand=True)

    def fim():
        audio.stop_music()
        cv.create_text(640, 360, text="(menu aqui)", fill=CYAN, font=FONT_MONO)

    from sound import SoundManager

    audio = SoundManager()

    def tick_audio():
        audio.update_music()
        root.after(25, tick_audio)

    def close():
        animation.cancel()
        audio.shutdown()
        root.destroy()

    root.update()
    animation = Intro(
        root,
        cv,
        on_done=fim,
        on_start=audio.start_intro_music,
        timeline=audio.intro_position,
    )
    root.protocol("WM_DELETE_WINDOW", close)
    animation.start()
    tick_audio()
    root.mainloop()

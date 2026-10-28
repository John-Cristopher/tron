"""Gera GIFs silenciosos da montagem da cidade e da transição até o título."""

from pathlib import Path
import argparse
import sys
import tempfile
import tkinter as tk
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.preview_capture import capture_window
from PIL import Image
from intro import T_TITLE_END
import tron_light_cycle as game
from tools.preview_chase import SilentSound, NoPads


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path)
    parser.add_argument("--fps",type=int,default=12)
    args = parser.parse_args()
    output = args.output or Path(tempfile.mkdtemp(prefix="tron-intro-"))
    output.mkdir(parents=True,exist_ok=True)
    root = tk.Tk()
    root.title("TRON / transition preview")
    root.configure(bg="#02060A")
    root.geometry("960x540+20+20")
    root.update()
    with patch.object(game,"SoundManager",SilentSound),patch.object(
        game,"GamepadManager",NoPads),patch.object(root,"attributes"):
        app = game.LightCycleGame(root,play_intro=False)
    app.screen_width,app.screen_height=960,540
    app.show_intro()
    root.update_idletasks()
    intro = app.current_frame.intro
    if intro._after_id is not None:
        root.after_cancel(intro._after_id)
        intro._after_id=None
    frames, title_frames = [], []
    captures={0:"intro_black",27:"intro_terminal",34.7:"intro_scan_start",
              35.6:"intro_scan",36.5:"intro_rez",40:"intro_city",42:"intro_flight",
              46.3:"intro_ignition",48.5:"intro_logo",57:"intro_dive",60.7:"intro_flash"}

    def gif_frame():
        return capture_window(root).resize((768,432),Image.Resampling.LANCZOS).convert(
            "P",palette=Image.Palette.ADAPTIVE,colors=128)
    try:
        for t,name in captures.items():
            intro._update(t)
            capture_window(root).save(output/(name+".png"))
        # Reinicia para que os eventos e o pool tenham a sequência natural.
        app.show_intro()
        root.update_idletasks()
        intro=app.current_frame.intro
        root.after_cancel(intro._after_id)
        intro._after_id=None
        count=len(intro.c.find_all())
        for i in range(round((T_TITLE_END - 32) * args.fps) + 1):
            t = 32 + i / args.fps
            intro._update(t)
            assert len(intro.c.find_all())==count
            frame=gif_frame()
            frames.append(frame)
            if t >= 43:
                title_frames.append(frame)
            if i % (args.fps*5)==0:
                print(f"Intro: {t:.1f}s",flush=True)
        intro._finish()
        menu=app.current_frame
        if menu.after_id is not None:
            menu.after_cancel(menu.after_id)
            menu.after_id=None
        boot_items=set(menu.cv.find_withtag("ui"))
        saved=set()
        for i in range(round(2.5*args.fps)+1):
            age=i/args.fps
            menu.t=age
            menu.update_arrival(age)
            menu.disc.animate(age)
            menu.stadium_scene.animate(age)
            menu.menu_race.advance(1/args.fps)
            for cue,name in ((0,"menu_arrival"),(.5,"menu_buttons"),(1.5,"menu_crowd"),(2.3,"menu_ready")):
                if age>=cue and name not in saved:
                    capture_window(root).save(output/(name+".png"))
                    saved.add(name)
            frame=gif_frame()
            frames.append(frame)
            title_frames.append(frame)
        assert set(menu.cv.find_withtag("ui"))==boot_items
        assert not menu.arrival_active
        for name, sequence in (
            ("intro_transition.gif", frames),
            ("intro_title_3d.gif", title_frames),
        ):
            sequence[0].save(
                output / name,
                save_all=True,
                append_images=sequence[1:],
                duration=round(1000/args.fps),
                loop=0,
                optimize=False,
            )
            print(name, flush=True)
        print("Prévia:",output,flush=True)
    finally:
        app.clear_screen()
        if app.music_after_id:
            root.after_cancel(app.music_after_id)
        root.destroy()


if __name__ == "__main__":
    main()

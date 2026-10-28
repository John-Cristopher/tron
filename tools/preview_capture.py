"""Captura só a janela Tk do próprio processo, mesmo atrás de outra janela."""

from functools import lru_cache
import os
import sys

from PIL import Image


@lru_cache(maxsize=1)
def _windows_api():
    import ctypes as C
    from ctypes import wintypes as W

    user = C.WinDLL("user32", use_last_error=True)
    gdi = C.WinDLL("gdi32", use_last_error=True)
    declarations = (
        (user, "GetAncestor", [W.HWND,W.UINT], W.HWND),
        (user, "GetWindowThreadProcessId", [W.HWND,C.POINTER(W.DWORD)], W.DWORD),
        (user, "GetClientRect", [W.HWND,C.POINTER(W.RECT)], W.BOOL),
        (user, "GetDC", [W.HWND], W.HDC),
        (user, "ReleaseDC", [W.HWND,W.HDC], C.c_int),
        (user, "PrintWindow", [W.HWND,W.HDC,W.UINT], W.BOOL),
        (gdi, "CreateCompatibleDC", [W.HDC], W.HDC),
        (gdi, "CreateCompatibleBitmap", [W.HDC,C.c_int,C.c_int], W.HBITMAP),
        (gdi, "SelectObject", [W.HDC,W.HGDIOBJ], W.HGDIOBJ),
        (gdi, "DeleteObject", [W.HGDIOBJ], W.BOOL),
        (gdi, "DeleteDC", [W.HDC], W.BOOL),
        (gdi, "GetDIBits", [W.HDC,W.HBITMAP,W.UINT,W.UINT,C.c_void_p,C.c_void_p,W.UINT], C.c_int),
    )
    for library,name,args,result in declarations:
        function = getattr(library,name)
        function.argtypes, function.restype = args,result

    class Header(C.Structure):
        _fields_ = [("size",W.DWORD),("width",W.LONG),("height",W.LONG),
                    ("planes",W.WORD),("bits",W.WORD),("compression",W.DWORD),
                    ("bytes",W.DWORD),("xppm",W.LONG),("yppm",W.LONG),
                    ("used",W.DWORD),("important",W.DWORD)]
    return C,W,user,gdi,Header


def capture_window(root):
    import _tkinter
    # Entrega Map/Expose após a troca de Frame, sem avançar timers da animação.
    for _ in range(64):
        if not root.tk.dooneevent(_tkinter.WINDOW_EVENTS | _tkinter.DONT_WAIT):
            break
    root.update_idletasks()
    if sys.platform != "win32":
        from PIL import ImageGrab
        return ImageGrab.grab(window=root.winfo_id())
    C,W,user,gdi,Header = _windows_api()
    window = user.GetAncestor(root.winfo_id(),2)
    process = W.DWORD()
    user.GetWindowThreadProcessId(window,C.byref(process))
    if process.value != os.getpid():
        raise RuntimeError("A captura deve pertencer ao processo da prévia.")
    rect = W.RECT()
    if not user.GetClientRect(window,C.byref(rect)):
        raise C.WinError(C.get_last_error())
    width,height = rect.right,rect.bottom
    source = user.GetDC(window)
    memory = gdi.CreateCompatibleDC(source)
    bitmap = gdi.CreateCompatibleBitmap(source,width,height)
    previous = gdi.SelectObject(memory,bitmap)
    try:
        # PW_CLIENTONLY | PW_RENDERFULLCONTENT evita capturar a janela da frente.
        if not user.PrintWindow(window,memory,3):
            raise C.WinError(C.get_last_error())
        gdi.SelectObject(memory,previous)
        header = Header(C.sizeof(Header),width,-height,1,32,0,0,0,0,0,0)
        pixels = C.create_string_buffer(width*height*4)
        if gdi.GetDIBits(memory,bitmap,0,height,pixels,C.byref(header),0) != height:
            raise C.WinError(C.get_last_error())
        return Image.frombytes("RGB",(width,height),pixels.raw,"raw","BGRX")
    finally:
        gdi.SelectObject(memory,previous)
        gdi.DeleteObject(bitmap)
        gdi.DeleteDC(memory)
        user.ReleaseDC(window,source)

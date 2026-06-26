from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from app import CaixaPosApp

_PRIMARY = "#0d6efd"
_SECONDARY = "#6c757d"
_SUCCESS = "#198754"
_DANGER = "#dc3545"
_WARNING = "#ffc107"
_INFO = "#0dcaf0"
_LIGHT = "#f8f9fa"
_DARK = "#212529"
_BG = "#ffffff"
_FG = "#212529"


def _configure_style(style):
    style.configure("TButton", background=_PRIMARY, foreground="#ffffff")
    style.map("TButton", background=[("disabled", _SECONDARY), ("active", "#0b5ed7")])
    style.configure("primary.TButton", background=_PRIMARY, foreground="#ffffff")
    style.configure("primary.Outline.TButton", background=_BG, foreground=_PRIMARY)
    style.configure("success.TButton", background=_SUCCESS, foreground="#ffffff")
    style.configure("danger.TButton", background=_DANGER, foreground="#ffffff")
    style.configure("TFrame", background=_BG)
    style.configure("TLabel", background=_BG, foreground=_FG)
    style.configure("TLabelframe", background=_BG, foreground=_FG)
    style.configure("TLabelframe.Label", background=_BG, foreground=_FG)
    style.configure("TEntry", fieldbackground=_BG, foreground=_FG)
    style.configure("Treeview", background=_BG, foreground=_FG, fieldbackground=_BG)
    style.configure("Treeview.Heading", background=_LIGHT, foreground=_FG)


def create_root():
    try:
        import ttkbootstrap as tb

        root = tb.Window(themename="flatly")
        root.configure(bg=_BG)
        style = root.style
        style.configure(".", background=_BG, foreground=_FG, font=("Segoe UI", 10))
        _configure_style(style)
        return root
    except Exception:
        root = tk.Tk()
        root.configure(bg=_BG)
        try:
            from tkinter import ttk

            style = ttk.Style(root)
            style.theme_use("clam")
            style.configure(".", background=_BG, foreground=_FG, font=("Segoe UI", 10))
            _configure_style(style)
        except Exception:
            pass
        return root


def main() -> None:
    root = create_root()
    try:
        app = CaixaPosApp(root)
    except Exception as exc:
        messagebox.showerror("Erro ao iniciar CaixaPos", str(exc))
        root.destroy()
        return
    root.protocol("WM_DELETE_WINDOW", app.close)
    root.mainloop()


if __name__ == "__main__":
    main()

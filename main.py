from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from app import CaixaPosApp


def create_root():
    try:
        import ttkbootstrap as tb

        return tb.Window(themename="litera")
    except Exception:
        root = tk.Tk()
        try:
            from tkinter import ttk

            ttk.Style(root).theme_use("clam")
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

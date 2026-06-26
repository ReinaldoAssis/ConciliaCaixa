from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from db import CaixaRepository
from views.historico import HistoryFrame
from views.importacao import ImportFrame
from views.resultado import ResultFrame


class CaixaPosApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("CaixaPos")
        self.root.minsize(900, 650)
        self.repo = CaixaRepository()
        self.container = ttk.Frame(root)
        self.container.pack(fill="both", expand=True)
        self.history = HistoryFrame(self.container, self)
        self.importacao = ImportFrame(self.container, self)
        self.resultado = ResultFrame(self.container, self)
        self.show_history()

    def _show(self, frame: ttk.Frame) -> None:
        for child in self.container.winfo_children():
            child.pack_forget()
        frame.pack(fill="both", expand=True)

    def show_history(self) -> None:
        self.history.refresh()
        self._show(self.history)

    def new_caixa(self) -> None:
        self.importacao.load_caixa(None)
        self._show(self.importacao)

    def open_caixa(self, caixa_id: str) -> None:
        caixa = self.repo.get(caixa_id)
        if not caixa:
            messagebox.showerror("Registro nao encontrado", "Nao foi possivel abrir este caixa.")
            return
        self.importacao.load_caixa(caixa)
        self._show(self.importacao)

    def edit_caixa_model(self, caixa: dict) -> None:
        self.importacao.load_caixa(caixa)
        self._show(self.importacao)

    def show_result(self, caixa: dict) -> None:
        self.resultado.load_caixa(caixa)
        self._show(self.resultado)

    def close(self) -> None:
        self.repo.close()
        self.root.destroy()

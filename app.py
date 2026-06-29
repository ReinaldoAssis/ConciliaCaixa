from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from db import CaixaRepository, CaixaRestauranteRepository
from views.historico import HistoryFrame
from views.historico_restaurante import HistoryRestauranteFrame
from views.importacao import ImportFrame
from views.importacao_restaurante import ImportRestauranteFrame
from views.resultado import ResultFrame
from views.resultado_restaurante import ResultRestauranteFrame


class CaixaPosApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("CaixaPos")
        self.root.minsize(960, 680)
        self.repo = CaixaRepository()
        self.repo_restaurante = CaixaRestauranteRepository()

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True)

        self.posto_container = ttk.Frame(self.notebook)
        self.restaurante_container = ttk.Frame(self.notebook)
        self.notebook.add(self.posto_container, text="Posto")
        self.notebook.add(self.restaurante_container, text="Restaurante")

        self.history = HistoryFrame(self.posto_container, self)
        self.importacao = ImportFrame(self.posto_container, self)
        self.resultado = ResultFrame(self.posto_container, self)

        self.history_restaurante = HistoryRestauranteFrame(self.restaurante_container, self)
        self.importacao_restaurante = ImportRestauranteFrame(self.restaurante_container, self)
        self.resultado_restaurante = ResultRestauranteFrame(self.restaurante_container, self)

        self.show_history()
        self.show_history_restaurante()

    def _show(self, frame: ttk.Frame, container: ttk.Frame) -> None:
        for child in container.winfo_children():
            child.pack_forget()
        frame.pack(fill="both", expand=True)

    def show_history(self) -> None:
        self.history.refresh()
        self._show(self.history, self.posto_container)

    def show_history_restaurante(self) -> None:
        self.history_restaurante.refresh()
        self._show(self.history_restaurante, self.restaurante_container)

    def new_caixa(self) -> None:
        self.importacao.load_caixa(None)
        self._show(self.importacao, self.posto_container)

    def new_caixa_restaurante(self) -> None:
        self.importacao_restaurante.load_caixa(None)
        self._show(self.importacao_restaurante, self.restaurante_container)

    def open_caixa(self, caixa_id: str) -> None:
        caixa = self.repo.get(caixa_id)
        if not caixa:
            messagebox.showerror("Registro nao encontrado", "Nao foi possivel abrir este caixa.")
            return
        self.importacao.load_caixa(caixa)
        self._show(self.importacao, self.posto_container)

    def open_caixa_restaurante(self, caixa_id: str) -> None:
        caixa = self.repo_restaurante.get(caixa_id)
        if not caixa:
            messagebox.showerror("Registro nao encontrado", "Nao foi possivel abrir este caixa.")
            return
        self.importacao_restaurante.load_caixa(caixa)
        self._show(self.importacao_restaurante, self.restaurante_container)

    def edit_caixa_model(self, caixa: dict) -> None:
        self.importacao.load_caixa(caixa)
        self._show(self.importacao, self.posto_container)

    def edit_caixa_restaurante_model(self, caixa: dict) -> None:
        self.importacao_restaurante.load_caixa(caixa)
        self._show(self.importacao_restaurante, self.restaurante_container)

    def show_result(self, caixa: dict) -> None:
        self.resultado.load_caixa(caixa)
        self._show(self.resultado, self.posto_container)

    def show_result_restaurante(self, caixa: dict) -> None:
        self.resultado_restaurante.load_caixa(caixa)
        self._show(self.resultado_restaurante, self.restaurante_container)

    def close(self) -> None:
        self.repo.close()
        self.repo_restaurante.close()
        self.root.destroy()

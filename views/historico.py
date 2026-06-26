from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from updater import CURRENT_VERSION, UpdateConfigDialog
from utils import date_to_br, date_to_iso, format_money


class HistoryFrame(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=14)
        self.app = app
        self.search_var = tk.StringVar()
        self.status_var = tk.StringVar(value="todos")
        header = ttk.Frame(self)
        header.pack(fill="x")
        ttk.Label(header, text="CaixaPos", font=("", 20, "bold")).pack(side="left")
        version_label = ttk.Label(header, text=CURRENT_VERSION)
        version_label.pack(side="left", padx=8)
        ttk.Button(header, text="Atualizacoes", command=self._open_updater).pack(side="left", padx=6)
        ttk.Button(header, text="Novo Caixa", command=self.app.new_caixa).pack(side="right")

        filters = ttk.LabelFrame(self, text="Filtros", padding=10)
        filters.pack(fill="x", pady=12)
        ttk.Label(filters, text="Data").pack(side="left")
        ttk.Entry(filters, textvariable=self.search_var, width=16).pack(side="left", padx=6)
        ttk.Label(filters, text="Status").pack(side="left", padx=(12, 0))
        ttk.Combobox(
            filters,
            textvariable=self.status_var,
            values=["todos", "rascunho", "conciliado"],
            width=14,
            state="readonly",
        ).pack(side="left", padx=6)
        ttk.Button(filters, text="Buscar", command=self.refresh).pack(side="left", padx=6)

        columns = ("data", "sistema", "site", "diferenca", "status")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=18)
        labels = {
            "data": "Data",
            "sistema": "Valor Sistema",
            "site": "Valor Site",
            "diferenca": "Diferenca Total",
            "status": "Status",
        }
        for col in columns:
            self.tree.heading(col, text=labels[col])
            self.tree.column(col, width=150, anchor="center")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", self._open_selected)
        self.tree.bind("<Return>", self._open_selected)
        self.footer_var = tk.StringVar()
        ttk.Label(self, textvariable=self.footer_var).pack(anchor="w", pady=(8, 0))

    def refresh(self) -> None:
        for row in self.tree.get_children():
            self.tree.delete(row)
        search_date = self.search_var.get().strip()
        iso_date = None
        if search_date:
            try:
                iso_date = date_to_iso(search_date)
            except ValueError:
                iso_date = search_date
        records = self.app.repo.search(iso_date, self.status_var.get())
        for item in records:
            self.tree.insert(
                "",
                "end",
                iid=item["id"],
                values=(
                    date_to_br(item["data"]),
                    format_money(item.get("total_sistema", 0)),
                    format_money(item.get("total_site", 0)),
                    format_money(item.get("diferenca_total", 0)),
                    item.get("status", "rascunho"),
                ),
            )
        self.footer_var.set(f"{len(records)} registro(s) exibido(s)")

    def _open_selected(self, _event=None) -> None:
        selected = self.tree.selection()
        if selected:
            self.app.open_caixa(selected[0])

    def _open_updater(self) -> None:
        UpdateConfigDialog(self)

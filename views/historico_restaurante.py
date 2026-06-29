from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from utils import date_to_br, date_to_iso, format_money


class HistoryRestauranteFrame(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=14)
        self.app = app
        self.search_var = tk.StringVar()
        self.status_var = tk.StringVar(value="ativos")
        header = ttk.Frame(self)
        header.pack(fill="x")
        ttk.Label(header, text="CaixaPos - Restaurante", font=("", 20, "bold")).pack(side="left")
        ttk.Button(header, text="Novo Caixa", command=self.app.new_caixa_restaurante).pack(side="right")

        filters = ttk.LabelFrame(self, text="Filtros", padding=10)
        filters.pack(fill="x", pady=12)
        ttk.Label(filters, text="Data").pack(side="left")
        ttk.Entry(filters, textvariable=self.search_var, width=16).pack(side="left", padx=6)
        ttk.Label(filters, text="Status").pack(side="left", padx=(12, 0))
        ttk.Combobox(
            filters,
            textvariable=self.status_var,
            values=["ativos", "todos", "rascunho", "conciliado", "arquivado"],
            width=14,
            state="readonly",
        ).pack(side="left", padx=6)
        ttk.Button(filters, text="Buscar", command=self.refresh).pack(side="left", padx=6)

        columns = ("data", "turno", "sistema", "real", "diferenca", "status")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=18)
        labels = {
            "data": "Data",
            "turno": "Turno",
            "sistema": "Valor Sistema",
            "real": "Valor Real",
            "diferenca": "Diferenca Total",
            "status": "Status",
        }
        widths = {"data": 110, "turno": 60, "sistema": 130, "real": 130, "diferenca": 130, "status": 100}
        for col in columns:
            self.tree.heading(col, text=labels[col])
            self.tree.column(col, width=widths.get(col, 130), anchor="center")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", self._open_selected)
        self.tree.bind("<Return>", self._open_selected)

        footer = ttk.Frame(self)
        footer.pack(fill="x", pady=(8, 0))
        self.footer_var = tk.StringVar()
        ttk.Label(footer, textvariable=self.footer_var).pack(side="left")
        ttk.Button(footer, text="Arquivar", command=self._archive_selected).pack(side="right", padx=4)
        ttk.Button(footer, text="Excluir", command=self._delete_selected).pack(side="right", padx=4)
        ttk.Button(footer, text="Restaurar", command=self._restore_selected).pack(side="right", padx=4)

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
        status_filter = self.status_var.get()
        records = self.app.repo_restaurante.all()
        if iso_date:
            records = [item for item in records if item.get("data") == iso_date]
        if status_filter == "ativos":
            records = [item for item in records if item.get("status") != "arquivado"]
        elif status_filter != "todos":
            records = [item for item in records if item.get("status") == status_filter]
        for item in records:
            turno_display = f"T{item['turno']}" if item.get("turno") else "-"
            status = item.get("status", "rascunho")
            tags = ("archived",) if status == "arquivado" else ()
            self.tree.insert(
                "", "end", iid=item["id"],
                values=(
                    date_to_br(item["data"]),
                    turno_display,
                    format_money(item.get("total_sistema", 0)),
                    format_money(item.get("total_real", 0)),
                    format_money(item.get("diferenca_total", 0)),
                    status,
                ),
                tags=tags,
            )
        self.tree.tag_configure("archived", foreground="#6c757d")
        self.footer_var.set(f"{len(records)} registro(s) exibido(s)")

    def _open_selected(self, _event=None) -> None:
        selected = self.tree.selection()
        if selected:
            caixa = self.app.repo_restaurante.get(selected[0])
            if caixa and caixa.get("status") == "arquivado":
                messagebox.showinfo("Arquivado", "Este caixa esta arquivado. Restaure-o para editar.")
                return
            self.app.open_caixa_restaurante(selected[0])

    def _archive_selected(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Nada selecionado", "Selecione um caixa para arquivar.")
            return
        caixa = self.app.repo_restaurante.get(selected[0])
        if not caixa:
            return
        if caixa.get("status") == "arquivado":
            messagebox.showinfo("Ja arquivado", "Este caixa ja esta arquivado.")
            return
        if messagebox.askyesno("Arquivar caixa", f"Arquivar caixa de {date_to_br(caixa['data'])}?"):
            caixa["status"] = "arquivado"
            self.app.repo_restaurante.save(caixa)
            self.refresh()

    def _restore_selected(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Nada selecionado", "Selecione um caixa arquivado para restaurar.")
            return
        caixa = self.app.repo_restaurante.get(selected[0])
        if not caixa:
            return
        if caixa.get("status") != "arquivado":
            messagebox.showinfo("Nao arquivado", "Apenas caixas arquivados podem ser restaurados.")
            return
        if messagebox.askyesno("Restaurar caixa", f"Restaurar caixa de {date_to_br(caixa['data'])} para rascunho?"):
            caixa["status"] = "rascunho"
            self.app.repo_restaurante.save(caixa)
            self.refresh()

    def _delete_selected(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Nada selecionado", "Selecione um caixa para excluir.")
            return
        caixa = self.app.repo_restaurante.get(selected[0])
        if not caixa:
            return
        if messagebox.askyesno(
            "Excluir permanentemente",
            f"Tem certeza que deseja EXCLUIR o caixa de {date_to_br(caixa['data'])}?\n\nEsta acao nao pode ser desfeita.",
        ):
            self.app.repo_restaurante.delete(selected[0])
            self.refresh()

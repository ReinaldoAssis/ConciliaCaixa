from __future__ import annotations

import tkinter as tk
from copy import deepcopy
from tkinter import filedialog, messagebox, ttk

from constants import build_conciliation_rows
from export.pdf_export import export_caixa_pdf
from utils import date_to_br, format_money


class ResultFrame(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=14)
        self.app = app
        self.caixa: dict | None = None
        header = ttk.Frame(self)
        header.pack(fill="x")
        ttk.Button(header, text="Recomecar", command=self._back).pack(side="left")
        self.title_var = tk.StringVar()
        ttk.Label(header, textvariable=self.title_var, font=("", 18, "bold")).pack(side="left", padx=12)

        columns = ("categoria", "sistema", "site", "diferenca", "status")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=14)
        headings = {
            "categoria": "Categoria",
            "sistema": "Sistema (R$)",
            "site": "Site (R$)",
            "diferenca": "Diferenca (R$)",
            "status": "Status",
        }
        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=160, anchor="center")
        self.tree.column("categoria", anchor="w", width=220)
        self.tree.tag_configure("ok", foreground="#198754")
        self.tree.tag_configure("bad", foreground="#dc3545")
        self.tree.pack(fill="both", expand=True, pady=12)

        self.info_var = tk.StringVar()
        ttk.Label(self, textvariable=self.info_var, justify="left").pack(anchor="w")
        footer = ttk.Frame(self)
        footer.pack(fill="x", pady=12)
        ttk.Button(footer, text="Salvar Conciliacao", command=self.save).pack(side="left")
        ttk.Button(footer, text="Exportar PDF", command=self.export_pdf).pack(side="right")

    def load_caixa(self, caixa: dict) -> None:
        self.caixa = deepcopy(caixa)
        self.title_var.set(f"Resultado - {date_to_br(self.caixa['data'])}")
        for item in self.tree.get_children():
            self.tree.delete(item)
        for index, row in enumerate(build_conciliation_rows(self.caixa.get("categorias", {}))):
            tag = "ok" if row["status"] == "OK" else "bad"
            self.tree.insert(
                "",
                "end",
                values=(
                    row["label"],
                    format_money(row["sistema"]),
                    format_money(row["site"]),
                    format_money(row["diferenca"]),
                    row["status"],
                ),
                tags=(tag,),
            )
        self.info_var.set(
            "\n".join(
                [
                    f"Sangria: {format_money(self.caixa.get('sangria', 0))}",
                    f"Notas a Prazo: {format_money(self.caixa.get('notas_a_prazo', 0))}",
                    f"Despesas do Posto: {format_money(self.caixa.get('despesas', 0))}",
                ]
            )
        )

    def save(self) -> None:
        if not self.caixa:
            return
        self.caixa["status"] = "conciliado"
        self.app.repo.save(self.caixa)
        messagebox.showinfo("Conciliacao salva", "O caixa foi salvo como conciliado.")
        self.app.show_history()

    def export_pdf(self) -> None:
        if not self.caixa:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=f"CaixaPos_{self.caixa['data']}.pdf",
        )
        if not path:
            return
        try:
            export_caixa_pdf(self.caixa, path)
            messagebox.showinfo("PDF exportado", f"Arquivo salvo em:\n{path}")
        except Exception as exc:
            messagebox.showerror("Erro ao exportar PDF", str(exc))

    def _back(self) -> None:
        if self.caixa:
            self.app.edit_caixa_model(self.caixa)

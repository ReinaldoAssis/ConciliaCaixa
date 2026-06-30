from __future__ import annotations

import tkinter as tk
from copy import deepcopy
from tkinter import filedialog, messagebox, ttk

from constants_restaurante import build_conciliation_rows_restaurante
from export.pdf_export import export_caixa_restaurante_pdf
from utils import date_to_br, format_money


class ResultRestauranteFrame(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=14)
        self.app = app
        self.caixa: dict | None = None
        header = ttk.Frame(self)
        header.pack(fill="x")
        ttk.Button(header, text="Recomecar", command=self._back).pack(side="left")
        self.title_var = tk.StringVar()
        ttk.Label(header, textvariable=self.title_var, font=("", 18, "bold")).pack(side="left", padx=12)

        columns = ("categoria", "classif", "sistema", "real", "diferenca", "status")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=16)
        headings = {
            "categoria": "Categoria",
            "classif": "Classif.",
            "sistema": "Sistema (R$)",
            "real": "Real (R$)",
            "diferenca": "Diferenca (R$)",
            "status": "Status",
        }
        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=130, anchor="center")
        self.tree.column("categoria", anchor="w", width=180)
        self.tree.tag_configure("ok", foreground="#198754")
        self.tree.tag_configure("bad", foreground="#dc3545")
        self.tree.pack(fill="both", expand=True, pady=12)
        self._bind_mousewheel()

        footer = ttk.Frame(self)
        footer.pack(fill="x", pady=12)
        ttk.Button(footer, text="Salvar Conciliacao", command=self.save).pack(side="left")
        ttk.Button(footer, text="Exportar PDF", command=self.export_pdf).pack(side="right")

    def load_caixa(self, caixa: dict) -> None:
        self.caixa = deepcopy(caixa)
        self.title_var.set(f"Resultado Restaurante - {date_to_br(self.caixa['data'])}")
        for item in self.tree.get_children():
            self.tree.delete(item)
        avulsos = self.caixa.get("lancamentos_avulsos") or []
        contagens = self.caixa.get("contagens_dinheiro") or []
        geral = next((c for c in contagens if c.get("label") == "Geral"), None)
        dinheiro_real = round(geral.get("total", 0) if geral else 0, 2)
        total_diff = 0.0
        for row in build_conciliation_rows_restaurante(
            self.caixa.get("categorias", {}), avulsos, dinheiro_real
        ):
            tag = "ok" if row["status"] == "OK" else "bad"
            self.tree.insert(
                "", "end",
                values=(
                    row["label"],
                    row["classificacao"],
                    format_money(row["sistema"]),
                    format_money(row["real"]),
                    format_money(row["diferenca"]),
                    row["status"],
                ),
                tags=(tag,),
            )
            total_diff += float(row["diferenca"])
        footer_row = (
            "", "", "Diferença Total:", format_money(round(total_diff, 2)), "",
        )
        tag = "ok" if abs(total_diff) < 0.005 else "bad"
        self.tree.insert("", "end", values=footer_row, tags=(tag,))

    def save(self) -> None:
        if not self.caixa:
            return
        self.caixa["status"] = "conciliado"
        self.app.repo_restaurante.save(self.caixa)
        messagebox.showinfo("Conciliacao salva", "O caixa foi salvo como conciliado.")
        self.app.show_history_restaurante()

    def export_pdf(self) -> None:
        if not self.caixa:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=f"CaixaPos_Restaurante_{self.caixa['data']}.pdf",
        )
        if not path:
            return
        try:
            export_caixa_restaurante_pdf(self.caixa, path)
            messagebox.showinfo("PDF exportado", f"Arquivo salvo em:\n{path}")
        except Exception as exc:
            messagebox.showerror("Erro ao exportar PDF", str(exc))

    def _bind_mousewheel(self) -> None:
        def _on_mousewheel(event):
            if event.delta > 0:
                self.tree.yview_scroll(-3, "units")
            elif event.delta < 0:
                self.tree.yview_scroll(3, "units")

        self.tree.bind("<MouseWheel>", _on_mousewheel)
        self.tree.bind("<Button-4>", lambda e: self.tree.yview_scroll(-3, "units"))
        self.tree.bind("<Button-5>", lambda e: self.tree.yview_scroll(3, "units"))

    def _back(self) -> None:
        if self.caixa:
            self.app.edit_caixa_restaurante_model(self.caixa)

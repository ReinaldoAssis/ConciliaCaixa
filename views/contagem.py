from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk
from uuid import uuid4

from constants import DENOMINATIONS
from utils import format_money, parse_money, serials_valid


class MoneyCountFrame(ttk.LabelFrame):
    def __init__(self, master, readonly: bool = False):
        super().__init__(master, text="Contagem de Dinheiro", padding=10)
        self.readonly = readonly
        self.counts: list[dict] = []
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)
        footer = ttk.Frame(self)
        footer.pack(fill="x", pady=(8, 0))
        ttk.Button(footer, text="+ Nova Contagem", command=self.add_count).pack(side="left")
        self.total_var = tk.StringVar(value=format_money(0))
        ttk.Label(footer, textvariable=self.total_var, font=("", 11, "bold")).pack(side="right")
        ttk.Label(footer, text="Total das contagens:").pack(side="right", padx=(0, 8))
        if readonly:
            for child in footer.winfo_children():
                if isinstance(child, ttk.Button):
                    child.configure(state="disabled")

    def set_counts(self, counts: list[dict]) -> None:
        for tab in self.notebook.tabs():
            self.notebook.forget(tab)
        self.counts = []
        for count in counts or []:
            self.add_count(count)
        self._refresh_total()

    def get_counts(self) -> list[dict]:
        return [self._collect_tab(self.notebook.nametowidget(tab)) for tab in self.notebook.tabs()]

    def add_count(self, existing: dict | None = None) -> None:
        index = len(self.notebook.tabs()) + 1
        frame = ttk.Frame(self.notebook, padding=8)
        frame.count_id = (existing or {}).get("id", str(uuid4()))
        frame.created_at = (existing or {}).get("criado_em", datetime.now().isoformat(timespec="seconds"))
        frame.vars = {}
        frame.serial_vars = []
        label_var = tk.StringVar(value=(existing or {}).get("label", f"Contagem {index}"))
        frame.label_var = label_var
        top = ttk.Frame(frame)
        top.pack(fill="x")
        ttk.Label(top, text="Label").pack(side="left")
        ttk.Entry(top, textvariable=label_var, width=24, state="readonly" if self.readonly else "normal").pack(
            side="left", padx=8
        )
        ttk.Button(top, text="Excluir", command=lambda f=frame: self._delete_tab(f), state="disabled" if self.readonly else "normal").pack(
            side="right"
        )
        grid = ttk.Frame(frame)
        grid.pack(fill="x", pady=8)
        for col, text in enumerate(["Cedula", "Valor Unit.", "Qtde.", "Subtotal"]):
            ttk.Label(grid, text=text, font=("", 10, "bold")).grid(row=0, column=col, sticky="w", padx=4, pady=3)
        notes = (existing or {}).get("notas", {})
        for row, denom in enumerate(DENOMINATIONS, start=1):
            qty_var = tk.StringVar(value=str(int(notes.get(str(denom), 0) or 0)))
            subtotal_var = tk.StringVar(value=format_money(int(qty_var.get() or 0) * denom))
            frame.vars[str(denom)] = (qty_var, subtotal_var)
            ttk.Label(grid, text=f"R$ {denom}").grid(row=row, column=0, sticky="w", padx=4, pady=2)
            ttk.Label(grid, text=format_money(denom)).grid(row=row, column=1, sticky="w", padx=4, pady=2)
            entry = ttk.Entry(grid, textvariable=qty_var, width=8, state="readonly" if self.readonly else "normal")
            entry.grid(row=row, column=2, sticky="w", padx=4, pady=2)
            ttk.Label(grid, textvariable=subtotal_var).grid(row=row, column=3, sticky="w", padx=4, pady=2)
            qty_var.trace_add("write", lambda *_args, f=frame: self._recalculate(f))
        moedas_var = tk.StringVar(value=str((existing or {}).get("moedas", "0")).replace(".", ","))
        frame.moedas_var = moedas_var
        frame.count_total_var = tk.StringVar(value=format_money((existing or {}).get("total", 0)))
        ttk.Label(grid, text="Moedas").grid(row=8, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(grid, textvariable=moedas_var, width=10, state="readonly" if self.readonly else "normal").grid(
            row=8, column=2, sticky="w", padx=4, pady=2
        )
        ttk.Label(grid, textvariable=moedas_var).grid(row=8, column=3, sticky="w", padx=4, pady=2)
        moedas_var.trace_add("write", lambda *_args, f=frame: self._recalculate(f))
        frame.serial_box = ttk.LabelFrame(frame, text="Seriais das notas de R$ 200", padding=8)
        frame.serial_box.pack(fill="x", pady=6)
        ttk.Label(frame, textvariable=frame.count_total_var, font=("", 12, "bold")).pack(anchor="e")
        self.notebook.add(frame, text=label_var.get())
        label_var.trace_add("write", lambda *_args, f=frame: self.notebook.tab(f, text=f.label_var.get() or "Contagem"))
        for serial in (existing or {}).get("seriais_200", []):
            frame.serial_vars.append(tk.StringVar(value=serial))
        self._recalculate(frame)

    def validate_counts(self) -> bool:
        for tab in self.notebook.tabs():
            data = self._collect_tab(self.notebook.nametowidget(tab))
            qty_200 = int(data["notas"].get("200", 0) or 0)
            if not serials_valid(data["seriais_200"], qty_200):
                messagebox.showerror("Seriais obrigatorios", "Cada nota de R$ 200 precisa de um serial numerico com 5 digitos.")
                return False
        return True

    def _delete_tab(self, frame) -> None:
        if messagebox.askyesno("Excluir contagem", "Deseja excluir esta contagem?"):
            self.notebook.forget(frame)
            self._refresh_total()

    def _collect_tab(self, frame) -> dict:
        notes = {}
        total = 0.0
        for denom in DENOMINATIONS:
            qty_var, _subtotal_var = frame.vars[str(denom)]
            try:
                qty = max(0, int(qty_var.get() or 0))
            except ValueError:
                qty = 0
            notes[str(denom)] = qty
            total += qty * denom
        moedas = parse_money(frame.moedas_var.get())
        total += moedas
        return {
            "id": frame.count_id,
            "label": frame.label_var.get() or "Contagem",
            "criado_em": frame.created_at,
            "notas": notes,
            "seriais_200": [var.get() for var in frame.serial_vars if var.get()],
            "moedas": moedas,
            "total": round(total, 2),
        }

    def _recalculate(self, frame) -> None:
        for denom in DENOMINATIONS:
            qty_var, subtotal_var = frame.vars[str(denom)]
            try:
                qty = max(0, int(qty_var.get() or 0))
            except ValueError:
                qty = 0
            subtotal_var.set(format_money(qty * denom))
        qty_200 = 0
        try:
            qty_200 = max(0, int(frame.vars["200"][0].get() or 0))
        except ValueError:
            pass
        self._sync_serials(frame, qty_200)
        data = self._collect_tab(frame)
        frame.count_total_var.set(f"Total: {format_money(data['total'])}")
        self._refresh_total()

    def _sync_serials(self, frame, qty_200: int) -> None:
        while len(frame.serial_vars) < qty_200:
            frame.serial_vars.append(tk.StringVar())
        while len(frame.serial_vars) > qty_200:
            frame.serial_vars.pop()
        for child in frame.serial_box.winfo_children():
            child.destroy()
        if qty_200 == 0:
            ttk.Label(frame.serial_box, text="Nenhuma nota de R$ 200 informada.").pack(anchor="w")
            return
        for idx, var in enumerate(frame.serial_vars, start=1):
            row = ttk.Frame(frame.serial_box)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=f"Serial nota {idx}").pack(side="left")
            ttk.Entry(row, textvariable=var, width=8, state="readonly" if self.readonly else "normal").pack(side="left", padx=8)

    def _refresh_total(self) -> None:
        total = 0.0
        for tab in self.notebook.tabs():
            try:
                total += self._collect_tab(self.notebook.nametowidget(tab))["total"]
            except Exception:
                pass
        self.total_var.set(format_money(total))

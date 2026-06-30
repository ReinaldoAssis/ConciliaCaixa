from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk
from uuid import uuid4

from constants import DENOMINATIONS
from utils import copy_image_to_clipboard, format_money, parse_money, serials_valid


class MoneyCountFrame(ttk.LabelFrame):
    def __init__(self, master, readonly: bool = False, on_change=None):
        super().__init__(master, text="Contagem de Dinheiro", padding=10)
        self.readonly = readonly
        self.caixa_data: str = ""
        self.counts: list[dict] = []
        self.geral_editado: bool = False
        self.on_change = on_change
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)

        self._build_geral_tab()

        footer = ttk.Frame(self)
        footer.pack(fill="x", pady=(8, 0))
        ttk.Button(footer, text="+ Nova Contagem", command=self.add_count).pack(side="left")
        self.copy_img_btn = ttk.Button(footer, text="Copiar Imagem", command=self._copy_image)
        self.copy_img_btn.pack(side="left", padx=8)
        self.total_var = tk.StringVar(value=format_money(0))
        ttk.Label(footer, textvariable=self.total_var, font=("", 11, "bold")).pack(side="right")
        ttk.Label(footer, text="Total das contagens:").pack(side="right", padx=(0, 8))
        self.edit_geral_btn = ttk.Button(footer, text="Editar Geral", command=self._edit_geral)
        self.edit_geral_btn.pack(side="left", padx=(12, 0))
        self.geral_editado_label = ttk.Label(footer, text="(editado)", foreground="#dc3545")
        if readonly:
            for child in footer.winfo_children():
                if isinstance(child, ttk.Button):
                    child.configure(state="disabled")

    def _build_geral_tab(self) -> None:
        frame = ttk.Frame(self.notebook, padding=8)
        frame.count_id = str(uuid4())
        frame.created_at = datetime.now().isoformat(timespec="seconds")
        frame.vars = {}
        frame.serial_vars = []
        frame.label_var = tk.StringVar(value="Geral")
        frame.label_var.set("Geral")
        top = ttk.Frame(frame)
        top.pack(fill="x")
        ttk.Label(top, text="Geral", font=("", 12, "bold")).pack(side="left")
        ttk.Label(top, text="(soma automatica das contagens abaixo)", foreground="#6c757d").pack(side="left", padx=8)

        grid = ttk.Frame(frame)
        grid.pack(fill="x", pady=8)
        for col, text in enumerate(["Cedula", "Valor Unit.", "Qtde.", "Subtotal"]):
            ttk.Label(grid, text=text, font=("", 10, "bold")).grid(row=0, column=col, sticky="w", padx=4, pady=3)
        for row, denom in enumerate(DENOMINATIONS, start=1):
            qty_var = tk.StringVar(value="0")
            subtotal_var = tk.StringVar(value=format_money(0))
            frame.vars[str(denom)] = (qty_var, subtotal_var)
            ttk.Label(grid, text=f"R$ {denom}").grid(row=row, column=0, sticky="w", padx=4, pady=2)
            ttk.Label(grid, text=format_money(denom)).grid(row=row, column=1, sticky="w", padx=4, pady=2)
            entry = ttk.Entry(grid, textvariable=qty_var, width=8, state="readonly")
            entry.grid(row=row, column=2, sticky="w", padx=4, pady=2)
            ttk.Label(grid, textvariable=subtotal_var).grid(row=row, column=3, sticky="w", padx=4, pady=2)
        moedas_var = tk.StringVar(value="0")
        frame.moedas_var = moedas_var
        frame.depositos_var = tk.StringVar(value="0")
        frame.count_total_var = tk.StringVar(value=f"Total: {format_money(0)} (Moedas: {format_money(0)})")
        ttk.Label(grid, text="Moedas").grid(row=8, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(grid, textvariable=moedas_var, width=10, state="readonly").grid(
            row=8, column=2, sticky="w", padx=4, pady=2
        )
        ttk.Label(grid, textvariable=moedas_var).grid(row=8, column=3, sticky="w", padx=4, pady=2)
        ttk.Label(grid, text="Depositos").grid(row=9, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(grid, textvariable=frame.depositos_var, width=10, state="readonly").grid(
            row=9, column=2, sticky="w", padx=4, pady=2
        )
        ttk.Label(grid, textvariable=frame.depositos_var).grid(row=9, column=3, sticky="w", padx=4, pady=2)
        frame.serial_box = ttk.LabelFrame(frame, text="Seriais das notas de R$ 200", padding=8)
        frame.serial_box.pack(fill="x", pady=6)
        ttk.Label(frame.serial_box, text="Seriais somados de todas as contagens.").pack(anchor="w")
        ttk.Label(frame, textvariable=frame.count_total_var, font=("", 12, "bold")).pack(anchor="e")
        frame.geral_entry_list: list[ttk.Entry] = []
        self.notebook.add(frame, text="Geral")
        self.geral_frame = frame

    def set_counts(self, counts: list[dict]) -> None:
        for tab in self.notebook.tabs():
            w = self.notebook.nametowidget(tab)
            if w is not self.geral_frame:
                self.notebook.forget(tab)
        self.counts = []
        self.geral_editado = False
        self.edit_geral_btn.configure(text="Editar Geral")
        self.geral_editado_label.pack_forget()
        for count in counts or []:
            if count.get("label") == "Geral":
                self.geral_editado = True
                self._apply_geral_data(count)
                continue
            self.add_count(count)
        self._refresh_geral()
        self._refresh_total()

    def get_counts(self) -> list[dict]:
        geral = self._collect_geral()
        rest = [self._collect_tab(self.notebook.nametowidget(tab)) for tab in self.notebook.tabs() if self.notebook.nametowidget(tab) is not self.geral_frame]
        return [geral] + rest

    def add_count(self, existing: dict | None = None) -> None:
        suffixes = [self.notebook.tab(t, "text") for t in self.notebook.tabs()]
        index = 1
        while f"Contagem {index}" in suffixes:
            index += 1
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
        depositos_str = str((existing or {}).get("depositos", "0")).replace(".", ",")
        frame.depositos_var = tk.StringVar(value=depositos_str)
        frame.count_total_var = tk.StringVar(value=f"Total: {format_money((existing or {}).get('total', 0))} (Moedas: {format_money((existing or {}).get('moedas', 0))})")
        ttk.Label(grid, text="Moedas").grid(row=8, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(grid, textvariable=moedas_var, width=10, state="readonly" if self.readonly else "normal").grid(
            row=8, column=2, sticky="w", padx=4, pady=2
        )
        ttk.Label(grid, textvariable=moedas_var).grid(row=8, column=3, sticky="w", padx=4, pady=2)
        moedas_var.trace_add("write", lambda *_args, f=frame: self._recalculate(f))
        ttk.Label(grid, text="Depositos").grid(row=9, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(grid, textvariable=frame.depositos_var, width=10, state="readonly" if self.readonly else "normal").grid(
            row=9, column=2, sticky="w", padx=4, pady=2
        )
        ttk.Label(grid, textvariable=frame.depositos_var).grid(row=9, column=3, sticky="w", padx=4, pady=2)
        frame.depositos_var.trace_add("write", lambda *_args, f=frame: self._recalculate(f))
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
            w = self.notebook.nametowidget(tab)
            if w is self.geral_frame and not self.geral_editado:
                continue
            data = self._collect_tab(w)
            qty_200 = int(data["notas"].get("200", 0) or 0)
            if not serials_valid(data["seriais_200"], qty_200):
                messagebox.showerror("Seriais obrigatorios", "Cada nota de R$ 200 precisa de um serial numerico com 5 digitos.")
                return False
        return True

    def _delete_tab(self, frame) -> None:
        if frame is self.geral_frame:
            return
        if messagebox.askyesno("Excluir contagem", "Deseja excluir esta contagem?"):
            self.notebook.forget(frame)
            self._refresh_geral()
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
        depositos = parse_money(frame.depositos_var.get())
        total += depositos
        return {
            "id": frame.count_id,
            "label": frame.label_var.get() or "Contagem",
            "criado_em": frame.created_at,
            "notas": notes,
            "seriais_200": [var.get() for var in frame.serial_vars if var.get()],
            "moedas": moedas,
            "depositos": depositos,
            "total": round(total, 2),
        }

    def _collect_geral(self) -> dict:
        if self.geral_editado:
            return self._collect_tab(self.geral_frame)
        total_notes: dict[str, int] = {str(d): 0 for d in DENOMINATIONS}
        total_moedas = 0.0
        total_depositos = 0.0
        all_serials: list[str] = []
        for tab in self.notebook.tabs():
            w = self.notebook.nametowidget(tab)
            if w is self.geral_frame:
                continue
            data = self._collect_tab(w)
            for d in DENOMINATIONS:
                total_notes[str(d)] += int(data["notas"].get(str(d), 0) or 0)
            total_moedas += data.get("moedas", 0) or 0
            total_depositos += data.get("depositos", 0) or 0
            all_serials.extend(data.get("seriais_200", []))
        grand = sum(total_notes[str(d)] * d for d in DENOMINATIONS) + total_moedas + total_depositos
        return {
            "id": self.geral_frame.count_id,
            "label": "Geral",
            "criado_em": self.geral_frame.created_at,
            "notas": total_notes,
            "seriais_200": all_serials,
            "moedas": round(total_moedas, 2),
            "depositos": round(total_depositos, 2),
            "total": round(grand, 2),
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
        frame.count_total_var.set(f"Total: {format_money(data['total'])} (Moedas: {format_money(data['moedas'])})")
        if frame is not self.geral_frame:
            self._refresh_geral()
        self._refresh_total()
        if self.on_change:
            self.on_change()

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

    def _refresh_geral(self) -> None:
        if self.geral_editado:
            return
        total_notes: dict[str, int] = {str(d): 0 for d in DENOMINATIONS}
        total_moedas = 0.0
        total_depositos = 0.0
        all_serials: list[str] = []
        for tab in self.notebook.tabs():
            w = self.notebook.nametowidget(tab)
            if w is self.geral_frame:
                continue
            data = self._collect_tab(w)
            for d in DENOMINATIONS:
                total_notes[str(d)] += int(data["notas"].get(str(d), 0) or 0)
            total_moedas += data.get("moedas", 0) or 0
            total_depositos += data.get("depositos", 0) or 0
            all_serials.extend(data.get("seriais_200", []))
        for d in DENOMINATIONS:
            qty_var, subtotal_var = self.geral_frame.vars[str(d)]
            qty_var.set(str(total_notes[str(d)]))
            subtotal_var.set(format_money(total_notes[str(d)] * d))
        self.geral_frame.moedas_var.set(str(total_moedas).replace(".", ","))
        self.geral_frame.depositos_var.set(str(total_depositos).replace(".", ","))
        grand = sum(total_notes[str(d)] * d for d in DENOMINATIONS) + total_moedas + total_depositos
        self.geral_frame.count_total_var.set(f"Total: {format_money(round(grand, 2))} (Moedas: {format_money(round(total_moedas, 2))})")
        for child in self.geral_frame.serial_box.winfo_children():
            child.destroy()
        if all_serials:
            ttk.Label(self.geral_frame.serial_box, text=", ".join(all_serials)).pack(anchor="w")
        else:
            ttk.Label(self.geral_frame.serial_box, text="Seriais somados de todas as contagens.").pack(anchor="w")

    def _apply_geral_data(self, count: dict) -> None:
        self.geral_editado = True
        self.edit_geral_btn.configure(text="Reverter ao automatico")
        self.geral_editado_label.pack(side="left", padx=4)
        notes = count.get("notas", {})
        for d in DENOMINATIONS:
            qty_var, subtotal_var = self.geral_frame.vars[str(d)]
            qty_var.set(str(int(notes.get(str(d), 0) or 0)))
            subtotal_var.set(format_money(int(notes.get(str(d), 0) or 0) * d))
        self.geral_frame.moedas_var.set(str(count.get("moedas", "0")).replace(".", ","))
        self.geral_frame.depositos_var.set(str(count.get("depositos", "0")).replace(".", ","))
        self.geral_frame.count_total_var.set(
            f"Total: {format_money(count.get('total', 0))} (Moedas: {format_money(count.get('moedas', 0))})"
        )
        for child in self.geral_frame.serial_box.winfo_children():
            child.destroy()
        serials = count.get("seriais_200", [])
        if serials:
            ttk.Label(self.geral_frame.serial_box, text=", ".join(serials)).pack(anchor="w")
        else:
            ttk.Label(self.geral_frame.serial_box, text="Seriais somados de todas as contagens.").pack(anchor="w")
        entradas = []
        for d in DENOMINATIONS:
            qty_var, _ = self.geral_frame.vars[str(d)]
            for w in self.geral_frame.winfo_children():
                if isinstance(w, ttk.Frame):
                    for child in w.winfo_children():
                        if isinstance(child, ttk.Entry) and child.cget("textvariable") == str(qty_var):
                            entradas.append(child)
        self.geral_frame.geral_entry_list = entradas

    def _edit_geral(self) -> None:
        if self.readonly:
            return
        if not self.geral_editado:
            if not messagebox.askyesno(
                "Editar Geral",
                "Isso ira desvincular o Geral da soma automatica das contagens.\n\n"
                "As alteracoes manuais no Geral NAO serao refletidas nas contagens individuais.\n\n"
                "Deseja continuar?",
            ):
                return
            self.geral_editado = True
            self.edit_geral_btn.configure(text="Reverter ao automatico")
            self.geral_editado_label.pack(side="left", padx=4)
            for d in DENOMINATIONS:
                qty_var, _ = self.geral_frame.vars[str(d)]
                for w in self.geral_frame.winfo_children():
                    if isinstance(w, ttk.Frame):
                        for child in w.winfo_children():
                            if isinstance(child, ttk.Entry) and child.cget("textvariable") == str(qty_var):
                                child.configure(state="normal")
                qty_var.trace_add("write", lambda *_a, f=self.geral_frame: self._recalculate(f))
            moedas_entry = None
            for w in self.geral_frame.winfo_children():
                if isinstance(w, ttk.Frame):
                    for child in w.winfo_children():
                        if isinstance(child, ttk.Entry) and hasattr(child, 'cget'):
                            try:
                                tv = child.cget("textvariable")
                                if tv == str(self.geral_frame.moedas_var):
                                    child.configure(state="normal")
                                    break
                            except Exception:
                                pass
            if moedas_entry:
                moedas_entry.configure(state="normal")
            self.geral_frame.moedas_var.trace_add("write", lambda *_a, f=self.geral_frame: self._recalculate(f))
        elif self.geral_editado:
            if messagebox.askyesno(
                "Reverter ao automatico",
                "Isso ira descartar as edicoes manuais do Geral e voltar a soma automatica.\n\nDeseja continuar?",
            ):
                self.geral_editado = False
                self.edit_geral_btn.configure(text="Editar Geral")
                self.geral_editado_label.pack_forget()
                for d in DENOMINATIONS:
                    qty_var, _ = self.geral_frame.vars[str(d)]
                    for w in self.geral_frame.winfo_children():
                        if isinstance(w, ttk.Frame):
                            for child in w.winfo_children():
                                if isinstance(child, ttk.Entry) and child.cget("textvariable") == str(qty_var):
                                    child.configure(state="readonly")
                    try:
                        qty_var.trace_remove("write", qty_var.trace_info()[0][1] if qty_var.trace_info() else None)
                    except Exception:
                        pass
                self._refresh_geral()
                self._refresh_total()

    def _refresh_total(self) -> None:
        geral = self._collect_geral()
        self.total_var.set(format_money(geral["total"]))
        if self.on_change:
            self.on_change()

    def _copy_image(self) -> None:
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            messagebox.showerror("Erro", "Instale pillow para gerar a imagem: pip install pillow")
            return

        geral = self._collect_geral()
        if geral["total"] == 0.0 and not self.geral_editado:
            counts_check = [self._collect_tab(self.notebook.nametowidget(t)) for t in self.notebook.tabs() if self.notebook.nametowidget(t) is not self.geral_frame]
            if not any(c["total"] > 0 for c in counts_check):
                messagebox.showwarning("Sem dados", "Nenhuma contagem registrada.")
                return

        notes = geral.get("notas", {})
        grand_total = geral.get("total", 0)

        row_h = 28
        pad = 16
        header_h = 48
        width = 340
        height = header_h + row_h + len(DENOMINATIONS) * row_h + 3 * row_h + pad * 2

        img = Image.new("RGB", (width, height), "#ffffff")
        draw = ImageDraw.Draw(img)
        try:
            font_title = ImageFont.truetype("arial.ttf", 18)
            font_body = ImageFont.truetype("arial.ttf", 14)
            font_bold = ImageFont.truetype("arialbd.ttf", 14)
        except Exception:
            font_title = ImageFont.load_default()
            font_body = ImageFont.load_default()
            font_bold = ImageFont.load_default()

        y = pad
        draw.text((pad, y), "Contagem de Dinheiro", fill="#212529", font=font_title)
        if self.caixa_data:
            y += row_h
            draw.text((pad, y), f"Data do caixa: {self.caixa_data}", fill="#6c757d", font=font_body)
        draw.line([(pad, y + 26), (width - pad, y + 26)], fill="#dee2e6", width=1)

        y = header_h + row_h
        col_w = (width - pad * 2) // 3
        for col, text in enumerate(["Cedula", "Qtde.", "Subtotal"]):
            x = pad + col * col_w
            draw.text((x + (col_w // 2) - 20, y), text, fill="#6c757d", font=font_bold)

        y += row_h
        draw.line([(pad, y), (width - pad, y)], fill="#dee2e6", width=1)

        for denom in DENOMINATIONS:
            qty = int(notes.get(str(denom), 0) or 0)
            subtotal = qty * denom
            texts = [f"R$ {denom}", str(qty), format_money(subtotal)]
            for col, text in enumerate(texts):
                x = pad + col * col_w
                draw.text((x + (col_w // 2) - 20, y + 4), text, fill="#212529", font=font_body)
            y += row_h

        draw.line([(pad, y), (width - pad, y)], fill="#dee2e6", width=1)
        y += 4
        draw.text((pad, y), "Total", fill="#212529", font=font_bold)
        draw.text((width - pad - 80, y), format_money(grand_total), fill="#0d6efd", font=font_bold)

        success = copy_image_to_clipboard(img)
        if success:
            messagebox.showinfo("Copiado", "Imagem copiada para a area de transferencia.")
        else:
            messagebox.showinfo(
                "Imagem gerada",
                "Nao foi possivel copiar para o clipboard. Salve a visualizacao como captura de tela.",
            )

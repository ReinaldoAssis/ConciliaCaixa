from __future__ import annotations

import threading
import tkinter as tk
from copy import deepcopy
from datetime import date, datetime
from tkinter import filedialog, messagebox, ttk
from uuid import uuid4

from constants_restaurante import (
    CATEGORIAS_RESTAURANTE,
    CATEGORIAS_RESTAURANTE_LABELS,
    CATEGORIA_CLASSIFICACAO,
    empty_categories_restaurante,
)
from parsers.restaurante_pagbank_csv import (
    aggregate_transactions,
    read_restaurante_transactions,
)
from utils import (
    date_to_br,
    date_to_iso,
    ensure_not_future,
    format_money,
    parse_date_input,
    parse_money,
)
from views.contagem import MoneyCountFrame


class ImportRestauranteFrame(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.caixa = self._new_model()
        self.imported_paths: dict[str, str] = {}
        self.readonly = False
        self._avulsos_data: list[dict] = []
        self._build()

    def _build(self) -> None:
        canvas = tk.Canvas(self, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.body = ttk.Frame(canvas, padding=14)
        self.body.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.body, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _on_mousewheel(event):
            if event.delta:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            else:
                canvas.yview_scroll(-3 if event.num == 4 else 3, "units")

        def _bind_recursive(widget):
            widget.bind("<MouseWheel>", _on_mousewheel, add="+")
            widget.bind("<Button-4>", lambda e: canvas.yview_scroll(-3, "units"), add="+")
            widget.bind("<Button-5>", lambda e: canvas.yview_scroll(3, "units"), add="+")
            for child in widget.winfo_children():
                _bind_recursive(child)

        _bind_recursive(canvas)
        _bind_recursive(self.body)
        self._rebind_scroll = lambda: _bind_recursive(self.body)

        header = ttk.Frame(self.body)
        header.pack(fill="x")
        ttk.Button(header, text="Voltar ao Historico", command=self.app.show_history_restaurante).pack(side="left")
        self.title_var = tk.StringVar(value="Novo Caixa - Restaurante")
        ttk.Label(header, textvariable=self.title_var, font=("", 18, "bold")).pack(side="left", padx=12)
        self.reopen_btn = ttk.Button(header, text="Reabrir para edicao", command=self._reopen)
        self.reopen_btn.pack(side="right")

        data_box = ttk.LabelFrame(self.body, text="A - Data da Conciliacao", padding=10)
        data_box.pack(fill="x", pady=10)
        ttk.Label(data_box, text="Data").pack(side="left")
        self.date_var = tk.StringVar()
        ttk.Entry(data_box, textvariable=self.date_var, width=14).pack(side="left", padx=8)
        ttk.Label(data_box, text="Turno").pack(side="left", padx=(16, 0))
        self.turno_var = tk.StringVar(value="Todos")
        self.turno_combo = ttk.Combobox(data_box, textvariable=self.turno_var, values=["T1", "T2", "Todos"], width=6, state="readonly")
        self.turno_combo.pack(side="left", padx=6)

        pagbank_box = ttk.LabelFrame(self.body, text="B - Relatorio PagBank (CSV) - Preenche coluna REAL", padding=10)
        pagbank_box.pack(fill="x", pady=6)
        self.pagbank_status = tk.StringVar(value="Nenhum arquivo importado.")
        top_row = ttk.Frame(pagbank_box)
        top_row.pack(fill="x")
        ttk.Label(top_row, textvariable=self.pagbank_status, wraplength=600).pack(side="left", fill="x", expand=True)
        ttk.Button(top_row, text="Selecionar Arquivo", command=self._choose_pagbank).pack(side="right", padx=4)
        ttk.Button(top_row, text="Remover", command=self._remove_pagbank).pack(side="right")

        sistema_box = ttk.LabelFrame(self.body, text="C - Conciliacao (Sistema = manual, Real = auto)", padding=10)
        sistema_box.pack(fill="x", pady=6)
        self.sistema_vars: dict[str, tk.StringVar] = {}
        self.real_labels: dict[str, tk.StringVar] = {}
        self.diff_labels: dict[str, tk.StringVar] = {}
        grid = ttk.Frame(sistema_box)
        grid.pack(fill="x")
        ttk.Label(grid, text="Categoria", font=("", 10, "bold")).grid(row=0, column=0, sticky="w", padx=3, pady=3)
        ttk.Label(grid, text="Classif.", font=("", 10, "bold")).grid(row=0, column=1, sticky="w", padx=3, pady=3)
        ttk.Label(grid, text="Sistema (R$)", font=("", 10, "bold")).grid(row=0, column=2, sticky="w", padx=3, pady=3)
        ttk.Label(grid, text="Real (R$)", font=("", 10, "bold")).grid(row=0, column=3, sticky="w", padx=3, pady=3)
        ttk.Label(grid, text="Diferença (R$)", font=("", 10, "bold")).grid(row=0, column=4, sticky="w", padx=3, pady=3)
        for idx, key in enumerate(CATEGORIAS_RESTAURANTE, start=1):
            label = CATEGORIAS_RESTAURANTE_LABELS[key]
            classif = CATEGORIA_CLASSIFICACAO[key]
            var = tk.StringVar()
            real_var = tk.StringVar(value="")
            diff_var = tk.StringVar(value="")
            self.sistema_vars[key] = var
            self.real_labels[key] = real_var
            self.diff_labels[key] = diff_var
            ttk.Label(grid, text=label).grid(row=idx, column=0, sticky="w", padx=3, pady=2)
            ttk.Label(grid, text=classif).grid(row=idx, column=1, sticky="w", padx=3, pady=2)
            entry = ttk.Entry(grid, textvariable=var, width=14)
            entry.grid(row=idx, column=2, sticky="w", padx=3, pady=2)
            ttk.Label(grid, textvariable=real_var, width=14, anchor="e").grid(row=idx, column=3, sticky="w", padx=3, pady=2)
            diff_color = "#198754"
            ttk.Label(grid, textvariable=diff_var, width=14, anchor="e", foreground=diff_color).grid(row=idx, column=4, sticky="w", padx=3, pady=2)
            var.trace_add("write", lambda *_a, k=key: self._apply_sistema(k))
        self.total_diff_var = tk.StringVar(value="")
        total_row = len(CATEGORIAS_RESTAURANTE) + 1
        sep = ttk.Separator(grid, orient="horizontal")
        sep.grid(row=total_row, column=0, columnspan=5, sticky="ew", pady=4)
        self.total_diff_label = ttk.Label(grid, textvariable=self.total_diff_var, font=("", 11, "bold"), foreground="#0d6efd")
        self.total_diff_label.grid(row=total_row + 1, column=3, columnspan=2, sticky="e", padx=3, pady=4)
        ttk.Label(grid, text="Diferença Total:", font=("", 11, "bold")).grid(row=total_row + 1, column=2, sticky="e", padx=3, pady=4)

        self.count_frame = MoneyCountFrame(self.body, on_change=self._on_contagem_change)
        self.count_frame.pack(fill="both", expand=True, pady=10)

        avulso_box = ttk.LabelFrame(self.body, text="D - Lancamentos Avulsos", padding=10)
        avulso_box.pack(fill="x", pady=6)
        form = ttk.Frame(avulso_box)
        form.pack(fill="x", pady=(0, 6))
        ttk.Label(form, text="Tipo").pack(side="left")
        self.avulso_tipo_var = tk.StringVar(value="RECEITA")
        self.avulso_tipo_combo = ttk.Combobox(form, textvariable=self.avulso_tipo_var, values=["RECEITA", "DESPESA"], width=9, state="readonly")
        self.avulso_tipo_combo.pack(side="left", padx=3)
        ttk.Label(form, text="Coluna").pack(side="left", padx=(8, 0))
        self.avulso_coluna_var = tk.StringVar(value="sistema")
        self.avulso_coluna_combo = ttk.Combobox(form, textvariable=self.avulso_coluna_var, values=["sistema", "real"], width=9, state="readonly")
        self.avulso_coluna_combo.pack(side="left", padx=3)
        ttk.Label(form, text="Descricao").pack(side="left", padx=(8, 0))
        self.avulso_desc_var = tk.StringVar()
        self.avulso_desc_entry = ttk.Entry(form, textvariable=self.avulso_desc_var, width=16)
        self.avulso_desc_entry.pack(side="left", padx=3)
        ttk.Label(form, text="Valor").pack(side="left", padx=(8, 0))
        self.avulso_valor_var = tk.StringVar()
        self.avulso_valor_entry = ttk.Entry(form, textvariable=self.avulso_valor_var, width=10)
        self.avulso_valor_entry.pack(side="left", padx=3)
        ttk.Label(form, text="Vincular a").pack(side="left", padx=(8, 0))
        cat_options = [CATEGORIAS_RESTAURANTE_LABELS[k] for k in CATEGORIAS_RESTAURANTE] + ["Nova categoria..."]
        self.avulso_cat_var = tk.StringVar(value=cat_options[0])
        self.avulso_cat_combo = ttk.Combobox(form, textvariable=self.avulso_cat_var, values=cat_options, width=20, state="readonly")
        self.avulso_cat_combo.pack(side="left", padx=3)
        self.avulso_nova_var = tk.StringVar()
        self.avulso_add_btn = ttk.Button(form, text="Adicionar", command=self._add_avulso)
        self.avulso_add_btn.pack(side="left", padx=(8, 0))
        self.nova_cat_row = ttk.Frame(avulso_box)
        self.nova_cat_label = ttk.Label(self.nova_cat_row, text="Nome da nova categoria:")
        self.nova_cat_label.pack(side="left")
        self.avulso_nova_entry = ttk.Entry(self.nova_cat_row, textvariable=self.avulso_nova_var, width=16)
        self.avulso_nova_entry.pack(side="left", padx=(6, 0))
        self.avulso_cat_var.trace_add("write", lambda *_args: self._on_avulso_cat_change())

        self.avulsos_tree = ttk.Treeview(avulso_box, columns=("tipo", "coluna", "desc", "valor", "cat"), show="headings", height=4)
        self.avulsos_tree.heading("tipo", text="Tipo")
        self.avulsos_tree.heading("coluna", text="Coluna")
        self.avulsos_tree.heading("desc", text="Descricao")
        self.avulsos_tree.heading("valor", text="Valor")
        self.avulsos_tree.heading("cat", text="Categoria")
        self.avulsos_tree.column("tipo", width=60, anchor="center")
        self.avulsos_tree.column("coluna", width=60, anchor="center")
        self.avulsos_tree.column("desc", width=140, anchor="w")
        self.avulsos_tree.column("valor", width=90, anchor="center")
        self.avulsos_tree.column("cat", width=160, anchor="w")
        self.avulsos_tree.pack(fill="x", pady=(6, 0))
        self.avulso_remove_btn = ttk.Button(avulso_box, text="Remover selecionado", command=self._remove_avulso)
        self.avulso_remove_btn.pack(anchor="w", pady=(4, 0))

        footer = ttk.Frame(self.body)
        footer.pack(fill="x", pady=12)
        ttk.Button(footer, text="Salvar Rascunho", command=self.save_draft).pack(side="left")
        self.result_btn = ttk.Button(footer, text="Ver Resultado", command=self.show_result)
        self.result_btn.pack(side="right")

        self.progress = ttk.Progressbar(self.body, mode="indeterminate")
        self.progress.pack(fill="x", pady=(0, 10))
        self.progress.pack_forget()

        self._rebind_scroll()

    def load_caixa(self, caixa: dict | None = None) -> None:
        self.caixa = deepcopy(caixa) if caixa else self._new_model()
        self.imported_paths = {}
        self.readonly = self.caixa.get("status") == "conciliado"
        self._avulsos_data = list(self.caixa.get("lancamentos_avulsos") or [])
        self.date_var.set(date_to_br(self.caixa["data"]))
        turno_raw = self.caixa.get("turno")
        if turno_raw == 1:
            self.turno_var.set("T1")
        elif turno_raw == 2:
            self.turno_var.set("T2")
        else:
            self.turno_var.set("Todos")
        self.turno_combo.configure(state="disabled" if self.readonly else "readonly")
        title = "Caixa Conciliado"
        if not self.readonly:
            turno = self.caixa.get("turno")
            title = f"Caixa em Edicao - Turno {turno}" if turno else "Caixa em Edicao"
        self.title_var.set(title)
        self.count_frame.readonly = self.readonly
        self.count_frame.caixa_data = date_to_br(self.caixa["data"])
        self.count_frame.set_counts(self.caixa.get("contagens_dinheiro", []))
        self._sync_dinheiro_real()
        self._refresh_total_diff()
        self._refresh_avulsos_tree()

        for key in CATEGORIAS_RESTAURANTE:
            valores = self.caixa["categorias"].get(key, {})
            v_sistema = valores.get("sistema", 0) or 0
            v_real = valores.get("real", 0) or 0
            self.sistema_vars[key].set(str(v_sistema).replace(".", ",") if v_sistema else "")
            self.real_labels[key].set(format_money(v_real) if v_real else "")
            self._refresh_diff(key)

        avulso_state = "disabled" if self.readonly else "readonly"
        avulso_entry_state = "disabled" if self.readonly else "normal"
        self.avulso_tipo_combo.configure(state=avulso_state)
        self.avulso_coluna_combo.configure(state=avulso_state)
        self.avulso_desc_entry.configure(state=avulso_entry_state)
        self.avulso_valor_entry.configure(state=avulso_entry_state)
        self.avulso_cat_combo.configure(state=avulso_state)
        self.nova_cat_row.pack_forget()
        self.avulso_add_btn.configure(state=avulso_entry_state)
        self.avulso_remove_btn.configure(state=avulso_entry_state)
        self.avulso_desc_var.set("")
        self.avulso_valor_var.set("")
        self.avulso_nova_var.set("")

        had_data = any(
            self.caixa["categorias"].get(key, {}).get("real", 0) for key in CATEGORIAS_RESTAURANTE
        )
        self.pagbank_status.set(
            "Dados PagBank carregados do registro." if had_data else "Nenhum arquivo importado."
        )
        self.reopen_btn.configure(state="normal" if self.readonly else "disabled")
        self.result_btn.configure(state="normal")

    def save_draft(self) -> None:
        if not self._collect_common("rascunho"):
            return
        self.app.repo_restaurante.save(self.caixa)
        messagebox.showinfo("Rascunho salvo", "O caixa foi salvo como rascunho.")
        self.app.show_history_restaurante()

    def show_result(self) -> None:
        if self._collect_common(self.caixa.get("status", "rascunho")):
            self.app.show_result_restaurante(self.caixa)

    def _choose_pagbank(self) -> None:
        if self.readonly:
            messagebox.showinfo("Somente leitura", "Reabra o caixa para edicao antes de importar arquivos.")
            return

        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv"), ("Todos", "*.*")])
        if not path:
            return
        if self.imported_paths.get("pagbank") == path:
            messagebox.showwarning("Arquivo repetido", "Este arquivo ja foi importado nesta secao.")
            return

        turno = self.turno_var.get()
        hora_ini = None
        hora_fim = None
        if turno in ("T1", "T2"):
            hora_ini, hora_fim = self._ask_time_range(turno)
            if hora_ini is None:
                return

        self.progress.pack(fill="x", pady=(0, 10))
        self.progress.start(10)

        def worker():
            try:
                transactions = read_restaurante_transactions(path)
                if hora_ini and hora_fim:
                    transactions = [
                        t for t in transactions
                        if t["dt"] and hora_ini <= t["dt"].time() <= hora_fim
                    ]
                if not transactions:
                    self.after(0, lambda: self._import_failed(
                        "Nenhuma transacao encontrada no intervalo informado."
                    ))
                    return
                result = aggregate_transactions(transactions)
                self.after(0, lambda: self._apply_pagbank_import(path, result))
            except Exception as exc:
                self.after(0, lambda: self._import_failed(str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _ask_time_range(self, turno: str) -> tuple:
        dialog = tk.Toplevel(self)
        dialog.title(f"Horario de Importacao - {turno}")
        dialog.resizable(False, False)
        dialog.transient(self)

        frame = ttk.Frame(dialog, padding=20)
        frame.pack()

        ttk.Label(frame, text=f"{turno} - Informe o intervalo de horario:", font=("", 11, "bold")).pack(pady=(0, 12))

        ini_frame = ttk.Frame(frame)
        ini_frame.pack(fill="x", pady=4)
        ttk.Label(ini_frame, text="Horario Inicial (hh:mm)").pack(side="left")
        ini_var = tk.StringVar(value="")
        ini_entry = ttk.Entry(ini_frame, textvariable=ini_var, width=8)
        ini_entry.pack(side="left", padx=8)

        fim_frame = ttk.Frame(frame)
        fim_frame.pack(fill="x", pady=4)
        ttk.Label(fim_frame, text="Horario Final (hh:mm)").pack(side="left")
        fim_var = tk.StringVar(value="")
        fim_entry = ttk.Entry(fim_frame, textvariable=fim_var, width=8)
        fim_entry.pack(side="left", padx=8)

        def _validate_hhmm(var):
            def _on_key(*_args):
                val = var.get()
                filtered = "".join(c for c in val if c.isdigit() or c == ":")
                if len(filtered) == 2 and ":" not in filtered[:2]:
                    filtered = filtered[:2] + ":"
                filtered = filtered[:5]
                if filtered != val:
                    var.set(filtered)
            return _on_key

        ini_var.trace_add("write", _validate_hhmm(ini_var))
        fim_var.trace_add("write", _validate_hhmm(fim_var))

        result = {"ini": None, "fim": None}

        def _confirm():
            ini = ini_var.get().strip()
            fim = fim_var.get().strip()
            try:
                ini_t = datetime.strptime(ini, "%H:%M").time()
                fim_t = datetime.strptime(fim, "%H:%M").time()
            except ValueError:
                messagebox.showwarning("Formato invalido", "Informe os horarios no formato hh:mm (ex: 08:00).", parent=dialog)
                return
            if ini_t > fim_t:
                messagebox.showwarning("Intervalo invalido", "O horario inicial deve ser menor que o final.", parent=dialog)
                return
            result["ini"] = ini_t
            result["fim"] = fim_t
            dialog.destroy()

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=(12, 0))
        ttk.Button(btn_frame, text="Confirmar", command=_confirm).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Cancelar", command=dialog.destroy).pack(side="left", padx=4)

        ini_entry.focus_set()
        dialog.grab_set()
        dialog.wait_window()
        return result["ini"], result["fim"]

    def _apply_pagbank_import(self, path: str, result: dict) -> None:
        self.progress.stop()
        self.progress.pack_forget()
        self.imported_paths["pagbank"] = path
        incoming = result["categorias"]
        for key in CATEGORIAS_RESTAURANTE:
            if key == "DINHEIRO":
                continue
            value = round(float((incoming.get(key) or {}).get("real", 0) or 0), 2)
            if value:
                self.caixa["categorias"][key]["real"] = value
            self.real_labels[key].set(format_money(value) if value else "")
            self._refresh_diff(key)
        self._sync_dinheiro_real()
        self._refresh_total_diff()
        summary = f"{result['registros_aprovados']} registros aprovados agrupados."
        self.pagbank_status.set(summary)

    def _import_failed(self, message: str) -> None:
        self.progress.stop()
        self.progress.pack_forget()
        messagebox.showerror("Erro de importacao", message)

    def _remove_pagbank(self) -> None:
        if self.readonly:
            messagebox.showinfo("Somente leitura", "Reabra o caixa para edicao antes de remover arquivos.")
            return
        self.imported_paths.pop("pagbank", None)
        for key in CATEGORIAS_RESTAURANTE:
            if key == "DINHEIRO":
                continue
            self.caixa["categorias"][key]["real"] = 0.0
            self.real_labels[key].set("")
            self._refresh_diff(key)
        self._sync_dinheiro_real()
        self._refresh_total_diff()
        self.pagbank_status.set("Nenhum arquivo importado.")

    def _apply_sistema(self, key: str) -> None:
        text = self.sistema_vars[key].get().strip()
        if not text:
            self.caixa["categorias"][key]["sistema"] = 0.0
        else:
            try:
                value = parse_money(text)
            except ValueError:
                return
            self.caixa["categorias"][key]["sistema"] = round(value, 2)
        self._refresh_diff(key)

    def _refresh_diff(self, key: str) -> None:
        real = self.caixa["categorias"][key].get("real", 0) or 0
        sistema = self.caixa["categorias"][key].get("sistema", 0) or 0
        diff = round(real - sistema, 2)
        self.diff_labels[key].set(format_money(diff) if diff else ("-" if real or sistema else ""))
        self._refresh_total_diff()

    def _refresh_total_diff(self) -> None:
        total = 0.0
        for key in CATEGORIAS_RESTAURANTE:
            real = self.caixa["categorias"][key].get("real", 0) or 0
            sistema = self.caixa["categorias"][key].get("sistema", 0) or 0
            total += round(real - sistema, 2)
        self.total_diff_var.set(format_money(round(total, 2)))
        if abs(total) < 0.005:
            self.total_diff_label.configure(foreground="#198754")
        else:
            self.total_diff_label.configure(foreground="#dc3545")

    def _sync_dinheiro_real(self) -> None:
        contagens = self.count_frame.get_counts()
        geral = next((c for c in contagens if c.get("label") == "Geral"), None)
        dinheiro_real = round(geral.get("total", 0) if geral else 0, 2)
        self.caixa["categorias"]["DINHEIRO"]["real"] = dinheiro_real
        self.real_labels["DINHEIRO"].set(format_money(dinheiro_real) if dinheiro_real else "")
        self._refresh_diff("DINHEIRO")

    def _on_contagem_change(self) -> None:
        self._sync_dinheiro_real()

    def _collect_raw_date(self) -> str | None:
        try:
            parsed = parse_date_input(self.date_var.get())
            ensure_not_future(parsed)
            return date_to_iso(parsed)
        except Exception as exc:
            messagebox.showerror("Dados invalidos", str(exc))
            return None

    def _collect_common(self, status: str) -> bool:
        try:
            parsed = parse_date_input(self.date_var.get())
            ensure_not_future(parsed)
            for key in CATEGORIAS_RESTAURANTE:
                self._apply_sistema(key)
            if not self.count_frame.validate_counts():
                return False
            self.caixa["data"] = date_to_iso(parsed)
            self.caixa["status"] = status
            self.caixa["contagens_dinheiro"] = self.count_frame.get_counts()
            turno_str = self.turno_var.get()
            self.caixa["turno"] = 1 if turno_str == "T1" else (2 if turno_str == "T2" else None)
            self.caixa["lancamentos_avulsos"] = self._collect_avulsos()
            self._sync_dinheiro_real()
            return True
        except Exception as exc:
            messagebox.showerror("Dados invalidos", str(exc))
            return False

    def _reopen(self) -> None:
        if messagebox.askyesno("Reabrir caixa", "Deseja reabrir este caixa conciliado para edicao?"):
            self.caixa["status"] = "rascunho"
            self.readonly = False
            self.load_caixa(self.caixa)

    @staticmethod
    def _new_model() -> dict:
        return {
            "data": date.today().isoformat(),
            "status": "rascunho",
            "turno": None,
            "categorias": empty_categories_restaurante(),
            "contagens_dinheiro": [],
            "lancamentos_avulsos": [],
            "observacoes": "",
        }

    def _on_avulso_cat_change(self) -> None:
        if self.readonly:
            return
        if self.avulso_cat_var.get() == "Nova categoria...":
            self.nova_cat_row.pack(fill="x", pady=(4, 0))
        else:
            self.nova_cat_row.pack_forget()
            self.avulso_nova_var.set("")

    def _add_avulso(self) -> None:
        if self.readonly:
            return
        desc = self.avulso_desc_var.get().strip()
        try:
            valor = parse_money(self.avulso_valor_var.get())
        except ValueError:
            messagebox.showwarning("Valor invalido", "Informe um valor monetario valido.")
            return
        if valor <= 0:
            messagebox.showwarning("Valor invalido", "O valor deve ser maior que zero.")
            return
        tipo = self.avulso_tipo_var.get()
        coluna = self.avulso_coluna_var.get()
        cat_label = self.avulso_cat_var.get()
        if cat_label == "Nova categoria...":
            nova = self.avulso_nova_var.get().strip().upper()
            if not nova:
                messagebox.showwarning("Nome obrigatorio", "Informe o nome da nova categoria.")
                return
            entry = {
                "id": str(uuid4()),
                "descricao": desc,
                "valor": round(valor, 2),
                "tipo": tipo,
                "coluna": coluna,
                "categoria_vinculada": None,
                "categoria_nova": nova,
            }
        else:
            key = [k for k, v in CATEGORIAS_RESTAURANTE_LABELS.items() if v == cat_label][0]
            entry = {
                "id": str(uuid4()),
                "descricao": desc,
                "valor": round(valor, 2),
                "tipo": tipo,
                "coluna": coluna,
                "categoria_vinculada": key,
                "categoria_nova": None,
            }
        self._avulsos_data.append(entry)
        self._refresh_avulsos_tree()
        self.avulso_desc_var.set("")
        self.avulso_valor_var.set("")
        self.avulso_nova_var.set("")

    def _remove_avulso(self) -> None:
        if self.readonly:
            return
        selected = self.avulsos_tree.selection()
        if not selected:
            return
        item_id = selected[0]
        idx = int(item_id)
        self._avulsos_data.pop(idx)
        self._refresh_avulsos_tree()

    def _refresh_avulsos_tree(self) -> None:
        for row in self.avulsos_tree.get_children():
            self.avulsos_tree.delete(row)
        for idx, entry in enumerate(self._avulsos_data):
            if entry.get("categoria_vinculada"):
                cat_display = CATEGORIAS_RESTAURANTE_LABELS.get(
                    entry["categoria_vinculada"], entry["categoria_vinculada"]
                )
            else:
                cat_display = entry.get("categoria_nova", "(nova)")
            self.avulsos_tree.insert(
                "", "end", iid=str(idx),
                values=(
                    entry["tipo"],
                    entry.get("coluna", "sistema"),
                    entry["descricao"],
                    format_money(entry["valor"]),
                    cat_display,
                ),
            )

    def _collect_avulsos(self) -> list[dict]:
        return list(self._avulsos_data)

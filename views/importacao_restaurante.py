from __future__ import annotations

import threading
import tkinter as tk
from copy import deepcopy
from datetime import date
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
    parse_restaurante_pagbank_csv,
    split_transactions_by_time,
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

        canvas.bind("<MouseWheel>", _on_mousewheel)
        canvas.bind("<Button-4>", lambda e: canvas.yview_scroll(-3, "units"))
        canvas.bind("<Button-5>", lambda e: canvas.yview_scroll(3, "units"))
        self.body.bind("<MouseWheel>", _on_mousewheel)
        self.body.bind("<Button-4>", lambda e: canvas.yview_scroll(-3, "units"))
        self.body.bind("<Button-5>", lambda e: canvas.yview_scroll(3, "units"))

        header = ttk.Frame(self.body)
        header.pack(fill="x")
        ttk.Button(header, text="Voltar ao Historico", command=self.app.show_history_restaurante).pack(side="left")
        self.title_var = tk.StringVar(value="Novo Caixa - Restaurante")
        ttk.Label(header, textvariable=self.title_var, font=("", 18, "bold")).pack(side="left", padx=12)
        self.reopen_btn = ttk.Button(header, text="Reabrir para edicao", command=self._reopen)
        self.reopen_btn.pack(side="right")

        data_box = ttk.LabelFrame(self.body, text="A - Data da Conciliacao", padding=10)
        data_box.pack(fill="x", pady=10)
        self.date_var = tk.StringVar()
        ttk.Label(data_box, text="Data").pack(side="left")
        ttk.Entry(data_box, textvariable=self.date_var, width=14).pack(side="left", padx=8)

        pagbank_box = ttk.LabelFrame(self.body, text="B - Relatorio PagBank (CSV) - Preenche coluna REAL", padding=10)
        pagbank_box.pack(fill="x", pady=6)
        self.pagbank_status = tk.StringVar(value="Nenhum arquivo importado.")
        top_row = ttk.Frame(pagbank_box)
        top_row.pack(fill="x")
        ttk.Label(top_row, textvariable=self.pagbank_status, wraplength=600).pack(side="left", fill="x", expand=True)
        ttk.Button(top_row, text="Selecionar Arquivo", command=self._choose_pagbank).pack(side="right", padx=4)
        ttk.Button(top_row, text="Remover", command=self._remove_pagbank).pack(side="right")
        split_row = ttk.Frame(pagbank_box)
        split_row.pack(fill="x", pady=(6, 0))
        self.split_var = tk.BooleanVar(value=False)
        self.split_cb = ttk.Checkbutton(
            split_row, text="Dividir em turnos", variable=self.split_var, command=self._on_split_toggle
        )
        self.split_cb.pack(side="left")
        ttk.Label(split_row, text="Fechamento 1° turno (HH:MM)").pack(side="left", padx=(16, 0))
        self.split_time_var = tk.StringVar(value="15:00")
        self.split_time_entry = ttk.Entry(split_row, textvariable=self.split_time_var, width=8)

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

        self.count_frame = MoneyCountFrame(self.body)
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

        self.split_time_entry.pack_forget()

    def load_caixa(self, caixa: dict | None = None) -> None:
        self.caixa = deepcopy(caixa) if caixa else self._new_model()
        self.imported_paths = {}
        self.readonly = self.caixa.get("status") == "conciliado"
        self._avulsos_data = list(self.caixa.get("lancamentos_avulsos") or [])
        self.date_var.set(date_to_br(self.caixa["data"]))
        title = "Caixa Conciliado"
        if not self.readonly:
            turno = self.caixa.get("turno")
            title = f"Caixa em Edicao - Turno {turno}" if turno else "Caixa em Edicao"
        self.title_var.set(title)
        self.count_frame.readonly = self.readonly
        self.count_frame.caixa_data = date_to_br(self.caixa["data"])
        self.count_frame.set_counts(self.caixa.get("contagens_dinheiro", []))
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

        if self.split_var.get():
            self._import_with_split()
            return

        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv"), ("Todos", "*.*")])
        if not path:
            return
        if self.imported_paths.get("pagbank") == path:
            messagebox.showwarning("Arquivo repetido", "Este arquivo ja foi importado nesta secao.")
            return
        self.progress.pack(fill="x", pady=(0, 10))
        self.progress.start(10)

        def worker():
            try:
                result = parse_restaurante_pagbank_csv(path)
                self.after(0, lambda: self._apply_pagbank_import(path, result))
            except Exception as exc:
                self.after(0, lambda: self._import_failed(str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _import_with_split(self) -> None:
        cutoff = self.split_time_var.get().strip()
        if not cutoff:
            messagebox.showwarning("Horario obrigatorio", "Informe o horario de fechamento do 1° turno (HH:MM).")
            return
        try:
            from datetime import datetime
            datetime.strptime(cutoff, "%H:%M")
        except ValueError:
            messagebox.showwarning("Horario invalido", f"Formato invalido: {cutoff!r}. Use HH:MM (ex: 15:00).")
            return

        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv"), ("Todos", "*.*")])
        if not path:
            return
        if self.imported_paths.get("pagbank") == path:
            messagebox.showwarning("Arquivo repetido", "Este arquivo ja foi importado nesta secao.")
            return
        self.progress.pack(fill="x", pady=(0, 10))
        self.progress.start(10)

        def worker():
            try:
                first_tx, second_tx = split_transactions_by_time(path, cutoff)
                self.after(0, lambda: self._apply_split_import(path, first_tx, second_tx, cutoff))
            except Exception as exc:
                self.after(0, lambda: self._import_failed(str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_pagbank_import(self, path: str, result: dict) -> None:
        self.progress.stop()
        self.progress.pack_forget()
        self.imported_paths["pagbank"] = path
        incoming = result["categorias"]
        for key in CATEGORIAS_RESTAURANTE:
            value = round(float((incoming.get(key) or {}).get("real", 0) or 0), 2)
            if value:
                self.caixa["categorias"][key]["real"] = value
            self.real_labels[key].set(format_money(value) if value else "")
            self._refresh_diff(key)
        summary = f"{result['registros_aprovados']} registros aprovados agrupados."
        self.pagbank_status.set(summary)

    def _apply_split_import(self, path: str, first_tx: list[dict], second_tx: list[dict], cutoff: str) -> None:
        self.progress.stop()
        self.progress.pack_forget()

        if not first_tx or not second_tx:
            messagebox.showwarning(
                "Divisao incompleta",
                f"Nao foi possivel dividir: {len(first_tx)} transacoes no 1° turno, {len(second_tx)} no 2°."
            )
            return

        result1 = aggregate_transactions(first_tx)
        result2 = aggregate_transactions(second_tx)

        base_data = self._collect_raw_date()
        if not base_data:
            return

        caixa1 = {
            "data": base_data,
            "status": "rascunho",
            "turno": 1,
            "categorias": empty_categories_restaurante(),
            "contagens_dinheiro": [],
            "lancamentos_avulsos": [],
            "observacoes": f"1° turno (ate {cutoff})",
        }
        caixa2 = {
            "data": base_data,
            "status": "rascunho",
            "turno": 2,
            "categorias": empty_categories_restaurante(),
            "contagens_dinheiro": [],
            "lancamentos_avulsos": [],
            "observacoes": f"2° turno (apos {cutoff})",
        }

        for key in CATEGORIAS_RESTAURANTE:
            caixa1["categorias"][key]["real"] = round(
                float((result1["categorias"].get(key) or {}).get("real", 0) or 0), 2
            )
            caixa2["categorias"][key]["real"] = round(
                float((result2["categorias"].get(key) or {}).get("real", 0) or 0), 2
            )

        self.app.repo_restaurante.save(caixa2)
        self.imported_paths["pagbank"] = path
        self.caixa = deepcopy(caixa1)
        self.caixa["id"] = str(uuid4())

        for key in CATEGORIAS_RESTAURANTE:
            v_real = caixa1["categorias"][key]["real"]
            self.sistema_vars[key].set("")
            self.real_labels[key].set(format_money(v_real) if v_real else "")
            self._refresh_diff(key)
        self.caixa["categorias"] = caixa1["categorias"]

        self.title_var.set(f"Caixa em Edicao - Turno 1 (ate {cutoff})")
        self.pagbank_status.set(
            f"1° turno: {result1['registros_aprovados']} registros | "
            f"2° turno salvo como rascunho: {result2['registros_aprovados']} registros."
        )

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
            self.caixa["categorias"][key]["real"] = 0.0
            self.real_labels[key].set("")
            self._refresh_diff(key)
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
            self.caixa["lancamentos_avulsos"] = self._collect_avulsos()
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

    def _on_split_toggle(self) -> None:
        if self.split_var.get():
            self.split_time_entry.pack(side="left", padx=6)
        else:
            self.split_time_entry.pack_forget()

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

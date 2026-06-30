from __future__ import annotations

import threading
import tkinter as tk
from copy import deepcopy
from datetime import date
from tkinter import filedialog, messagebox, ttk
from uuid import uuid4

from constants import CATEGORIES, CATEGORY_LABELS, empty_categories
from parsers import parse_caixa_csv, parse_pagbank_csv, parse_premmia_file
from utils import date_to_br, date_to_iso, ensure_not_future, format_money, parse_date_input, parse_money
from views.contagem import MoneyCountFrame


class ImportFrame(ttk.Frame):
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
        ttk.Button(header, text="Voltar ao Historico", command=self.app.show_history).pack(side="left")
        self.title_var = tk.StringVar(value="Novo Caixa")
        ttk.Label(header, textvariable=self.title_var, font=("", 18, "bold")).pack(side="left", padx=12)
        self.reopen_btn = ttk.Button(header, text="Reabrir para edicao", command=self._reopen)
        self.reopen_btn.pack(side="right")

        data_box = ttk.LabelFrame(self.body, text="A - Data da Conciliacao", padding=10)
        data_box.pack(fill="x", pady=10)
        self.date_var = tk.StringVar()
        ttk.Label(data_box, text="Data").pack(side="left")
        ttk.Entry(data_box, textvariable=self.date_var, width=14).pack(side="left", padx=8)

        self.caixa_status = self._file_section(
            "caixa",
            "B - Relatorio do Sistema Interno (CAIXA CSV)",
            lambda: self._choose_file("caixa", parse_caixa_csv, [("CSV", "*.csv"), ("Todos", "*.*")]),
        )
        self.pagbank_status = self._file_section(
            "pagbank",
            "C - Relatorio PagBank (CSV)",
            lambda: self._choose_file("pagbank", parse_pagbank_csv, [("CSV", "*.csv"), ("Todos", "*.*")]),
        )

        fit_box = ttk.LabelFrame(self.body, text="D - FitCard", padding=10)
        fit_box.pack(fill="x", pady=6)
        ttk.Label(fit_box, text="Digite o valor total do FitCard (lado do site/adquirente)").pack(anchor="w")
        row = ttk.Frame(fit_box)
        row.pack(fill="x", pady=(6, 0))
        self.fitcard_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.fitcard_var, width=16).pack(side="left")
        self.fitcard_ok = tk.StringVar(value="")
        ttk.Label(row, textvariable=self.fitcard_ok).pack(side="left", padx=8)
        self.fitcard_var.trace_add("write", lambda *_args: self._apply_fitcard())

        self.premmia_status = self._file_section(
            "premmia",
            "E - Relatorio Premmia (XLS)",
            lambda: self._choose_file("premmia", parse_premmia_file, [("Premmia", "*.xls *.XLS *.csv *.CSV"), ("Todos", "*.*")]),
        )

        avulso_box = ttk.LabelFrame(self.body, text="F - Lancamentos Avulsos", padding=10)
        avulso_box.pack(fill="x", pady=6)
        form = ttk.Frame(avulso_box)
        form.pack(fill="x", pady=(0, 6))
        ttk.Label(form, text="Tipo").pack(side="left")
        self.avulso_tipo_var = tk.StringVar(value="RECEITA")
        self.avulso_tipo_combo = ttk.Combobox(form, textvariable=self.avulso_tipo_var, values=["RECEITA", "DESPESA"], width=9, state="readonly")
        self.avulso_tipo_combo.pack(side="left", padx=3)
        ttk.Label(form, text="Coluna").pack(side="left", padx=(8, 0))
        self.avulso_coluna_var = tk.StringVar(value="sistema")
        self.avulso_coluna_combo = ttk.Combobox(form, textvariable=self.avulso_coluna_var, values=["sistema", "site"], width=9, state="readonly")
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
        cat_options = [CATEGORY_LABELS[k] for k in CATEGORIES] + ["Nova categoria..."]
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
        self._toggle_nova_categoria_visibility()
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

        self.count_frame = MoneyCountFrame(self.body)
        self.count_frame.pack(fill="both", expand=True, pady=10)

        footer = ttk.Frame(self.body)
        footer.pack(fill="x", pady=12)
        ttk.Button(footer, text="Salvar Rascunho", command=self.save_draft).pack(side="left")
        self.result_btn = ttk.Button(footer, text="Ver Resultado", command=self.show_result)
        self.result_btn.pack(side="right")

        self.progress = ttk.Progressbar(self.body, mode="indeterminate")
        self.progress.pack(fill="x", pady=(0, 10))
        self.progress.pack_forget()

    def load_caixa(self, caixa: dict | None = None) -> None:
        self.caixa = deepcopy(caixa) if caixa else self._new_model()
        self.imported_paths = {}
        self.readonly = self.caixa.get("status") == "conciliado"
        self._avulsos_data = list(self.caixa.get("lancamentos_avulsos") or [])
        self.date_var.set(date_to_br(self.caixa["data"]))
        self.fitcard_var.set(str(self.caixa.get("fitcard_total", 0)).replace(".", ",") if self.caixa.get("fitcard_total") else "")
        self.title_var.set("Caixa Conciliado" if self.readonly else "Caixa em Edicao")
        self.count_frame.readonly = self.readonly
        self.count_frame.caixa_data = date_to_br(self.caixa["data"])
        self.count_frame.set_counts(self.caixa.get("contagens_dinheiro", []))
        self._refresh_avulsos_tree()
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
        self._set_status(self.caixa_status, "Importe o arquivo CAIXA CSV." if not caixa else "Dados do CAIXA carregados do registro.")
        self._set_status(self.pagbank_status, "Importe o arquivo PagBank CSV." if not caixa else "Dados PagBank carregados do registro.")
        self._set_status(self.premmia_status, "Importe o arquivo Premmia XLS." if not caixa else "Dados Premmia carregados do registro.")
        self.reopen_btn.configure(state="normal" if self.readonly else "disabled")
        self.result_btn.configure(state="normal" if caixa or self._has_system_data() else "disabled")

    def save_draft(self) -> None:
        if not self._collect_common("rascunho"):
            return
        if self._confirm_same_date():
            self.app.repo.save(self.caixa)
            messagebox.showinfo("Rascunho salvo", "O caixa foi salvo como rascunho.")
            self.app.show_history()

    def show_result(self) -> None:
        if not self._has_system_data():
            messagebox.showerror("CAIXA obrigatorio", "Importe o CSV do sistema interno antes de ver o resultado.")
            return
        if self._collect_common(self.caixa.get("status", "rascunho")):
            self.app.show_result(self.caixa)

    def _file_section(self, section: str, title: str, command):
        box = ttk.LabelFrame(self.body, text=title, padding=10)
        box.pack(fill="x", pady=6)
        status = tk.StringVar(value="Nenhum arquivo importado.")
        ttk.Label(box, textvariable=status, wraplength=820).pack(side="left", fill="x", expand=True)
        ttk.Button(box, text="Selecionar Arquivo", command=command).pack(side="right", padx=4)
        ttk.Button(box, text="Remover", command=lambda s=section, v=status: self._remove_import(s, v)).pack(side="right")
        return status

    def _choose_file(self, section: str, parser, filetypes) -> None:
        if self.readonly:
            messagebox.showinfo("Somente leitura", "Reabra o caixa para edicao antes de importar arquivos.")
            return
        path = filedialog.askopenfilename(filetypes=filetypes)
        if not path:
            return
        if self.imported_paths.get(section) == path:
            messagebox.showwarning("Arquivo repetido", "Este arquivo ja foi importado nesta secao.")
            return
        self.progress.pack(fill="x", pady=(0, 10))
        self.progress.start(10)

        def worker():
            try:
                result = parser(path)
                self.after(0, lambda: self._apply_import(section, path, result))
            except Exception as exc:
                self.after(0, lambda: self._import_failed(str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_import(self, section: str, path: str, result: dict) -> None:
        self.progress.stop()
        self.progress.pack_forget()
        self.imported_paths[section] = path
        if section == "caixa":
            self._merge_categories(result["categorias"], side="sistema", replace=True)
            self.caixa["sangria"] = result["sangria"]
            self.caixa["notas_a_prazo"] = result["notas_a_prazo"]
            self.caixa["despesas"] = result["despesas"]
            summary = f"{len(result['detected'])} itens detectados. Total: {format_money(result['total_saidas'])}"
            self._set_status(self.caixa_status, summary)
            self.result_btn.configure(state="normal")
        elif section == "pagbank":
            self._merge_categories(result["categorias"], side="site", replace=True)
            summary = f"{result['registros_aprovados']} registros aprovados agrupados."
            self._set_status(self.pagbank_status, summary)
        elif section == "premmia":
            self._merge_categories(result["categorias"], side="site", replace=True)
            summary = f"Formato {result['formato'].upper()} detectado. {result['transacoes_processadas']} transacoes processadas."
            self._set_status(self.premmia_status, summary)
        self._apply_fitcard()

    def _import_failed(self, message: str) -> None:
        self.progress.stop()
        self.progress.pack_forget()
        messagebox.showerror("Erro de importacao", message)

    def _merge_categories(self, incoming: dict, side: str, replace: bool) -> None:
        for key in CATEGORIES:
            value = float((incoming.get(key) or {}).get(side, 0) or 0)
            if replace and value:
                self.caixa["categorias"][key][side] = 0.0
            if value:
                self.caixa["categorias"][key][side] = round(self.caixa["categorias"][key][side] + value, 2)

    def _remove_import(self, section: str, status_var: tk.StringVar) -> None:
        if self.readonly:
            messagebox.showinfo("Somente leitura", "Reabra o caixa para edicao antes de remover arquivos.")
            return
        self.imported_paths.pop(section, None)
        if section == "caixa":
            for key in CATEGORIES:
                self.caixa["categorias"][key]["sistema"] = 0.0
            self.caixa["sangria"] = 0.0
            self.caixa["notas_a_prazo"] = 0.0
            self.caixa["despesas"] = 0.0
            self.result_btn.configure(state="disabled")
        elif section == "pagbank":
            for key in ["PAG_PIX", "ELO_CREDITO", "ELO_DEBITO", "MASTERCARD_CREDITO", "MASTERCARD_DEBITO", "VISA_CREDITO", "VISA_DEBITO"]:
                self.caixa["categorias"][key]["site"] = 0.0
        elif section == "premmia":
            for key in ["PREMMIA_CARTAO", "PREMMIA_PIX", "PREMMIA_CUPOM", "PREMMIA_VALE"]:
                self.caixa["categorias"][key]["site"] = 0.0
        self._apply_fitcard()
        self._set_status(status_var, "Nenhum arquivo importado.")

    def _apply_fitcard(self) -> None:
        text = self.fitcard_var.get().strip()
        if not text:
            self.fitcard_ok.set("")
            self.caixa["fitcard_total"] = 0.0
            self.caixa["categorias"]["FITCARD"]["site"] = 0.0
            return
        try:
            value = parse_money(text)
        except ValueError:
            self.fitcard_ok.set("valor invalido")
            return
        self.fitcard_ok.set("✓ valor valido")
        self.caixa["fitcard_total"] = value
        self.caixa["categorias"]["FITCARD"]["site"] = value

    def _collect_common(self, status: str) -> bool:
        try:
            parsed = parse_date_input(self.date_var.get())
            ensure_not_future(parsed)
            self._apply_fitcard()
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

    def _confirm_same_date(self) -> bool:
        existing = self.app.repo.get_by_date(self.caixa["data"])
        if existing and existing.get("id") != self.caixa.get("id"):
            return messagebox.askyesno("Data ja existente", "Ja existe um caixa nesta data. Deseja sobrescrever?")
        return True

    def _reopen(self) -> None:
        if messagebox.askyesno("Reabrir caixa", "Deseja reabrir este caixa conciliado para edicao?"):
            self.caixa["status"] = "rascunho"
            self.readonly = False
            self.load_caixa(self.caixa)

    def _has_system_data(self) -> bool:
        return any(values.get("sistema") for values in self.caixa.get("categorias", {}).values())

    @staticmethod
    def _new_model() -> dict:
        return {
            "data": date.today().isoformat(),
            "status": "rascunho",
            "fitcard_total": 0.0,
            "categorias": empty_categories(),
            "sangria": 0.0,
            "notas_a_prazo": 0.0,
            "despesas": 0.0,
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

    def _toggle_nova_categoria_visibility(self) -> None:
        if self.avulso_cat_var.get() == "Nova categoria...":
            self.nova_cat_row.pack(fill="x", pady=(4, 0))
        else:
            self.nova_cat_row.pack_forget()

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
            key = [k for k, v in CATEGORY_LABELS.items() if v == cat_label][0]
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
                cat_display = CATEGORY_LABELS.get(entry["categoria_vinculada"], entry["categoria_vinculada"])
            else:
                cat_display = entry.get("categoria_nova", "(nova)")
            self.avulsos_tree.insert(
                "",
                "end",
                iid=str(idx),
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

    @staticmethod
    def _set_status(var: tk.StringVar, message: str) -> None:
        var.set(message)

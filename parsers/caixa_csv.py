from __future__ import annotations

import csv
from pathlib import Path

from constants import empty_categories
from utils import normalize_text, parse_money


SYSTEM_CATEGORY_MAP = {
    "BR PREMMIA CARTAO": "PREMMIA_CARTAO",
    "BR PREMMIA GENERICO": "PREMMIA_CUPOM",
    "BR PREMMIA GENERICO / CUPOM": "PREMMIA_CUPOM",
    "BR PREMMIA CUPOM": "PREMMIA_CUPOM",
    "BR PREMMIA PIX": "PREMMIA_PIX",
    "CARTAO FITCARD": "FITCARD",
    "PAG PIX": "PAG_PIX",
    "POS PAGSEGURO MASTER.CRE": "MASTERCARD_CREDITO",
    "SMART PAGSEGURO MASTER.C": "MASTERCARD_CREDITO",
    "POS PAGSEGURO MASTER.DEB": "MASTERCARD_DEBITO",
    "SMART PAGSEGURO MASTER.D": "MASTERCARD_DEBITO",
    "POS PAGSEGURO ELO CRED": "ELO_CREDITO",
    "SMART PAGSEGURO ELO CRED": "ELO_CREDITO",
    "POS PAGSEGURO ELO DEBITO": "ELO_DEBITO",
    "SMART PAGSEGURO ELO DEBI": "ELO_DEBITO",
    "POS PAGSEGURO VISA CREDI": "VISA_CREDITO",
    "SMART PAGSEGURO VISA CRE": "VISA_CREDITO",
    "POS PAGSEGURO VISA DEBIT": "VISA_DEBITO",
    "SMART PAGSEGURO VISA DEB": "VISA_DEBITO",
}

INFO_FIELDS = {
    "SANGRIA": "sangria",
    "NOTAS A PRAZO": "notas_a_prazo",
    "DESPESAS DO POSTO": "despesas",
}


def _read_rows(path: str | Path) -> list[list[str]]:
    with open(path, "r", encoding="latin-1", newline="") as handle:
        return list(csv.reader(handle, delimiter=";"))


def parse_caixa_csv(path: str | Path) -> dict[str, object]:
    rows = _read_rows(path)
    first_lines = [";".join(row) for row in rows[:5]]
    if not any("CAIXA GERAL" in line.upper() for line in first_lines):
        raise ValueError("O arquivo selecionado nao parece ser um CSV do CAIXA GERAL.")

    header_index = None
    for idx, row in enumerate(rows):
        normalized = [normalize_text(cell) for cell in row]
        if len(normalized) >= 2 and normalized[0] == "ENTRADAS" and normalized[1].startswith("SA"):
            header_index = idx
            break
    if header_index is None:
        raise ValueError("Nao encontrei a secao FINANCEIRO com o cabecalho Entradas/Saidas.")

    categorias = empty_categories()
    info = {"sangria": 0.0, "notas_a_prazo": 0.0, "despesas": 0.0}
    detected: list[dict[str, object]] = []

    for row in rows[header_index + 1 :]:
        if not row:
            continue
        if normalize_text(row[0]).startswith("SUBTOTAL"):
            break
        if len(row) < 4:
            continue
        name = normalize_text(row[2])
        value_text = row[3].strip() if len(row) > 3 else ""
        if not name or not value_text:
            continue
        value = parse_money(value_text)
        if name in SYSTEM_CATEGORY_MAP:
            key = SYSTEM_CATEGORY_MAP[name]
            categorias[key]["sistema"] = round(categorias[key]["sistema"] + value, 2)
            detected.append({"nome": name, "categoria": key, "valor": value})
        elif name in INFO_FIELDS:
            info[INFO_FIELDS[name]] = value
            detected.append({"nome": name, "categoria": INFO_FIELDS[name], "valor": value})

    return {
        "categorias": categorias,
        "sangria": info["sangria"],
        "notas_a_prazo": info["notas_a_prazo"],
        "despesas": info["despesas"],
        "detected": detected,
        "total_saidas": round(sum(item["valor"] for item in detected), 2),
    }

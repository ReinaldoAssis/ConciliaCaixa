from __future__ import annotations

import csv
from pathlib import Path

from constants import empty_categories
from utils import normalize_text, parse_money


def _category(bandeira: str, forma: str) -> str | None:
    brand = normalize_text(bandeira)
    method = normalize_text(forma)
    if method == "PIX" or (not brand and method == "PIX"):
        return "PAG_PIX"
    if brand == "VISA" and method.startswith("DEBIT"):
        return "VISA_DEBITO"
    if brand == "VISA" and method.startswith("CREDIT"):
        return "VISA_CREDITO"
    if brand == "MASTERCARD" and method.startswith("DEBIT"):
        return "MASTERCARD_DEBITO"
    if brand == "MASTERCARD" and method.startswith("CREDIT"):
        return "MASTERCARD_CREDITO"
    if brand == "ELO" and method.startswith("DEBIT"):
        return "ELO_DEBITO"
    if brand == "ELO" and method.startswith("CREDIT"):
        return "ELO_CREDITO"
    return None


def parse_pagbank_csv(path: str | Path) -> dict[str, object]:
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        if not reader.fieldnames or "Código da Transação" not in reader.fieldnames:
            raise ValueError("O arquivo selecionado nao parece ser o CSV PagBank esperado.")

        categorias = empty_categories()
        approved = 0
        ignored = 0
        detected: list[dict[str, object]] = []
        for row in reader:
            if normalize_text(row.get("Status")) != "APROVADA":
                ignored += 1
                continue
            key = _category(row.get("Bandeira", ""), row.get("Forma de Pagamento", ""))
            if not key:
                ignored += 1
                continue
            value = parse_money(row.get("Valor Bruto", "0"))
            categorias[key]["site"] = round(categorias[key]["site"] + value, 2)
            approved += 1
            detected.append({"categoria": key, "valor": value})

    return {
        "categorias": categorias,
        "registros_aprovados": approved,
        "registros_ignorados": ignored,
        "detected": detected,
    }

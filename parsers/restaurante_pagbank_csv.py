from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from constants_restaurante import empty_categories_restaurante
from utils import normalize_text, parse_money


RESTAURANTE_CATEGORY_MAP: dict[tuple[str, str], str] = {
    ("PIX", "PIX"): "PIX",
    ("ELO", "DEBITO"): "ELO_DEBITO",
    ("ELO", "CREDITO"): "ELO_CR",
    ("MASTERCARD", "DEBITO"): "MAESTRO",
    ("MASTERCARD", "CREDITO"): "MASTERCARD",
    ("VISA", "DEBITO"): "VC_ELECTRON",
    ("VISA", "CREDITO"): "VISA",
    ("AMEX", "CREDITO"): "AMEX",
    ("AMEX", "AMBOS"): "AMEX",
}


def _category_key(bandeira: str, forma: str) -> tuple[str, str]:
    brand = normalize_text(bandeira)
    method = normalize_text(forma)
    if not brand and method == "PIX":
        return ("PIX", "PIX")
    if brand == "ELO":
        return ("ELO", "DEBITO" if method.startswith("DEBIT") else "CREDITO" if method.startswith("CREDIT") else method)
    if brand == "MASTERCARD":
        return ("MASTERCARD", "DEBITO" if method.startswith("DEBIT") else "CREDITO" if method.startswith("CREDIT") else method)
    if brand == "VISA":
        return ("VISA", "DEBITO" if method.startswith("DEBIT") else "CREDITO" if method.startswith("CREDIT") else method)
    if brand == "AMEX":
        return ("AMEX", "CREDITO" if method.startswith("CREDIT") else method)
    return (brand, method)


def _parse_datetime(dt_str: str) -> datetime | None:
    if not dt_str:
        return None
    try:
        return datetime.strptime(dt_str.strip(), "%d/%m/%Y %H:%M")
    except ValueError:
        try:
            return datetime.strptime(dt_str.strip(), "%d/%m/%Y")
        except ValueError:
            return None


def read_restaurante_transactions(path: str | Path) -> list[dict]:
    transactions: list[dict] = []
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        if not reader.fieldnames or "Código da Transação" not in reader.fieldnames:
            raise ValueError("O arquivo selecionado nao parece ser o CSV PagBank esperado.")

        for row in reader:
            if normalize_text(row.get("Status", "")) != "APROVADA":
                continue
            raw_key = _category_key(row.get("Bandeira", ""), row.get("Forma de Pagamento", ""))
            key = RESTAURANTE_CATEGORY_MAP.get(raw_key)
            if not key:
                continue
            value = parse_money(row.get("Valor Bruto", "0"))
            dt = _parse_datetime(row.get("Data da Transação", ""))
            transactions.append({
                "categoria": key,
                "valor": round(value, 2),
                "dt": dt,
            })

    return transactions


def aggregate_transactions(transactions: list[dict]) -> dict[str, object]:
    categorias = empty_categories_restaurante()
    approved = len(transactions)
    for tx in transactions:
        key = tx["categoria"]
        categorias[key]["real"] = round(categorias[key]["real"] + tx["valor"], 2)
    return {
        "categorias": categorias,
        "registros_aprovados": approved,
        "registros_ignorados": 0,
        "detected": [{"categoria": tx["categoria"], "valor": tx["valor"]} for tx in transactions],
    }


def parse_restaurante_pagbank_csv(path: str | Path) -> dict[str, object]:
    transactions = read_restaurante_transactions(path)
    return aggregate_transactions(transactions)


def split_transactions_by_time(
    path: str | Path, cutoff_time: str
) -> tuple[list[dict], list[dict]]:
    try:
        cutoff = datetime.strptime(cutoff_time.strip(), "%H:%M").time()
    except ValueError:
        raise ValueError(f"Horario de corte invalido: {cutoff_time!r}. Use HH:MM.")

    transactions = read_restaurante_transactions(path)
    first_shift: list[dict] = []
    second_shift: list[dict] = []

    for tx in transactions:
        if tx["dt"] and tx["dt"].time() <= cutoff:
            first_shift.append(tx)
        else:
            second_shift.append(tx)

    return first_shift, second_shift

from __future__ import annotations

import os
import re
import sys
from datetime import date, datetime
from pathlib import Path


DATE_BR_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
DATE_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_money(value: object) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    text = str(value).strip()
    if not text:
        return 0.0
    text = text.replace("R$", "").replace("\xa0", " ").strip()
    text = re.sub(r"[^\d,.\-]", "", text)
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return round(float(text), 2)
    except ValueError as exc:
        raise ValueError(f"Valor monetario invalido: {value!r}") from exc


def format_money(value: object) -> str:
    amount = float(value or 0)
    formatted = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


def normalize_text(text: object) -> str:
    raw = "" if text is None else str(text)
    replacements = {
        "Á": "A",
        "À": "A",
        "Â": "A",
        "Ã": "A",
        "Ä": "A",
        "É": "E",
        "Ê": "E",
        "Í": "I",
        "Ó": "O",
        "Ô": "O",
        "Õ": "O",
        "Ú": "U",
        "Ü": "U",
        "Ç": "C",
    }
    out = raw.strip().upper()
    for src, dst in replacements.items():
        out = out.replace(src, dst)
    return " ".join(out.split())


def parse_date_input(value: str) -> date:
    text = value.strip()
    if DATE_BR_RE.match(text):
        return datetime.strptime(text, "%d/%m/%Y").date()
    if DATE_ISO_RE.match(text):
        return datetime.strptime(text, "%Y-%m-%d").date()
    raise ValueError("Informe a data no formato DD/MM/AAAA ou AAAA-MM-DD.")


def date_to_br(value: str | date) -> str:
    if isinstance(value, date):
        parsed = value
    else:
        parsed = parse_date_input(value)
    return parsed.strftime("%d/%m/%Y")


def date_to_iso(value: str | date) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return parse_date_input(value).isoformat()


def ensure_not_future(value: date) -> None:
    if value > date.today():
        raise ValueError("A data do caixa nao pode ser futura.")


def app_data_dir() -> Path:
    base = os.environ.get("CAIXAPOS_DATA_DIR")
    if base:
        path = Path(base)
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / "CaixaPos"
    elif os.name == "nt":
        path = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "CaixaPos"
    else:
        path = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "caixapos"
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return app_data_dir() / "caixapos_db.json"


def serials_valid(serials: list[str], qty_200: int) -> bool:
    if qty_200 <= 0:
        return True
    if len(serials) != qty_200:
        return False
    return all(re.fullmatch(r"\d{5}", serial or "") for serial in serials)

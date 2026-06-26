from __future__ import annotations

from pathlib import Path

from constants import empty_categories
from utils import normalize_text, parse_money

OLE2_MAGIC = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"


def detectar_formato_premmia(path: str | Path) -> str:
    with open(path, "rb") as handle:
        return "xls" if handle.read(8) == OLE2_MAGIC else "csv"


def _category(forma: object) -> str | None:
    method = normalize_text(forma)
    if method == "PIX":
        return "PREMMIA_PIX"
    if method in {"CARTAO APP", "CARTAO"}:
        return "PREMMIA_CARTAO"
    if method in {"DESCONTO", "CUPOM"}:
        return "PREMMIA_CUPOM"
    return None


def _rows_from_xls(path: str | Path) -> list[dict[str, object]]:
    try:
        import xlrd
    except ImportError as exc:
        raise RuntimeError("A dependencia xlrd nao esta instalada. Execute: pip install -r requirements.txt") from exc

    book = xlrd.open_workbook(path)
    if "Conferência" in book.sheet_names():
        sheet = book.sheet_by_name("Conferência")
    elif "Conferencia" in book.sheet_names():
        sheet = book.sheet_by_name("Conferencia")
    else:
        raise ValueError("Nao encontrei a planilha 'Conferencia' no arquivo Premmia.")

    header_row = None
    headers: list[str] = []
    for row_idx in range(sheet.nrows):
        values = [str(sheet.cell_value(row_idx, col)).strip() for col in range(sheet.ncols)]
        normalized = [normalize_text(v) for v in values]
        if "CPF" in normalized and "STATUS" in normalized:
            header_row = row_idx
            headers = values
            break
    if header_row is None:
        raise ValueError("Nao encontrei o cabecalho esperado no arquivo Premmia.")

    records = []
    for row_idx in range(header_row + 1, sheet.nrows):
        record = {}
        for col_idx, header in enumerate(headers):
            record[header] = sheet.cell_value(row_idx, col_idx)
        records.append(record)
    return records


def _get(record: dict[str, object], wanted: str) -> object:
    wanted_norm = normalize_text(wanted)
    for key, value in record.items():
        if normalize_text(key) == wanted_norm:
            return value
    return ""


def parse_premmia_file(path: str | Path) -> dict[str, object]:
    formato = detectar_formato_premmia(path)
    if formato != "xls":
        raise ValueError("O relatorio Premmia deve ser um arquivo Excel .xls valido.")
    records = _rows_from_xls(path)
    categorias = empty_categories()
    processed = 0
    ignored = 0
    detected: list[dict[str, object]] = []

    for record in records:
        if normalize_text(_get(record, "Status")) != "PROCESSADA":
            ignored += 1
            continue
        key = _category(_get(record, "Forma de Pagamento"))
        if not key:
            ignored += 1
            continue
        value = parse_money(_get(record, "Valor líquido"))
        categorias[key]["site"] = round(categorias[key]["site"] + value, 2)
        processed += 1
        detected.append({"categoria": key, "valor": value})

    return {
        "formato": formato,
        "categorias": categorias,
        "transacoes_processadas": processed,
        "transacoes_ignoradas": ignored,
        "detected": detected,
    }

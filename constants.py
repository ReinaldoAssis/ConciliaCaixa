from __future__ import annotations

CATEGORIES = [
    "PREMMIA_CARTAO",
    "PREMMIA_PIX",
    "PREMMIA_CUPOM",
    "FITCARD",
    "PAG_PIX",
    "ELO_CREDITO",
    "ELO_DEBITO",
    "MASTERCARD_CREDITO",
    "MASTERCARD_DEBITO",
    "VISA_CREDITO",
    "VISA_DEBITO",
]

CATEGORY_LABELS = {
    "PREMMIA_CARTAO": "PREMMIA CARTAO",
    "PREMMIA_PIX": "PREMMIA PIX",
    "PREMMIA_CUPOM": "PREMMIA CUPOM",
    "FITCARD": "FITCARD",
    "PAG_PIX": "PAG PIX",
    "ELO_CREDITO": "ELO CREDITO",
    "ELO_DEBITO": "ELO DEBITO",
    "MASTERCARD_CREDITO": "MASTERCARD CREDITO",
    "MASTERCARD_DEBITO": "MASTERCARD DEBITO",
    "VISA_CREDITO": "VISA CREDITO",
    "VISA_DEBITO": "VISA DEBITO",
}

DENOMINATIONS = [200, 100, 50, 20, 10, 5, 2]


def empty_categories() -> dict[str, dict[str, float]]:
    return {key: {"sistema": 0.0, "site": 0.0} for key in CATEGORIES}


def normalize_categories(categorias: dict[str, dict[str, float]] | None) -> dict[str, dict[str, float]]:
    normalized = empty_categories()
    for key, values in (categorias or {}).items():
        if key == "CARTAO_FITCARD":
            target = "FITCARD"
        elif key in normalized:
            target = key
        else:
            continue
        normalized[target]["sistema"] = round(
            normalized[target]["sistema"] + float((values or {}).get("sistema", 0) or 0), 2
        )
        normalized[target]["site"] = round(
            normalized[target]["site"] + float((values or {}).get("site", 0) or 0), 2
        )
    return normalized


def build_conciliation_rows(categorias: dict[str, dict[str, float]]) -> list[dict[str, object]]:
    categorias = normalize_categories(categorias)
    rows = []
    for key in CATEGORIES:
        values = categorias.get(key, {})
        sistema = round(float(values.get("sistema", 0) or 0), 2)
        site = round(float(values.get("site", 0) or 0), 2)
        diff = round(sistema - site, 2)
        rows.append(
            {
                "key": key,
                "label": CATEGORY_LABELS[key],
                "sistema": sistema,
                "site": site,
                "diferenca": diff,
                "status": "OK" if abs(diff) < 0.005 else "DIVERGENTE",
            }
        )
    return rows


def totals(categorias: dict[str, dict[str, float]]) -> tuple[float, float, float]:
    rows = build_conciliation_rows(categorias)
    sistema = round(sum(float(row["sistema"]) for row in rows), 2)
    site = round(sum(float(row["site"]) for row in rows), 2)
    return sistema, site, round(sistema - site, 2)

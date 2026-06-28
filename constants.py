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


def _apply_avulsos(base_sistema: float, avulsos: list[dict], key: str) -> float:
    result = base_sistema
    for avulso in (avulsos or []):
        if avulso.get("categoria_vinculada") == key:
            valor = float(avulso.get("valor", 0) or 0)
            result = round(result + valor if avulso.get("tipo") == "RECEITA" else result - valor, 2)
    return result


def build_conciliation_rows(
    categorias: dict[str, dict[str, float]],
    avulsos: list[dict] | None = None,
) -> list[dict[str, object]]:
    categorias = normalize_categories(categorias)
    rows = []
    for key in CATEGORIES:
        values = categorias.get(key, {})
        sistema = round(float(values.get("sistema", 0) or 0), 2)
        site = round(float(values.get("site", 0) or 0), 2)
        sistema = _apply_avulsos(sistema, avulsos or [], key)
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
    for avulso in (avulsos or []):
        if avulso.get("categoria_nova"):
            valor = float(avulso.get("valor", 0) or 0)
            label = avulso["categoria_nova"]
            sistema_new = round(valor if avulso.get("tipo") == "RECEITA" else -valor, 2)
            rows.append(
                {
                    "key": label,
                    "label": label,
                    "sistema": sistema_new,
                    "site": 0.0,
                    "diferenca": sistema_new,
                    "status": "OK" if abs(sistema_new) < 0.005 else "DIVERGENTE",
                }
            )
    return rows


def totals(
    categorias: dict[str, dict[str, float]],
    avulsos: list[dict] | None = None,
) -> tuple[float, float, float]:
    rows = build_conciliation_rows(categorias, avulsos)
    sistema = round(sum(float(row["sistema"]) for row in rows), 2)
    site = round(sum(float(row["site"]) for row in rows), 2)
    return sistema, site, round(sistema - site, 2)

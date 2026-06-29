from __future__ import annotations

CATEGORIAS_RESTAURANTE = [
    "PIX",
    "ELO_DEBITO",
    "MAESTRO",
    "VC_ELECTRON",
    "AMEX",
    "ELO_CR",
    "MASTERCARD",
    "VISA",
    "DINHEIRO",
]

CATEGORIAS_RESTAURANTE_LABELS = {
    "PIX": "PIX",
    "ELO_DEBITO": "ELO DEBITO",
    "MAESTRO": "MAESTRO",
    "VC_ELECTRON": "VC ELECTRON",
    "AMEX": "AMEX",
    "ELO_CR": "ELO CR",
    "MASTERCARD": "MASTERCARD",
    "VISA": "VISA",
    "DINHEIRO": "DINHEIRO",
}

CATEGORIA_CLASSIFICACAO = {
    "PIX": "DEBITO",
    "ELO_DEBITO": "DEBITO",
    "MAESTRO": "DEBITO",
    "VC_ELECTRON": "DEBITO",
    "AMEX": "CREDITO",
    "ELO_CR": "CREDITO",
    "MASTERCARD": "CREDITO",
    "VISA": "CREDITO",
    "DINHEIRO": "DINHEIRO",
}


def empty_categories_restaurante() -> dict[str, dict[str, float]]:
    return {key: {"sistema": 0.0, "real": 0.0} for key in CATEGORIAS_RESTAURANTE}


def normalize_categories_restaurante(
    categorias: dict[str, dict[str, float]] | None,
) -> dict[str, dict[str, float]]:
    normalized = empty_categories_restaurante()
    for key, values in (categorias or {}).items():
        if key not in normalized:
            continue
        normalized[key]["sistema"] = round(
            normalized[key]["sistema"] + float((values or {}).get("sistema", 0) or 0), 2
        )
        normalized[key]["real"] = round(
            normalized[key]["real"] + float((values or {}).get("real", 0) or 0), 2
        )
    return normalized


def _apply_avulsos_restaurante(base_sistema: float, avulsos: list[dict], key: str) -> float:
    result = base_sistema
    for avulso in (avulsos or []):
        if avulso.get("categoria_vinculada") == key:
            valor = float(avulso.get("valor", 0) or 0)
            result = round(
                result + valor if avulso.get("tipo") == "RECEITA" else result - valor, 2
            )
    return result


def build_conciliation_rows_restaurante(
    categorias: dict[str, dict[str, float]],
    avulsos: list[dict] | None = None,
    dinheiro_real: float = 0.0,
) -> list[dict[str, object]]:
    categorias = normalize_categories_restaurante(categorias)
    rows = []
    for key in CATEGORIAS_RESTAURANTE:
        values = categorias.get(key, {})
        sistema = round(float(values.get("sistema", 0) or 0), 2)
        real = round(float(values.get("real", 0) or 0), 2)
        if key == "DINHEIRO":
            real = round(dinheiro_real, 2)
        sistema = _apply_avulsos_restaurante(sistema, avulsos or [], key)
        diff = round(sistema - real, 2)
        rows.append({
            "key": key,
            "label": CATEGORIAS_RESTAURANTE_LABELS[key],
            "classificacao": CATEGORIA_CLASSIFICACAO[key],
            "sistema": sistema,
            "real": real,
            "diferenca": diff,
            "status": "OK" if abs(diff) < 0.005 else "DIVERGENTE",
        })
    for avulso in (avulsos or []):
        if avulso.get("categoria_nova"):
            valor = float(avulso.get("valor", 0) or 0)
            label = avulso["categoria_nova"]
            sistema_new = round(valor if avulso.get("tipo") == "RECEITA" else -valor, 2)
            rows.append({
                "key": label,
                "label": label,
                "classificacao": "",
                "sistema": sistema_new,
                "real": 0.0,
                "diferenca": sistema_new,
                "status": "OK" if abs(sistema_new) < 0.005 else "DIVERGENTE",
            })
    return rows


def totals_restaurante(
    categorias: dict[str, dict[str, float]],
    avulsos: list[dict] | None = None,
    dinheiro_real: float = 0.0,
) -> tuple[float, float, float]:
    rows = build_conciliation_rows_restaurante(categorias, avulsos, dinheiro_real)
    sistema = round(sum(float(row["sistema"]) for row in rows), 2)
    real = round(sum(float(row["real"]) for row in rows), 2)
    return sistema, real, round(sistema - real, 2)

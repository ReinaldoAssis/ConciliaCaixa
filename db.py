from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from constants import empty_categories, normalize_categories, totals
from utils import db_path


class CaixaRepository:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else db_path()
        try:
            from tinydb import Query, TinyDB
        except ImportError as exc:
            raise RuntimeError("Instale tinydb para usar a persistencia local.") from exc
        self._query = Query()
        self._db = TinyDB(self.path, ensure_ascii=False, indent=2)
        self._caixas = self._db.table("caixas")

    def all(self) -> list[dict]:
        records = list(self._caixas.all())
        records.sort(key=lambda item: item.get("data", ""), reverse=True)
        return records

    def search(self, data: str | None = None, status: str | None = None) -> list[dict]:
        records = self.all()
        if data:
            records = [item for item in records if item.get("data") == data]
        if status and status != "todos":
            records = [item for item in records if item.get("status") == status]
        return records

    def get(self, caixa_id: str) -> dict | None:
        found = self._caixas.search(self._query.id == caixa_id)
        return found[0] if found else None

    def get_by_date(self, iso_date: str) -> dict | None:
        found = self._caixas.search(self._query.data == iso_date)
        return found[0] if found else None

    def save(self, caixa: dict) -> dict:
        now = datetime.now().isoformat(timespec="seconds")
        caixa = self._normalize(caixa)
        caixa.setdefault("id", str(uuid4()))
        caixa.setdefault("criado_em", now)
        caixa["atualizado_em"] = now
        existing = self.get(caixa["id"])
        if existing:
            self._caixas.update(caixa, self._query.id == caixa["id"])
        else:
            same_date = self.get_by_date(caixa["data"])
            if same_date and same_date.get("id") != caixa["id"]:
                self._caixas.remove(self._query.id == same_date["id"])
            self._caixas.insert(caixa)
        return caixa

    def delete(self, caixa_id: str) -> None:
        self._caixas.remove(self._query.id == caixa_id)

    def close(self) -> None:
        self._db.close()

    @staticmethod
    def _normalize(caixa: dict) -> dict:
        normalized = dict(caixa)
        normalized.setdefault("status", "rascunho")
        normalized.setdefault("categorias", empty_categories())
        normalized["categorias"] = normalize_categories(normalized["categorias"])
        normalized.setdefault("fitcard_total", 0.0)
        normalized.setdefault("sangria", 0.0)
        normalized.setdefault("notas_a_prazo", 0.0)
        normalized.setdefault("despesas", 0.0)
        normalized.setdefault("contagens_dinheiro", [])
        normalized.setdefault("observacoes", "")
        total_sistema, total_site, diferenca = totals(normalized["categorias"])
        normalized["total_sistema"] = total_sistema
        normalized["total_site"] = total_site
        normalized["diferenca_total"] = diferenca
        return normalized

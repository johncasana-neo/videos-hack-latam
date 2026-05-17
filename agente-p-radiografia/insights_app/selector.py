"""Case selection logic."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class CaseSelector:
    """Pick the strongest case while avoiding repeated entities."""

    def __init__(self, insights_dir: str | Path = "insights") -> None:
        self.insights_dir = Path(insights_dir)

    def pick(self, casos: list[dict[str, Any]]) -> dict[str, Any] | None:
        recent_entities = self._recent_entities()
        ranked = sorted(casos, key=self._score, reverse=True)
        for caso in ranked:
            if self._score(caso) < 7:
                return None
            entidad = str(caso.get("licitacion", {}).get("entidad") or caso.get("source", {}).get("entidad_nombre") or "")
            if entidad and entidad in recent_entities:
                continue
            return caso
        return None

    def _recent_entities(self) -> set[str]:
        entities: set[str] = set()
        files = sorted(self.insights_dir.glob("insight_2*.json"), reverse=True)[:7]
        for path in files:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            entity = data.get("source", {}).get("entidad_nombre")
            if entity:
                entities.add(str(entity))
        return entities

    @staticmethod
    def _score(caso: dict[str, Any]) -> float:
        flags = caso.get("red_flags", [])
        if not flags:
            return 0
        max_severity = max(float(flag.get("severity", 0)) for flag in flags)
        amount = float(caso.get("licitacion", {}).get("monto_adjudicado") or 0)
        amount_bonus = min(amount / 10_000_000, 1.5)
        confidence = float(caso.get("confidence", 0.85))
        return max_severity + amount_bonus + confidence - 1

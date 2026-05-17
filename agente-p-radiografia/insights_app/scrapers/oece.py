"""OCDS/OECE collector for Peruvian contracting data."""

from __future__ import annotations

from datetime import date
from typing import Any

import requests

from .base import BaseCollector


class OeceCollector(BaseCollector):
    """Fetch and normalize public OCDS releases."""

    publication_url = "https://data.open-contracting.org/es/publication/135"

    def fetch(self) -> list[dict[str, Any]]:
        try:
            response = requests.get(self.publication_url, timeout=self.timeout, headers={"User-Agent": "agente-p-radiografia/1.0"})
            response.raise_for_status()
        except requests.RequestException:
            return []

        if "application/json" not in response.headers.get("content-type", ""):
            return []

        payload = response.json()
        releases = payload.get("releases", []) if isinstance(payload, dict) else []
        return [self._normalize_release(release) for release in releases[:500] if isinstance(release, dict)]

    def _normalize_release(self, release: dict[str, Any]) -> dict[str, Any]:
        tender = release.get("tender", {}) or {}
        awards = release.get("awards", []) or []
        buyer = release.get("buyer", {}) or {}
        award = awards[0] if awards else {}
        suppliers = award.get("suppliers", []) or []
        value = award.get("value", {}) or tender.get("value", {}) or {}
        return {
            "codigo_seace": str(release.get("ocid", "")),
            "entidad": buyer.get("name", ""),
            "ruc_entidad": buyer.get("id", ""),
            "objeto": tender.get("title", "") or tender.get("description", ""),
            "monto_referencial": float((tender.get("value") or {}).get("amount") or 0),
            "monto_adjudicado": float(value.get("amount") or 0),
            "fecha_convocatoria": str(tender.get("tenderPeriod", {}).get("startDate", ""))[:10] or str(date.today()),
            "fecha_adjudicacion": str(award.get("date", ""))[:10] or str(date.today()),
            "numero_postores": int(tender.get("numberOfTenderers") or max(len(suppliers), 1)),
            "postores": [str(s.get("id", "")) for s in suppliers if s.get("id")],
            "fuente_oficial": "OCDS/OECE",
        }

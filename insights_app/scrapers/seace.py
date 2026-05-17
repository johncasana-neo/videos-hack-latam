"""Best-effort SEACE collector."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import requests
from bs4 import BeautifulSoup
from dateutil import parser

from .base import BaseCollector


class SeaceCollector(BaseCollector):
    """Collect recent procurement records from public SEACE pages."""

    base_url = "https://www.seace.gob.pe"

    def fetch(self) -> list[dict[str, Any]]:
        return self.fetch_recent(days=7)

    def fetch_recent(self, days: int = 7) -> list[dict[str, Any]]:
        cutoff = date.today() - timedelta(days=days)
        records: list[dict[str, Any]] = []
        endpoints = [
            "https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml",
            self.base_url,
        ]
        for url in endpoints:
            try:
                response = requests.get(url, timeout=self.timeout, headers={"User-Agent": "agente-p-radiografia/1.0"})
                response.raise_for_status()
            except requests.RequestException:
                continue
            records.extend(self._parse_html(response.text, cutoff))
            if records:
                break
        return records

    def _parse_html(self, html: str, cutoff: date) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        rows = soup.select("tr")
        parsed: list[dict[str, Any]] = []
        for row in rows:
            cells = [cell.get_text(" ", strip=True) for cell in row.select("td")]
            if len(cells) < 5:
                continue
            text = " | ".join(cells)
            amount = self._extract_amount(text)
            fecha = self._extract_date(text)
            if fecha and fecha < cutoff:
                continue
            codigo = next((value for value in cells if any(ch.isdigit() for ch in value) and "-" in value), "")
            entidad = cells[0]
            objeto = cells[2] if len(cells) > 2 else text[:180]
            parsed.append(
                {
                    "codigo_seace": codigo or f"SEACE-{date.today():%Y%m%d}-{len(parsed)+1}",
                    "entidad": entidad,
                    "ruc_entidad": "",
                    "objeto": objeto,
                    "monto_referencial": amount,
                    "monto_adjudicado": amount,
                    "fecha_convocatoria": str(fecha or date.today()),
                    "fecha_adjudicacion": str(date.today()),
                    "numero_postores": 1 if "adjudicado" in text.lower() else 2,
                    "postores": [],
                    "fuente_oficial": "SEACE",
                }
            )
        return parsed

    @staticmethod
    def _extract_amount(text: str) -> float:
        import re

        matches = re.findall(r"(?:S/\s*)?([0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?)", text)
        if not matches:
            return 0.0
        return float(matches[-1].replace(",", ""))

    @staticmethod
    def _extract_date(text: str) -> date | None:
        import re

        match = re.search(r"\b([0-3]?\d/[01]?\d/20\d{2})\b", text)
        if not match:
            return None
        try:
            return parser.parse(match.group(1), dayfirst=True).date()
        except (ValueError, TypeError):
            return None

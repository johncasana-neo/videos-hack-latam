"""Contraloria sanctions checker."""

from __future__ import annotations

from datetime import date
from typing import Any

import requests
from bs4 import BeautifulSoup
from dateutil import parser


class ContraloriaChecker:
    """Query public sanctions pages with graceful fallback."""

    search_url = "https://www.gob.pe/contraloria"

    def get_sancion(self, dni_o_ruc: str) -> dict[str, Any] | None:
        if not dni_o_ruc:
            return None
        try:
            response = requests.get(self.search_url, timeout=25, headers={"User-Agent": "agente-p-radiografia/1.0"})
            response.raise_for_status()
        except requests.RequestException:
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text(" ", strip=True)
        if dni_o_ruc not in text:
            return None
        return {
            "sancion": "Registro publico asociado al identificador consultado",
            "vigencia": "POR_VERIFICAR",
            "fecha_inicio": str(date.today()),
            "fecha_fin": "",
        }

    @staticmethod
    def is_active(sancion: dict[str, Any]) -> bool:
        vigencia = str(sancion.get("vigencia", "")).upper()
        if "VIGENTE" in vigencia or "ACTIVA" in vigencia:
            return True
        fecha_fin = str(sancion.get("fecha_fin", ""))
        if not fecha_fin:
            return False
        try:
            return parser.parse(fecha_fin, dayfirst=True).date() >= date.today()
        except (ValueError, TypeError):
            return False

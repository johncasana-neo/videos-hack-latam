"""LLM synthetic fallback — generates plausible procurement red flag cases."""

from __future__ import annotations

import json
import os
from datetime import date, timedelta
from typing import Any

from .base import BaseCollector

_PATTERNS = ["fraccionamiento_contractual", "proveedor_recurrente", "postor_unico_con_proceso_acelerado"]

_PROMPT_TEMPLATE = (
    "Eres un experto en contrataciones publicas peruanas. "
    "Genera 2 casos PLAUSIBLES de alertas de contratacion publica para el sistema Agente P Radiografia.\n\n"
    "Cada caso es un objeto JSON con estos campos:\n"
    'codigo_seace (string), entidad (entidad publica peruana real), ruc_entidad (11 digitos),\n'
    'objeto (descripcion concreta del contrato), monto_adjudicado (numero en soles entre 200000 y 5000000),\n'
    'fecha_convocatoria (YYYY-MM-DD), fecha_adjudicacion (YYYY-MM-DD), numero_postores (numero),\n'
    'postores (array de RUCs), fuente_oficial ("SEACE"), funcionarios ([]), signatarios ([]),\n'
    'patron_sugerido (uno de: fraccionamiento_contractual | proveedor_recurrente | postor_unico_con_proceso_acelerado)\n\n'
    "Reglas de deteccion:\n"
    "- fraccionamiento_contractual: mismo RUC en postores, misma ruc_entidad, 2 registros dentro de 30 dias, suma > 400000\n"
    "- proveedor_recurrente: mismo RUC en postores, misma entidad, mas de 5 registros en 12 meses\n"
    "- postor_unico_con_proceso_acelerado: numero_postores=1, dias entre convocatoria y adjudicacion < 20\n\n"
    "Entidades reales: MTC, MINSA, MINEDU, GORE Lima, ESSALUD, PROVIAS, SUNAFIL, MINAM, etc.\n"
    "Empresas proveedoras: ficticias pero plausibles con RUC de 11 digitos.\n"
    "Fecha de hoy: {today}\n\n"
    "Devuelve SOLO un array JSON. Sin explicaciones ni markdown."
)


class SyntheticCollector(BaseCollector):
    """Generate plausible procurement cases via LLM when real sources fail."""

    def fetch(self) -> list[dict[str, Any]]:
        api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("ANTHROPIC_API_KEY", "")
        base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY o ANTHROPIC_API_KEY requerido para fallback sintetico")

        try:
            import requests
        except ImportError as exc:
            raise RuntimeError("pip install requests") from exc

        prompt = _PROMPT_TEMPLATE.format(today=date.today().isoformat())
        use_openrouter = "openrouter" in base_url

        if use_openrouter:
            # Normalize: openrouter needs /v1/chat/completions
            base = base_url.rstrip("/")
            if not base.endswith("/v1"):
                base = base + "/v1"
            endpoint = f"{base}/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": os.environ.get("ANTHROPIC_MODEL", "anthropic/claude-haiku-4-5"),
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1200,
                "temperature": 0.8,
            }
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=60)
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"].strip()
        else:
            endpoint = f"{base_url.rstrip('/')}/v1/messages"
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 1200,
                "messages": [{"role": "user", "content": prompt}],
            }
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=60)
            resp.raise_for_status()
            raw = resp.json()["content"][0]["text"].strip()

        cases = self._parse_response(raw)
        return self._expand_for_detector(cases)

    def _parse_response(self, raw: str) -> list[dict[str, Any]]:
        # Strip markdown fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        try:
            data = json.loads(cleaned)
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, ValueError):
            pass
        return []

    def _expand_for_detector(self, cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Expand cases so the detector can fire the right pattern."""
        expanded: list[dict[str, Any]] = []
        for case in cases:
            pattern = case.pop("patron_sugerido", "fraccionamiento_contractual")
            # Ensure required fields
            case.setdefault("funcionarios", [])
            case.setdefault("signatarios", [])
            case.setdefault("fuente_oficial", "SEACE-Sintetico")
            case["_synthetic"] = True

            if pattern == "fraccionamiento_contractual":
                # Need 2 records with same postor/entity within 30 days
                try:
                    adj = date.fromisoformat(str(case.get("fecha_adjudicacion", date.today())))
                except ValueError:
                    adj = date.today()
                sibling = {**case, "codigo_seace": case["codigo_seace"] + "-B"}
                earlier = adj - timedelta(days=20)
                sibling["fecha_convocatoria"] = str(earlier - timedelta(days=5))
                sibling["fecha_adjudicacion"] = str(earlier)
                expanded.append(case)
                expanded.append(sibling)

            elif pattern == "proveedor_recurrente":
                # Need >5 records with same postor/entity in 12 months
                try:
                    base_date = date.fromisoformat(str(case.get("fecha_adjudicacion", date.today())))
                except ValueError:
                    base_date = date.today()
                for i in range(6):
                    clone = {**case, "codigo_seace": f"{case['codigo_seace']}-{i+1:02d}"}
                    clone["fecha_adjudicacion"] = str(base_date - timedelta(days=i * 45))
                    clone["fecha_convocatoria"] = str(base_date - timedelta(days=i * 45 + 10))
                    expanded.append(clone)

            elif pattern == "postor_unico_con_proceso_acelerado":
                # Need numero_postores=1 and dias_proceso < 20
                case["numero_postores"] = 1
                try:
                    adj = date.fromisoformat(str(case.get("fecha_adjudicacion", date.today())))
                except ValueError:
                    adj = date.today()
                case["fecha_convocatoria"] = str(adj - timedelta(days=12))
                expanded.append(case)

            else:
                expanded.append(case)

        return expanded

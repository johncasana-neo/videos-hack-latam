"""Insight JSON builder."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


class ScriptGenerator:
    """Build the complete JSON contract consumed by the video skill."""

    def __init__(self, insights_dir: str | Path = "insights") -> None:
        self.insights_dir = Path(insights_dir)

    def build(self, caso: dict[str, Any]) -> dict[str, Any]:
        lic = caso["licitacion"]
        flag = max(caso["red_flags"], key=lambda item: int(item.get("severity", 0)))
        now = datetime.now(ZoneInfo("America/Lima"))
        episode = self._next_episode()
        monto = float(lic.get("monto_adjudicado") or lic.get("monto_referencial") or 0)
        dias = int(flag.get("evidencia", {}).get("dias_proceso") or caso.get("dias_proceso") or self._days(lic))
        promedio = int(flag.get("evidencia", {}).get("promedio_sector") or 40)
        entidad = str(lic.get("entidad") or "Entidad publica")
        sigla = self._sigla(entidad)
        title = self._title(flag["patron_id"], entidad, monto)
        voiceover = self._voiceover(flag["patron_id"], entidad, monto, dias, promedio, lic)
        return {
            "video_id": f"radiografia-{now:%Y%m%d-%H%M%S}",
            "generated_at": now.isoformat(),
            "series": {
                "name": "Radiografia del Gasto Publico",
                "project": "Agente P : Operaciones Glitch",
                "episode_number": episode,
                "episode_label": f"{episode:02d}/30",
            },
            "case": {
                "caso_titulo": title,
                "patron_detectado": flag["patron_id"],
                "confidence": float(caso.get("confidence", 0.86)),
                "severity": int(flag.get("severity", 0)),
                "red_flags": caso["red_flags"],
            },
            "source": {
                "entidad_nombre": entidad,
                "entidad_sigla": sigla,
                "entidad_ruc": str(lic.get("ruc_entidad", "")),
                "codigo_seace": str(lic.get("codigo_seace", "")),
                "fuente_oficial": str(lic.get("fuente_oficial", "SEACE")),
                "raw_data_points": lic,
            },
            "contract": {
                "objeto_contrato": str(lic.get("objeto", "")),
                "monto_adjudicado": monto,
                "numero_postores": int(lic.get("numero_postores") or 0),
                "dias_proceso": dias,
                "promedio_sector": promedio,
            },
            "script": {
                "voiceover_text_full": voiceover,
                "segments": self._segments(title, entidad, monto, dias, promedio),
            },
            "global_style": {
                "background": "#0A1628",
                "grid": "#1E3A5F",
                "positive": "#4ADE80",
                "alert": "#EF4444",
                "warning": "#FBBF24",
                "main_text": "#FFFFFF",
                "cta": "#F472B6",
            },
            "audio": {
                "provider": "MiniMax",
                "model": "speech-2.6-hd",
                "voice_id": "Spanish_SeriousMan",
                "language_boost": "Spanish",
                "speed": 1.05,
                "pitch": -1,
                "emotion": "neutral",
            },
            "subtitles": {"engine": "whisper", "granularity": "word-level", "karaoke": True},
            "output": {"width": 1080, "height": 1920, "fps": 30, "duration_seconds": 20},
            "metadata": {
                "title": title,
                "description": f"Analisis de datos publicos de contrataciones: {entidad}. Fuente: {lic.get('fuente_oficial', 'SEACE')}.",
                "hashtags": ["#AgenteP", "#GastoPublico", "#ContratacionesPublicas", "#Peru", "#DatosPublicos"],
            },
        }

    def _next_episode(self) -> int:
        max_episode = 0
        for path in self.insights_dir.glob("insight_*.json"):
            if path.name == "insight_example_mtc.json":
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            max_episode = max(max_episode, int(data.get("series", {}).get("episode_number") or 0))
        return min(max_episode + 1, 30)

    @staticmethod
    def _title(pattern: str, entidad: str, monto: float) -> str:
        amount = f"S/ {monto:,.0f}"
        if pattern == "postor_unico_con_proceso_acelerado":
            return f"Un solo postor por {amount}"
        if pattern == "proveedor_recurrente":
            return f"El proveedor que vuelve una y otra vez"
        if pattern == "fraccionamiento_contractual":
            return f"Contratos partidos que suman {amount}"
        if pattern == "funcionario_sancionado_activo":
            return f"Firma bajo sancion en {entidad}"
        return f"Alerta en contratacion publica: {amount}"

    @staticmethod
    def _voiceover(pattern: str, entidad: str, monto: float, dias: int, promedio: int, lic: dict[str, Any]) -> str:
        amount = f"S/ {monto:,.0f}"
        objeto = str(lic.get("objeto", "un contrato publico"))
        if pattern == "postor_unico_con_proceso_acelerado":
            return f"Radiografia del gasto publico. Hoy, {entidad}: {amount} adjudicados para {objeto}. El dato que prende la alerta: solo hubo un postor, y el proceso duro {dias} dias, frente a un promedio sectorial de {promedio}. No es sentencia, es una red flag con datos publicos. Fuente: {lic.get('fuente_oficial', 'SEACE')}."
        return f"Radiografia del gasto publico. Hoy revisamos {entidad}, con un caso por {amount}: {objeto}. El patron detectado exige mirar contratos, fechas y repeticion de actores. No es sentencia, es una red flag basada en datos publicos. Fuente: {lic.get('fuente_oficial', 'SEACE')}."

    @staticmethod
    def _segments(title: str, entidad: str, monto: float, dias: int, promedio: int) -> list[dict[str, Any]]:
        return [
            {"start": 0, "end": 2, "label": "intro", "text": title},
            {"start": 2, "end": 3, "label": "dato_monto", "text": f"S/ {monto:,.0f}"},
            {"start": 3, "end": 4, "label": "dato_postores", "text": "Postores y competencia"},
            {"start": 4, "end": 5, "label": "dato_tiempo", "text": f"{dias} dias"},
            {"start": 5, "end": 10, "label": "contexto", "text": entidad},
            {"start": 10, "end": 14, "label": "comparativa", "text": f"{dias} vs {promedio} dias"},
            {"start": 14, "end": 17, "label": "punch", "text": "La alerta esta en el patron"},
            {"start": 17, "end": 20, "label": "cta", "text": "Sigueme"},
        ]

    @staticmethod
    def _sigla(entidad: str) -> str:
        words = [word for word in entidad.replace("-", " ").split() if word[:1].isupper()]
        sigla = "".join(word[0] for word in words[:5])
        return sigla or entidad[:8].upper()

    @staticmethod
    def _days(lic: dict[str, Any]) -> int:
        from dateutil import parser

        try:
            start = parser.parse(str(lic.get("fecha_convocatoria")), dayfirst=True)
            end = parser.parse(str(lic.get("fecha_adjudicacion")), dayfirst=True)
            return max((end - start).days, 1)
        except (ValueError, TypeError):
            return 1

"""Insight JSON builder."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

try:
    import requests as _requests
except ImportError:
    _requests = None


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
        voiceover = self._voiceover(flag["patron_id"], sigla, monto, dias, promedio, lic)
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
                "provider": "ElevenLabs",
                "model": "eleven_multilingual_v2",
                "voice_id": "pNInz6obpgDQGcFmaJgB",
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.4,
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
    def _voiceover(pattern: str, sigla: str, monto: float, dias: int, promedio: int, lic: dict[str, Any]) -> str:
        amount = f"S/ {monto:,.0f}"
        objeto_raw = str(lic.get("objeto", "un contrato publico"))
        objeto = objeto_raw[:60] + "..." if len(objeto_raw) > 60 else objeto_raw
        fuente = lic.get("fuente_oficial", "SEACE")
        entidad = str(lic.get("entidad", sigla))

        ai_text = ScriptGenerator._voiceover_ai(
            pattern=pattern,
            sigla=sigla,
            entidad=entidad,
            objeto=objeto,
            monto=monto,
            dias=dias,
            promedio=promedio,
            fuente=fuente,
            lic=lic,
        )
        if ai_text:
            return ai_text

        # Fallback: template por patron (max 50 palabras)
        cta = "No es sentencia, son datos publicos. Siguenos: Agente Perry."
        if pattern == "postor_unico_con_proceso_acelerado":
            body = (
                f"Radiografia del gasto publico. {sigla}: {amount}. "
                f"Un solo postor. {dias} dias frente a {promedio} en promedio. "
                f"Fuente: {fuente}."
            )
        elif pattern == "proveedor_recurrente":
            body = (
                f"Radiografia del gasto publico. {sigla}: {amount}. "
                f"El mismo proveedor ganando una y otra vez. "
                f"Fuente: {fuente}."
            )
        elif pattern == "fraccionamiento_contractual":
            body = (
                f"Radiografia del gasto publico. {sigla}: contratos partidos, suman {amount}. "
                f"Mismo proveedor, mismo objeto. "
                f"Fuente: {fuente}."
            )
        elif pattern == "funcionario_sancionado_activo":
            body = (
                f"Radiografia del gasto publico. {sigla}: {amount} "
                f"firmado por funcionario inhabilitado. Sancion vigente. "
                f"Fuente: {fuente}."
            )
        else:
            body = (
                f"Radiografia del gasto publico. {sigla}: {amount}. "
                f"Patron detectado en contrataciones publicas. "
                f"Fuente: {fuente}."
            )
        text = f"{body} {cta}"
        word_count = len(text.split())
        if word_count > 50:
            import sys as _sys
            print(f"WARNING: fallback voiceover tiene {word_count} palabras (max 50)", file=_sys.stderr)
        return text

    @staticmethod
    def _voiceover_ai(
        pattern: str, sigla: str, entidad: str, objeto: str,
        monto: float, dias: int, promedio: int, fuente: str,
        lic: dict[str, Any],
    ) -> str:
        if _requests is None:
            return ""

        api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENROUTER_API_KEY", "")
        base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
        if not api_key:
            return ""

        patron_labels = {
            "postor_unico_con_proceso_acelerado": "Postor unico con proceso acelerado",
            "proveedor_recurrente": "Proveedor recurrente",
            "fraccionamiento_contractual": "Fraccionamiento contractual",
            "funcionario_sancionado_activo": "Funcionario sancionado activo",
        }

        datos_extra: list[str] = []
        if pattern == "postor_unico_con_proceso_acelerado":
            datos_extra.append(f"Solo 1 postor se presento. Proceso: {dias} dias vs {promedio} dias promedio sector.")
        elif pattern == "proveedor_recurrente":
            wins = lic.get("numero_victorias") or lic.get("contratos_recurrentes", "")
            if wins:
                datos_extra.append(f"El mismo proveedor ha ganado {wins} contratos en los ultimos 12 meses.")
        elif pattern == "fraccionamiento_contractual":
            datos_extra.append(f"Contratos divididos en ventana de {dias} dias, mismo objeto, mismo proveedor.")
        elif pattern == "funcionario_sancionado_activo":
            sancion = lic.get("sancion_fecha", "")
            firma = lic.get("firma_fecha", "")
            if sancion and firma:
                datos_extra.append(f"Sancion vigente desde {sancion}. Contrato firmado el {firma}.")

        prompt = f"""Eres periodista de datos peruano. Escribe el voiceover en español para un reel de EXACTAMENTE 20 segundos sobre una alerta de contratacion publica detectada por el sistema Agente P.

Datos del caso:
- Patron: {patron_labels.get(pattern, pattern)}
- Entidad: {entidad} ({sigla})
- Objeto del contrato: {objeto}
- Monto: S/ {monto:,.0f}
- Fuente: {fuente}
{chr(10).join(f"- {d}" for d in datos_extra)}

Reglas ESTRICTAS:
1. Exactamente 4 a 5 oraciones cortas. Cada una termina en punto seguido de espacio.
2. Primera oracion siempre: "Radiografia del gasto publico."
3. Penultima oracion: menciona que son datos publicos y la fuente.
4. Ultima oracion siempre: "No es sentencia, son datos publicos. Siguenos: Agente Perry."
5. MAXIMO 50 PALABRAS EN TOTAL. Contar cuidadosamente. Si superas 50, cortar.
6. Tono directo, periodistico, sin adjetivos vacios. Sin palabras de relleno.
7. No inventes datos que no esten en el contexto.
8. Solo devuelve el texto del voiceover, sin explicaciones ni comillas."""

        use_openrouter = "openrouter" in base_url
        if use_openrouter:
            base = base_url.rstrip("/")
            if not base.endswith("/v1"):
                base = base + "/v1"
            endpoint = f"{base}/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": os.environ.get("ANTHROPIC_MODEL", "anthropic/claude-haiku-4.5"),
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300,
                "temperature": 0.7,
            }
            try:
                resp = _requests.post(endpoint, headers=headers, json=payload, timeout=30)
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"].strip()
            except Exception as exc:
                print(f"WARNING: voiceover AI (OpenRouter) failed: {exc}", flush=True)
                return ""
        else:
            endpoint = f"{base_url.rstrip('/')}/v1/messages"
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 300,
                "messages": [{"role": "user", "content": prompt}],
            }
            try:
                resp = _requests.post(endpoint, headers=headers, json=payload, timeout=30)
                resp.raise_for_status()
                return resp.json()["content"][0]["text"].strip()
            except Exception as exc:
                print(f"WARNING: voiceover AI (Anthropic) failed: {exc}", flush=True)
                return ""

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

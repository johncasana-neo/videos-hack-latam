"""Red flag detection engine."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any, Protocol

from dateutil import parser


PROMEDIO_SECTOR: dict[str, int] = {
    "MTC": 45,
    "MINSA": 38,
    "MINEDU": 35,
    "GORE": 42,
    "ESSALUD": 40,
    "DEFAULT": 40,
}
UMBRAL_LICITACION = 400_000.0


class SancionChecker(Protocol):
    def get_sancion(self, dni_o_ruc: str) -> dict[str, Any] | None: ...


@dataclass(frozen=True)
class RedFlag:
    tipo: str
    severity: int
    evidencia: dict[str, Any]
    patron_id: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RedFlagDetector:
    """Run public procurement anomaly detectors."""

    def analyze(
        self,
        licitacion: dict[str, Any],
        historial: list[dict[str, Any]] | None = None,
        contraloria: SancionChecker | None = None,
    ) -> list[dict[str, Any]]:
        historial = historial or []
        flags = [
            self.detect_postor_unico(licitacion),
            self.detect_proveedor_recurrente(licitacion, historial),
            self.detect_fraccionamiento(licitacion, historial),
        ]
        if contraloria is not None:
            flags.append(self.detect_funcionario_sancionado(licitacion, contraloria))
        return [flag.to_dict() for flag in flags if flag is not None]

    def detect_postor_unico(self, licitacion: dict[str, Any]) -> RedFlag | None:
        numero_postores = int(licitacion.get("numero_postores") or 0)
        dias_proceso = self._dias_proceso(licitacion)
        promedio = self._promedio_sector(licitacion)
        if numero_postores == 1 and dias_proceso < promedio * 0.5:
            return RedFlag(
                tipo="postor_unico",
                severity=9,
                patron_id="postor_unico_con_proceso_acelerado",
                evidencia={
                    "numero_postores": numero_postores,
                    "dias_proceso": dias_proceso,
                    "promedio_sector": promedio,
                    "codigo_seace": licitacion.get("codigo_seace", ""),
                },
            )
        return None

    def detect_proveedor_recurrente(
        self,
        licitacion: dict[str, Any],
        historial: list[dict[str, Any]],
    ) -> RedFlag | None:
        entidad = str(licitacion.get("entidad", ""))
        ruc_entidad = str(licitacion.get("ruc_entidad", ""))
        postores = [str(p) for p in licitacion.get("postores", []) if p]
        cutoff = date.today() - timedelta(days=365)
        for postor in postores:
            matches = [
                item for item in historial
                if postor in [str(p) for p in item.get("postores", [])]
                and (item.get("entidad") == entidad or item.get("ruc_entidad") == ruc_entidad)
                and self._parse_date(item.get("fecha_adjudicacion")) >= cutoff
            ]
            if len(matches) > 5:
                total = sum(float(item.get("monto_adjudicado") or 0) for item in matches)
                return RedFlag(
                    tipo="proveedor_recurrente",
                    severity=7,
                    patron_id="proveedor_recurrente",
                    evidencia={"ruc_proveedor": postor, "contratos_12_meses": len(matches), "monto_total": total},
                )
        return None

    def detect_fraccionamiento(
        self,
        licitacion: dict[str, Any],
        historial: list[dict[str, Any]],
    ) -> RedFlag | None:
        ref = self._parse_date(licitacion.get("fecha_adjudicacion"))
        start = ref - timedelta(days=30)
        postores = [str(p) for p in licitacion.get("postores", []) if p]
        ruc_entidad = str(licitacion.get("ruc_entidad", ""))
        for postor in postores:
            matches = [
                item for item in historial
                if postor in [str(p) for p in item.get("postores", [])]
                and str(item.get("ruc_entidad", "")) == ruc_entidad
                and start <= self._parse_date(item.get("fecha_adjudicacion")) <= ref
            ]
            total = sum(float(item.get("monto_adjudicado") or 0) for item in matches)
            if len(matches) >= 2 and total > UMBRAL_LICITACION:
                return RedFlag(
                    tipo="fraccionamiento",
                    severity=8,
                    patron_id="fraccionamiento_contractual",
                    evidencia={"ruc_proveedor": postor, "num_contratos": len(matches), "monto_total": total, "umbral": UMBRAL_LICITACION},
                )
        return None

    def detect_funcionario_sancionado(
        self,
        licitacion: dict[str, Any],
        contraloria: SancionChecker,
    ) -> RedFlag | None:
        for person_id in licitacion.get("funcionarios", []) + licitacion.get("signatarios", []):
            sancion = contraloria.get_sancion(str(person_id))
            if not sancion:
                continue
            vigencia = str(sancion.get("vigencia", "")).upper()
            fecha_fin = self._parse_optional_date(sancion.get("fecha_fin"))
            active = "VIGENTE" in vigencia or "ACTIVA" in vigencia or (fecha_fin is not None and fecha_fin >= date.today())
            if active:
                return RedFlag(
                    tipo="funcionario_sancionado",
                    severity=10,
                    patron_id="funcionario_sancionado_activo",
                    evidencia={"dni_o_ruc_censurado": self._mask_id(str(person_id)), "sancion": sancion},
                )
        return None

    def _dias_proceso(self, licitacion: dict[str, Any]) -> int:
        start = self._parse_date(licitacion.get("fecha_convocatoria"))
        end = self._parse_date(licitacion.get("fecha_adjudicacion"))
        return max((end - start).days, 1)

    def _promedio_sector(self, licitacion: dict[str, Any]) -> int:
        text = f"{licitacion.get('entidad', '')} {licitacion.get('entidad_sigla', '')}".upper()
        for key, value in PROMEDIO_SECTOR.items():
            if key != "DEFAULT" and key in text:
                return value
        return PROMEDIO_SECTOR["DEFAULT"]

    @staticmethod
    def _parse_date(value: Any) -> date:
        if isinstance(value, date):
            return value
        if not value:
            return date.today()
        try:
            return parser.parse(str(value), dayfirst=True).date()
        except (ValueError, TypeError):
            return date.today()

    @staticmethod
    def _parse_optional_date(value: Any) -> date | None:
        if not value:
            return None
        try:
            return parser.parse(str(value), dayfirst=True).date()
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _mask_id(value: str) -> str:
        return f"***{value[-3:]}" if len(value) >= 3 else "***"

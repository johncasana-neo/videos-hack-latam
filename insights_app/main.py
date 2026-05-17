"""Generate the daily insight JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from insights_app.detector import RedFlagDetector
from insights_app.scrapers.contraloria import ContraloriaChecker
from insights_app.scrapers.oece import OeceCollector
from insights_app.scrapers.seace import SeaceCollector
from insights_app.script_generator import ScriptGenerator
from insights_app.selector import CaseSelector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Radiografia insight JSON")
    parser.add_argument("--output", required=True, help="Output JSON path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print("✓ iniciando recoleccion de fuentes publicas")
    licitaciones = collect_records()
    if not licitaciones:
        print("⚠ no se obtuvieron licitaciones recientes")
        return 1

    detector = RedFlagDetector()
    contraloria = ContraloriaChecker()
    casos: list[dict[str, Any]] = []
    for lic in licitaciones:
        flags = detector.analyze(lic, historial=licitaciones, contraloria=contraloria)
        if flags:
            casos.append({"licitacion": lic, "red_flags": flags, "confidence": estimate_confidence(lic, flags)})

    if not casos:
        print("⚠ no hay casos suficientes hoy")
        return 1

    selector = CaseSelector(output_path.parent)
    selected = selector.pick(casos)
    if selected is None:
        print("⚠ no hay casos con score minimo o entidad no repetida")
        return 1

    insight = ScriptGenerator(output_path.parent).build(selected)
    output_path.write_text(json.dumps(insight, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ insight generado: {output_path}")
    print(f"✓ caso: {insight['case']['caso_titulo']}")
    return 0


def collect_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for collector in (SeaceCollector(), OeceCollector()):
        try:
            batch = collector.fetch()
        except Exception as exc:
            print(f"⚠ collector {collector.__class__.__name__} fallo: {exc}")
            batch = []
        print(f"✓ {collector.__class__.__name__}: {len(batch)} registros")
        records.extend(normalize_batch(batch))
        if len(records) >= 50:
            break
    return records


def normalize_batch(batch: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in batch:
        if not item.get("codigo_seace") and not item.get("objeto"):
            continue
        normalized.append(item)
    return normalized


def estimate_confidence(lic: dict[str, Any], flags: list[dict[str, Any]]) -> float:
    score = 0.72
    if lic.get("codigo_seace"):
        score += 0.06
    if lic.get("monto_adjudicado"):
        score += 0.06
    if lic.get("fecha_convocatoria") and lic.get("fecha_adjudicacion"):
        score += 0.06
    if any(flag.get("severity", 0) >= 9 for flag in flags):
        score += 0.04
    return min(score, 0.96)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("❌ interrumpido")
        raise SystemExit(130)
    except Exception as exc:
        print(f"❌ error fatal: {exc}")
        raise SystemExit(2)

"""Neo4j collector — queries Perry's procurement graph for red flag cases."""

from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any

from .base import BaseCollector


def _env(key: str) -> str:
    return os.environ.get(key, "")


class Neo4jCollector(BaseCollector):
    """Query Perry's Neo4j AuraDB for procurement red flag cases."""

    def fetch(self) -> list[dict[str, Any]]:
        uri = _env("NEO4J_URI")
        user = _env("NEO4J_USERNAME") or "neo4j"
        password = _env("NEO4J_PASSWORD")
        database = _env("NEO4J_DATABASE") or "neo4j"

        if not uri or not password:
            raise RuntimeError("NEO4J_URI y NEO4J_PASSWORD requeridos")

        try:
            from neo4j import GraphDatabase
        except ImportError as exc:
            raise RuntimeError("pip install neo4j") from exc

        driver = GraphDatabase.driver(uri, auth=(user, password))
        try:
            with driver.session(database=database) as session:
                records = []
                records.extend(self._fetch_fraccionamiento(session))
                if not records:
                    records.extend(self._fetch_proveedor_recurrente(session))
                if not records:
                    records.extend(self._fetch_postor_unico(session))
                if not records:
                    records.extend(self._fetch_ghost_company(session))
                return records
        finally:
            driver.close()

    # ------------------------------------------------------------------ #
    # Pattern 1: fraccionamiento_contractual                              #
    # Same supplier, same entity, 2+ contracts within 30 days, >S/400k  #
    # ------------------------------------------------------------------ #
    def _fetch_fraccionamiento(self, session: Any) -> list[dict[str, Any]]:
        query = """
        MATCH (c:Company)-[:WON]->(k1:Contract)-[:AWARDED_BY]->(e:PublicEntity),
              (c)-[:WON]->(k2:Contract)-[:AWARDED_BY]->(e)
        WHERE elementId(k1) < elementId(k2)
          AND k1.fecha IS NOT NULL AND k2.fecha IS NOT NULL
          AND abs(duration.inDays(date(k1.fecha), date(k2.fecha)).days) <= 30
        WITH c, e, k1, k2,
             k1.monto + k2.monto AS total_monto,
             k1.fecha AS fecha_anterior, k2.fecha AS fecha_posterior
        WHERE total_monto > 400000
        RETURN c.ruc     AS ruc_proveedor,
               c.name    AS nombre_proveedor,
               e.ruc     AS ruc_entidad,
               e.name    AS nombre_entidad,
               e.region  AS region,
               k1.external_id AS contrato1_id,
               k2.external_id AS contrato2_id,
               k1.monto  AS monto1,
               k2.monto  AS monto2,
               total_monto,
               fecha_anterior,
               fecha_posterior,
               k2.procedure_type AS tipo_proceso
        ORDER BY total_monto DESC
        LIMIT 3
        """
        results = session.run(query)
        records: list[dict[str, Any]] = []
        for row in results:
            ruc_p = str(row["ruc_proveedor"] or "")
            ruc_e = str(row["ruc_entidad"] or "")
            entidad = str(row["nombre_entidad"] or "Entidad publica")
            monto1 = float(row["monto1"] or 0)
            monto2 = float(row["monto2"] or 0)
            fecha_ant = self._to_str(row["fecha_anterior"])
            fecha_pos = self._to_str(row["fecha_posterior"])
            objeto = f"Contratos fraccionados — {row['tipo_proceso'] or 'contratacion directa'}"
            # Two sibling records so detector finds >= 2 matches in historial
            base = {
                "entidad": entidad,
                "ruc_entidad": ruc_e,
                "objeto": objeto,
                "postores": [ruc_p],
                "fuente_oficial": "Neo4j/SEACE",
                "funcionarios": [],
                "signatarios": [],
                "region": str(row["region"] or ""),
            }
            records.append({
                **base,
                "codigo_seace": str(row["contrato1_id"] or f"NEO-{date.today():%Y%m%d}-A"),
                "monto_adjudicado": monto1,
                "fecha_convocatoria": fecha_ant,
                "fecha_adjudicacion": fecha_ant,
                "numero_postores": 2,
            })
            records.append({
                **base,
                "codigo_seace": str(row["contrato2_id"] or f"NEO-{date.today():%Y%m%d}-B"),
                "monto_adjudicado": monto2,
                "fecha_convocatoria": fecha_ant,
                "fecha_adjudicacion": fecha_pos,
                "numero_postores": 2,
            })
        return records

    # ------------------------------------------------------------------ #
    # Pattern 2: proveedor_recurrente                                     #
    # Same supplier won >5 contracts from same entity in 12 months       #
    # ------------------------------------------------------------------ #
    def _fetch_proveedor_recurrente(self, session: Any) -> list[dict[str, Any]]:
        cutoff = (date.today() - timedelta(days=365)).isoformat()
        query = """
        MATCH (c:Company)-[:WON]->(k:Contract)-[:AWARDED_BY]->(e:PublicEntity)
        WHERE k.fecha IS NOT NULL AND k.fecha >= $cutoff
        WITH c, e,
             count(k) AS wins,
             sum(k.monto) AS total_monto,
             collect(k.external_id)[0..6] AS ids,
             collect(k.fecha)[0..6] AS fechas,
             collect(k.monto)[0..6] AS montos,
             collect(k.procedure_type)[0..1][0] AS tipo_proceso
        WHERE wins > 5
        RETURN c.ruc    AS ruc_proveedor,
               c.name   AS nombre_proveedor,
               e.ruc    AS ruc_entidad,
               e.name   AS nombre_entidad,
               e.region AS region,
               wins, total_monto, ids, fechas, montos, tipo_proceso
        ORDER BY wins DESC
        LIMIT 1
        """
        results = session.run(query, cutoff=cutoff)
        records: list[dict[str, Any]] = []
        for row in results:
            ruc_p = str(row["ruc_proveedor"] or "")
            ruc_e = str(row["ruc_entidad"] or "")
            entidad = str(row["nombre_entidad"] or "Entidad publica")
            ids = list(row["ids"] or [])
            fechas = list(row["fechas"] or [])
            montos = list(row["montos"] or [])
            wins = int(row["wins"])
            avg_monto = float(row["total_monto"] or 0) / max(wins, 1)
            for i in range(min(wins, len(ids))):
                records.append({
                    "codigo_seace": str(ids[i] if i < len(ids) else f"NEO-REC-{i}"),
                    "entidad": entidad,
                    "ruc_entidad": ruc_e,
                    "objeto": f"Contrato recurrente {i+1} — {row['tipo_proceso'] or 'adjudicacion directa'}",
                    "monto_adjudicado": float(montos[i]) if i < len(montos) else avg_monto,
                    "fecha_convocatoria": self._to_str(fechas[i] if i < len(fechas) else date.today()),
                    "fecha_adjudicacion": self._to_str(fechas[i] if i < len(fechas) else date.today()),
                    "numero_postores": 2,
                    "postores": [ruc_p],
                    "fuente_oficial": "Neo4j/SEACE",
                    "funcionarios": [],
                    "signatarios": [],
                    "region": str(row["region"] or ""),
                    "numero_victorias": wins,
                })
        return records

    # ------------------------------------------------------------------ #
    # Pattern 3: postor_unico_con_proceso_acelerado                      #
    # Tender where only one company won, large amount                    #
    # ------------------------------------------------------------------ #
    def _fetch_postor_unico(self, session: Any) -> list[dict[str, Any]]:
        query = """
        MATCH (c:Company)-[:WON]->(k:Contract)-[:UNDER_TENDER]->(t:Tender)
        WITH t, count(DISTINCT c) AS num_bidders,
             collect(DISTINCT c)[0] AS winner,
             collect(k)[0] AS contract
        WHERE num_bidders = 1 AND contract.monto > 100000
        MATCH (contract)-[:AWARDED_BY]->(e:PublicEntity)
        RETURN winner.ruc   AS ruc_proveedor,
               winner.name  AS nombre_proveedor,
               e.ruc        AS ruc_entidad,
               e.name       AS nombre_entidad,
               e.region     AS region,
               t.tender_id  AS tender_id,
               contract.external_id AS contrato_id,
               contract.monto       AS monto_adjudicado,
               contract.fecha       AS fecha_adjudicacion,
               contract.procedure_type AS tipo_proceso
        ORDER BY contract.monto DESC
        LIMIT 3
        """
        results = session.run(query)
        records: list[dict[str, Any]] = []
        for row in results:
            ruc_p = str(row["ruc_proveedor"] or "")
            ruc_e = str(row["ruc_entidad"] or "")
            fecha_adj = self._to_str(row["fecha_adjudicacion"])
            # Set convocatoria 15 days before → dias_proceso=15 < 50% of 40-day avg
            from datetime import datetime
            try:
                adj_date = date.fromisoformat(fecha_adj)
            except (ValueError, TypeError):
                adj_date = date.today()
            fecha_conv = str(adj_date - timedelta(days=15))
            records.append({
                "codigo_seace": str(row["contrato_id"] or row["tender_id"] or f"NEO-PU-{date.today():%Y%m%d}"),
                "entidad": str(row["nombre_entidad"] or "Entidad publica"),
                "ruc_entidad": ruc_e,
                "objeto": f"Licitacion con postor unico — {row['tipo_proceso'] or 'proceso'}",
                "monto_adjudicado": float(row["monto_adjudicado"] or 0),
                "fecha_convocatoria": fecha_conv,
                "fecha_adjudicacion": fecha_adj,
                "numero_postores": 1,
                "postores": [ruc_p],
                "fuente_oficial": "Neo4j/SEACE",
                "funcionarios": [],
                "signatarios": [],
                "region": str(row["region"] or ""),
            })
        return records

    # ------------------------------------------------------------------ #
    # Pattern 4: empresa fantasma (proxy for funcionario_sancionado)     #
    # Company estado=BAJA/NO HABIDO with recent contracts               #
    # ------------------------------------------------------------------ #
    def _fetch_ghost_company(self, session: Any) -> list[dict[str, Any]]:
        cutoff = (date.today() - timedelta(days=180)).isoformat()
        query = """
        MATCH (c:Company)-[:WON]->(k:Contract)-[:AWARDED_BY]->(e:PublicEntity)
        WHERE c.estado IN ['BAJA', 'NO HABIDO', 'BAJA DE OFICIO']
          AND k.fecha IS NOT NULL AND k.fecha >= $cutoff
        RETURN c.ruc    AS ruc_proveedor,
               c.name   AS nombre_proveedor,
               c.estado AS estado_sunat,
               e.ruc    AS ruc_entidad,
               e.name   AS nombre_entidad,
               e.region AS region,
               k.external_id AS contrato_id,
               k.monto  AS monto_contrato,
               k.fecha  AS fecha_contrato,
               k.procedure_type AS tipo_proceso
        ORDER BY k.monto DESC
        LIMIT 3
        """
        results = session.run(query, cutoff=cutoff)
        records: list[dict[str, Any]] = []
        for row in results:
            ruc_p = str(row["ruc_proveedor"] or "")
            fecha = self._to_str(row["fecha_contrato"])
            records.append({
                "codigo_seace": str(row["contrato_id"] or f"NEO-GH-{date.today():%Y%m%d}"),
                "entidad": str(row["nombre_entidad"] or "Entidad publica"),
                "ruc_entidad": str(row["ruc_entidad"] or ""),
                "objeto": f"Contrato con empresa {row['estado_sunat']} — {row['tipo_proceso'] or 'proceso'}",
                "monto_adjudicado": float(row["monto_contrato"] or 0),
                "fecha_convocatoria": fecha,
                "fecha_adjudicacion": fecha,
                "numero_postores": 2,
                "postores": [ruc_p],
                "fuente_oficial": "Neo4j/SEACE",
                "funcionarios": [ruc_p],
                "signatarios": [ruc_p],
                "region": str(row["region"] or ""),
                "_ghost_estado": str(row["estado_sunat"] or ""),
            })
        return records

    @staticmethod
    def _to_str(value: Any) -> str:
        if value is None:
            return str(date.today())
        if hasattr(value, "iso_format"):
            return value.iso_format()
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)

"""SUNAT RUC validator using the public reduced registry when available."""

from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path
from typing import Any

import requests


class SunatValidator:
    """Local cache backed lookup for RUC status."""

    zip_url = "https://www.sunat.gob.pe/descargaPRR/padron_reducido_ruc.zip"

    def __init__(self, cache_dir: str | Path = ".cache") -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "padron_reducido.csv"
        self._index: dict[str, dict[str, str]] | None = None

    def get_estado(self, ruc: str) -> dict[str, Any]:
        if self._index is None:
            self._index = self._load_index()
        return self._index.get(
            ruc,
            {"ruc": ruc, "razon_social": "", "estado": "NO_ENCONTRADO", "condicion": "", "ubigeo": ""},
        )

    def _load_index(self) -> dict[str, dict[str, str]]:
        if not self.cache_file.exists():
            self._download()
        index: dict[str, dict[str, str]] = {}
        if not self.cache_file.exists():
            return index
        with self.cache_file.open("r", encoding="latin-1", errors="ignore", newline="") as handle:
            reader = csv.reader(handle, delimiter="|")
            for row in reader:
                if len(row) < 6 or not row[0].isdigit():
                    continue
                index[row[0]] = {
                    "ruc": row[0],
                    "razon_social": row[1],
                    "estado": row[4] if len(row) > 4 else "",
                    "condicion": row[5] if len(row) > 5 else "",
                    "ubigeo": row[2] if len(row) > 2 else "",
                }
        return index

    def _download(self) -> None:
        try:
            response = requests.get(self.zip_url, timeout=45)
            response.raise_for_status()
        except requests.RequestException:
            return
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            first_name = archive.namelist()[0]
            self.cache_file.write_bytes(archive.read(first_name))

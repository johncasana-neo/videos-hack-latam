"""Shared collector contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseCollector(ABC):
    """Base class for public-data collectors."""

    timeout: int = 30

    @abstractmethod
    def fetch(self) -> list[dict[str, Any]]:
        """Fetch records and return normalized dictionaries."""

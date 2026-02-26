"""Base classes for all collectors."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class CollectorResult:
    data: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


class BaseCollector(ABC):
    name: str = "base"

    @abstractmethod
    def _collect(self) -> dict:
        """Implement in subclass to return collected data."""
        ...

    def collect(self) -> CollectorResult:
        """Wrap _collect in try/except; never raises."""
        try:
            return CollectorResult(data=self._collect())
        except Exception as exc:  # noqa: BLE001
            return CollectorResult(errors=[f"{self.name}: {exc}"])

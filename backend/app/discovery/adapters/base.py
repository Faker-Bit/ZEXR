"""Source adapter contract.

An adapter turns a permitted upstream payload into `DiscoveredItem` objects.  It
never decides whether an offer is real — that is `normalize.py`'s job — and it
never fabricates fields.  Missing data stays `None`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.discovery.base import FetchResult
from app.schemas.offer import DiscoveredItem


@dataclass
class AdapterContext:
    """Everything an adapter may need; passed in rather than imported."""

    source: Any
    payload: FetchResult | None = None
    api_key: str | None = None
    config: dict[str, Any] = field(default_factory=dict)

    def option(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)


@dataclass
class AdapterOutcome:
    items: list[DiscoveredItem] = field(default_factory=list)
    http_status: int | None = None
    warnings: list[str] = field(default_factory=list)
    total_seen: int = 0
    #: rows the source returned but the config's `filter` rules excluded
    filtered: int = 0
    truncated: bool = False


class SourceAdapter(ABC):
    name: str = "base"
    #: adapters that require JS execution or auth are flagged on the source row
    requires_js: bool = False
    supports_conditional: bool = True

    @abstractmethod
    def fetch(self, ctx: AdapterContext) -> FetchResult:  # pragma: no cover - interface
        ...

    @abstractmethod
    def parse(self, ctx: AdapterContext) -> AdapterOutcome:  # pragma: no cover - interface
        ...

    def run(self, ctx: AdapterContext) -> AdapterOutcome:
        result = self.fetch(ctx)
        ctx.payload = result
        if not result.ok:
            return AdapterOutcome(
                http_status=result.status_code,
                warnings=[result.error or "fetch failed"],
            )
        outcome = self.parse(ctx)
        outcome.http_status = result.status_code
        if outcome.total_seen > ctx.option("max_items", ctx.source.max_items):
            outcome.truncated = True
        return outcome
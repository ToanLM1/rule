"""Fail-closed adapter registry."""

from __future__ import annotations

from brp.adapters.contracts import SOURCE_ADAPTER_CAPABILITY, SourceAdapter


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, SourceAdapter] = {}

    def register(self, adapter: SourceAdapter) -> None:
        if not isinstance(adapter, SourceAdapter):
            raise TypeError("adapter does not implement SourceAdapter")
        if adapter.capability_version != SOURCE_ADAPTER_CAPABILITY:
            raise ValueError(f"unsupported capability: {adapter.capability_version}")
        if adapter.name in self._adapters:
            raise ValueError(f"adapter already registered: {adapter.name}")
        self._adapters[adapter.name] = adapter

    def get(self, name: str) -> SourceAdapter:
        try:
            return self._adapters[name]
        except KeyError as exc:
            raise KeyError(f"unknown adapter: {name}") from exc

    def selected(self, names: list[str]) -> list[SourceAdapter]:
        return [self.get(name) for name in names]

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))

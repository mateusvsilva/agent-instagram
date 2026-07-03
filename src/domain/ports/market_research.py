"""Porta `MarketResearchProvider` — fonte da pesquisa de mercado (HU-BACKEND-02).

A pesquisa roda antes da imagem e da legenda. A FONTE real dos dados é uma
decisão de produto pendente (DA-02), por isso é plugável. Implementada hoje pelo
`StubMarketResearchProvider`. O contrato (`ContentRequest` -> `MarketResearch`)
está fechado.
"""
from typing import Protocol, runtime_checkable

from ..models.content import ContentRequest, MarketResearch


@runtime_checkable
class MarketResearchProvider(Protocol):
    async def research(self, request: ContentRequest) -> MarketResearch: ...

    @property
    def source_name(self) -> str: ...

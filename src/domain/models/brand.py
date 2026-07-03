"""Identidade de marca lida da pasta `prompts/` (HU-BACKEND-05).

Entidade pura, sem I/O: representa o conteúdo dos arquivos de marca já
carregado em memória, mais a informação de quais arquivos estão incompletos
(vazios ou ainda com os marcadores `> PREENCHER:`). Quem lê o disco é o
`PromptsLoaderService`; aqui ficam só os dados e as regras de leitura deles.
"""
from pydantic import BaseModel, Field


class BrandIdentity(BaseModel):
    identity: str = ""
    image_guidelines: str = ""
    caption_guidelines: str = ""
    hashtag_strategy: str = ""
    # Nomes lógicos dos arquivos incompletos (ex.: "identity", "caption_guidelines").
    incomplete_sections: list[str] = Field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        return not self.incomplete_sections

    def image_brief(self) -> str:
        """Bloco de diretrizes de marca para o prompt de imagem."""
        return self._join(self.identity, self.image_guidelines)

    def caption_brief(self) -> str:
        """Bloco de diretrizes de marca para a redação da legenda."""
        return self._join(self.identity, self.caption_guidelines, self.hashtag_strategy)

    @staticmethod
    def _join(*blocks: str) -> str:
        return "\n\n".join(block.strip() for block in blocks if block and block.strip())
